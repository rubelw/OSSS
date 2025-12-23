import logging
from typing import Dict, Any, Optional, Union, Tuple, List
import asyncio
import json
from OSSS.ai.agents.base_agent import (
    BaseAgent,
    NodeType,
    NodeInputSchema,
    NodeOutputSchema,
)
from OSSS.ai.context import AgentContext
from OSSS.ai.llm.llm_interface import LLMInterface

# Configuration system imports
from OSSS.ai.config.agent_configs import SynthesisConfig
from OSSS.ai.workflows.prompt_composer import PromptComposer, ComposedPrompt

# Structured output integration using LangChain service pattern
from OSSS.ai.services.langchain_service import LangChainService
from OSSS.ai.agents.models import SynthesisOutput, SynthesisTheme, ConfidenceLevel
from OSSS.ai.utils.llm_text import coerce_llm_text

logger = logging.getLogger(__name__)


class SynthesisAgent(BaseAgent):
    """
    Enhanced agent for sophisticated synthesis of multi-agent outputs with LLM-powered
    thematic analysis, conflict resolution, and comprehensive knowledge integration.

    Performs deep analysis of agent outputs to identify themes, resolve conflicts,
    extract meta-insights, and produce coherent, wiki-ready synthesis.

    Parameters
    ----------
    llm : LLMInterface, optional
        LLM interface for synthesis analysis. If None, uses default OpenAI setup.
    config : Optional[SynthesisConfig], optional
        Configuration for agent behavior. If None, uses default configuration.
        Maintains backward compatibility - existing code continues to work.

    Attributes
    ----------
    config : SynthesisConfig
        Configuration for agent behavior and prompt composition.
    """

    def __init__(
        self,
        llm: Optional[Union[LLMInterface, str]] = "default",
        config: Optional[SynthesisConfig] = None,
    ) -> None:
        # Configuration system - backward compatible
        # All config classes have sensible defaults via Pydantic Field definitions
        self.config = config if config is not None else SynthesisConfig()

        # Pass timeout from config to BaseAgent
        super().__init__(
            "synthesis", timeout_seconds=self.config.execution_config.timeout_seconds
        )

        self._prompt_composer = PromptComposer()
        self._composed_prompt: Optional[ComposedPrompt]

        # Use sentinel value to distinguish between None (explicit) and default
        if llm == "default":
            self.llm: Optional[LLMInterface] = self._create_default_llm()
        else:
            # Type guard: ensure llm is either None or LLMInterface
            if llm is None:
                self.llm = None
            elif hasattr(llm, "generate"):
                self.llm = llm  # type: ignore[assignment]
            else:
                self.llm = None

        # Initialize LangChain service for structured output (following RefinerAgent pattern)
        self.structured_service: Optional[LangChainService] = None
        self._setup_structured_service()

        # Compose the prompt on initialization for performance
        self._update_composed_prompt()

    def _as_text(self, x: Any) -> str:
        """Normalize unknown values (str/dict/list/etc.) into safe display text."""
        if x is None:
            return ""
        if isinstance(x, str):
            return x
        try:
            return json.dumps(x, indent=2, ensure_ascii=False, default=str)
        except Exception:
            return str(x)

    def _extract_db_payload(self, data_query_output: Any) -> Any:
        """
        If data_query returns an envelope dict, extract the most useful payload.
        Adjust keys here to match your data_query agent envelope contract.
        """
        if not isinstance(data_query_output, dict):
            return data_query_output

        for key in ("rows", "data", "items", "result", "results", "payload", "body"):
            if key in data_query_output:
                return data_query_output[key]

        return data_query_output

    def _to_int(self, v: Any, default: int = 0) -> int:
        try:
            if v is None:
                return default
            if isinstance(v, bool):
                return int(v)
            if isinstance(v, int):
                return v
            if isinstance(v, float):
                return int(v)
            if isinstance(v, str):
                s = v.strip()
                if s == "":
                    return default
                return int(float(s))  # handles "5" or "5.0"
            return default
        except Exception:
            return default




    def _find_data_query_payload(self, outputs: Dict[str, Any]) -> Tuple[Optional[str], Any]:
        """
        Find the data_query payload even when the key is namespaced like:
          'data_query:warrantys' or 'data_query:teachers'
        Returns (key, payload) or (None, None).
        """
        # 1) exact key
        if "data_query" in outputs:
            return "data_query", outputs["data_query"]

        # 2) namespaced keys
        for k, v in outputs.items():
            if str(k).lower().startswith("data_query:"):
                return k, v

        # 3) fallback variants you might have
        for k, v in outputs.items():
            lk = str(k).lower()
            if lk.startswith("dataquery:") or lk == "dataquery":
                return k, v

        return None, None

    def _to_markdown_table(
            self,
            rows: List[Dict[str, Any]],
            max_rows: int = 25,
            max_cols: int = 10,
    ) -> str:
        if not rows:
            return "_No rows returned._"

        # Stable columns from first row; cap for readability
        cols = list(rows[0].keys())[:max_cols]
        rows = rows[:max_rows]

        def cell(v: Any) -> str:
            if v is None:
                return ""
            if isinstance(v, (dict, list)):
                s = json.dumps(v, ensure_ascii=False, default=str)
            else:
                s = str(v)
            s = s.replace("\n", " ").strip()
            if len(s) > 120:
                s = s[:120] + "…"
            # prevent breaking markdown table pipes
            s = s.replace("|", "\\|")
            return s

        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join(["---"] * len(cols)) + " |"
        body = "\n".join(
            "| " + " | ".join(cell(r.get(c)) for c in cols) + " |"
            for r in rows
        )

        return "\n".join([header, sep, body])


    def _format_db_appendix(self, outputs: Dict[str, Any]) -> str:
        """
        Pretty DB appendix for the UI:
        - Table when rows are list[dict]
        - JSON code block otherwise
        - Never crashes on dict/list
        """
        dq_key, dq_payload = self._find_data_query_payload(outputs)
        if not dq_key or dq_payload is None:
            return ""

        payload = self._extract_db_payload(dq_payload)

        # Normalize rows into list if possible
        rows: list[dict[str, Any]] = []
        if isinstance(payload, list) and payload and all(isinstance(x, dict) for x in payload):
            rows = payload  # type: ignore[assignment]
        elif isinstance(payload, dict):
            # common shape: {"rows": [...]} or {"items": [...]}
            inner = None
            for k in ("rows", "items", "data", "results"):
                if k in payload:
                    inner = payload[k]
                    break
            if isinstance(inner, list) and inner and all(isinstance(x, dict) for x in inner):
                rows = inner  # type: ignore[assignment]

        # Meta header (best-effort)
        meta_bits: list[str] = []
        if isinstance(dq_payload, dict):
            view = str(dq_payload.get("view") or "").strip()
            if view:
                meta_bits.append(f"view={view}")
            status_code = dq_payload.get("status_code")
            if status_code is not None:
                meta_bits.append(f"status={self._to_int(status_code, default=0)}")
            row_count = dq_payload.get("row_count")
            if row_count is not None:
                meta_bits.append(f"rows={self._to_int(row_count, default=0)}")

        meta_line = f"**{(' | '.join(meta_bits))}**\n\n" if meta_bits else ""

        # Prefer table when we have row dicts
        if rows:
            table = self._to_markdown_table(rows, max_rows=25, max_cols=10)
            return (
                "\n\n---\n"
                "## Database Results\n"
                f"{meta_line}"
                f"{table}\n"
            )

        # Otherwise dump a compact JSON preview (capped)
        text = self._as_text(payload).strip()
        if not text:
            return ""

        max_chars = 12_000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n...<truncated>..."

        return (
            "\n\n---\n"
            "## Database Results\n"
            f"{meta_line}"
            "```json\n"
            f"{text}\n"
            "```\n"
        )

    def _wrap_output(
            self,
            output: str | None = None,
            *,
            intent: str | None = None,
            tone: str | None = None,
            action: str | None = None,
            sub_tone: str | None = None,
            content: str | None = None,  # legacy alias
            **_: Any,
    ) -> dict:
        return super()._wrap_output(
            output=output,
            intent=intent,
            tone=tone,
            action=action,
            sub_tone=sub_tone,
            content=content,
        )

    def _compute_word_count(self, text: str) -> int:
        """
        Compute word count deterministically server-side.

        We do this here (instead of trusting the LLM) so `word_count` is always accurate
        and never causes validation failures due to model miscount.
        """
        return len((text or "").strip().split())

    def _norm(self, name: str) -> str:
        return (name or "").strip().lower()

    def _stringify_agent_output(self, output: Any) -> str:
        """
        Convert agent output objects into a useful string.
        (Fixes cases like: <OSSS.ai.llm.llm_interface.LLMResponse object at 0x...>)
        """
        if output is None:
            return ""
        # Common OSSS pattern
        if hasattr(output, "text"):
            try:
                return str(output.text or "").strip()
            except Exception:
                pass
        return str(output).strip()

    def _dedupe_agent_outputs(self, outputs: Dict[str, Any]) -> Dict[str, str]:
        """
        De-dupe by normalized agent name (refiner/Refiner -> refiner).
        Keep the first non-empty value (or first seen if all empty).
        Excludes this agent's own output key.
        """
        unique: dict[str, str] = {}
        for name, raw in outputs.items():
            if name == self.name:
                continue

            key = self._norm(name)
            text = self._stringify_agent_output(raw)

            if key not in unique or (not unique[key] and text):
                unique[key] = text

        return unique

    def _create_default_llm(self) -> Optional[LLMInterface]:
        """Create default LLM interface using OpenAI configuration."""
        try:
            # Import here to avoid circular imports
            from OSSS.ai.llm.openai import OpenAIChatLLM
            from OSSS.ai.config.openai_config import OpenAIConfig

            openai_config = OpenAIConfig.load()
            return OpenAIChatLLM(
                api_key=openai_config.api_key,
                model=openai_config.model,
                base_url=openai_config.base_url,
            )
        except Exception as e:
            logger.warning(
                f"Failed to create OpenAI LLM: {e}. Using fallback synthesis."
            )
            return None

    def _setup_structured_service(self) -> None:
        """Initialize the LangChain service for structured output support."""
        try:
            # Only set up if we have an LLM
            if self.llm is None:
                logger.info(
                    f"[{self.name}] No LLM available, structured service disabled"
                )
                self.structured_service = None
                return

            # Get API key from LLM interface
            api_key = getattr(self.llm, "api_key", None)

            # Let discovery service choose the best model for SynthesisAgent
            self.structured_service = LangChainService(
                model=None,  # Let discovery service choose
                api_key=api_key,
                temperature=0.2,  # Use low temperature for consistent synthesis
                agent_name="synthesis",  # Enable agent-specific model selection
                use_discovery=True,  # Enable model discovery
            )

            # Log the selected model
            selected_model = self.structured_service.model_name
            logger.info(
                f"[{self.name}] Structured output service initialized with discovered model: {selected_model}"
            )
        except Exception as e:
            logger.warning(
                f"[{self.name}] Failed to initialize structured service: {e}. "
                f"Will use traditional LLM interface only."
            )
            self.structured_service = None

        selected_model = (self.structured_service.model_name or "")
        if "llama" in selected_model.lower():
            logger.info(f"[{self.name}] Disabling structured output for llama models (speed + reliability)")
            self.structured_service = None
            return

    def _update_composed_prompt(self) -> None:
        """Update the composed prompt based on current configuration."""
        try:
            self._composed_prompt = self._prompt_composer.compose_synthesis_prompt(
                self.config
            )
            logger.debug(
                f"[{self.name}] Prompt composed with config: {self.config.synthesis_strategy}"
            )
        except Exception as e:
            logger.warning(
                f"[{self.name}] Failed to compose prompt, using default: {e}"
            )
            self._composed_prompt = None

    def _get_system_prompt(self) -> str:
        """Get the system prompt, using composed prompt if available, otherwise fallback."""
        if self._composed_prompt and self._prompt_composer.validate_composition(
            self._composed_prompt
        ):
            return self._composed_prompt.system_prompt
        else:
            # Fallback to embedded prompt for backward compatibility
            logger.debug(f"[{self.name}] Using default system prompt (fallback)")
            return self._get_default_system_prompt()

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for fallback compatibility."""
        try:
            from OSSS.ai.agents.synthesis.prompts import SYNTHESIS_SYSTEM_PROMPT

            return SYNTHESIS_SYSTEM_PROMPT
        except ImportError:
            # Fallback to basic embedded prompt
            return """As a synthesis agent, analyze and integrate multiple agent outputs to create comprehensive, coherent responses that combine all perspectives."""

    def update_config(self, config: SynthesisConfig) -> None:
        """
        Update the agent configuration and recompose prompts.

        Parameters
        ----------
        config : SynthesisConfig
            New configuration to apply
        """
        self.config = config
        self._update_composed_prompt()
        logger.info(
            f"[{self.name}] Configuration updated: {config.synthesis_strategy} strategy"
        )

    async def run(self, context: AgentContext) -> AgentContext:
        """
        Execute enhanced synthesis with sophisticated LLM-powered analysis.

        Performs thematic analysis, conflict resolution, and comprehensive synthesis
        of all agent outputs into a coherent, wiki-ready final result.

        Parameters
        ----------
        context : AgentContext
            The context containing outputs from other agents.

        Returns
        -------
        AgentContext
            The updated context with the sophisticated synthesis result.
        """
        outputs = context.agent_outputs

        query = context.query.strip()

        # Always define analysis so later code can safely reference it
        analysis: Dict[str, Any] = {}
        # If you want full thematic analysis, enable this:
        # analysis = await self._analyze_agent_outputs(query, outputs, context)

        logger.info(f"[{self.name}] Running synthesis for query: {query}")
        logger.info(f"[{self.name}] Processing outputs from: {list(outputs.keys())}")



        try:
            # Try structured output first if available, otherwise use traditional approach
            if self.structured_service:
                try:
                    final_synthesis = await self._run_structured(
                        query, outputs, context
                    )
                except Exception as e:
                    logger.warning(
                        f"[{self.name}] Structured output failed, falling back to traditional: {e}"
                    )
                    # Fall back to traditional synthesis
                    #analysis = await self._analyze_agent_outputs(
                    #    query, outputs, context
                    #)
                    if self.llm:
                        synthesis_result = await self._llm_powered_synthesis(
                            query, outputs, analysis, context
                        )
                    else:
                        synthesis_result = await self._fallback_synthesis(
                            query, outputs, context
                        )
                    final_synthesis = await self._format_final_output(
                        query, synthesis_result, analysis
                    )
            else:
                # Traditional synthesis path (backward compatible)
                #analysis = await self._analyze_agent_outputs(query, outputs, context)

                if self.llm:
                    synthesis_result = await self._llm_powered_synthesis(
                        query, outputs, analysis, context
                    )
                else:
                    synthesis_result = await self._fallback_synthesis(
                        query, outputs, context
                    )

                final_synthesis = await self._format_final_output(
                    query, synthesis_result, analysis
                )

            # Step 4: Update context
            from OSSS.ai.utils.llm_text import coerce_llm_text

            final_text = coerce_llm_text(final_synthesis).strip()

            # ✅ Append DB results (pretty + safe) so UI includes them, never crash synthesis
            try:
                final_text = final_text + self._format_db_appendix(outputs)
            except Exception as e:
                logger.warning(f"[{self.name}] Failed to append DB results: {e}")

            env = self._wrap_output(
                output=final_text,
                intent="synthesis_query",
                tone="neutral",
                action="read",
                sub_tone=None,
            )

            context.add_agent_output(self.name, final_text)
            context.add_agent_output_envelope(self.name, env)

            context.set_final_synthesis(final_text)
            context.log_trace(self.name, input_data=list(outputs.keys()), output_data=final_text)

            # Log successful execution
            logger.info(
                f"[{self.name}] Generated synthesis: {len(final_synthesis)} characters"
            )

            context.complete_agent_execution(self.name, success=True)

            return context

        except Exception as e:
            # Handle failures gracefully
            logger.error(f"[{self.name}] Error during synthesis: {e}")

            # Fall back to basic concatenation
            fallback_output = await self._create_emergency_fallback(query, outputs)
            context.add_agent_output(self.name, fallback_output)
            context.set_final_synthesis(fallback_output)
            context.mark_agent_error(self.name, e)
            context.complete_agent_execution(self.name, success=False)
            context.log_trace(self.name, input_data=outputs, output_data=str(e))

            return context

    async def _analyze_agent_outputs(
        self, query: str, outputs: Dict[str, Any], context: AgentContext
    ) -> Dict[str, Any]:
        """Analyze agent outputs to identify themes, conflicts, and synthesis opportunities."""
        analysis: Dict[str, Any] = {
            "themes": [],
            "conflicts": [],
            "complementary_insights": [],
            "gaps": [],
            "confidence_levels": {},
            "key_topics": [],
            "meta_insights": [],
        }

        if not self.llm:
            # Basic analysis without LLM
            analysis["themes"] = ["synthesis", "multi-agent", "integration"]
            analysis["key_topics"] = [query.split()[0] if query.split() else "general"]
            return analysis

        try:
            # Build analysis prompt
            analysis_prompt = self._build_analysis_prompt(query, outputs)

            # Get LLM analysis
            system_prompt = self._get_system_prompt()
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": analysis_prompt},
            ]
            if hasattr(self.llm, "ainvoke"):
                llm_response = await self.llm.ainvoke(messages)
            else:
                llm_response = await asyncio.to_thread(self.llm.generate, analysis_prompt)
            response_text = coerce_llm_text(llm_response)

            # Track token usage for analysis (first LLM call)
            if (
                hasattr(llm_response, "tokens_used")
                and llm_response.tokens_used is not None
            ):
                # Use detailed token breakdown if available
                input_tokens = getattr(llm_response, "input_tokens", None) or 0
                output_tokens = getattr(llm_response, "output_tokens", None) or 0
                total_tokens = llm_response.tokens_used

                # For synthesis, we accumulate token usage across multiple LLM calls
                existing_usage = context.get_agent_token_usage(self.name)

                context.add_agent_token_usage(
                    agent_name=self.name,
                    input_tokens=existing_usage["input_tokens"] + input_tokens,
                    output_tokens=existing_usage["output_tokens"] + output_tokens,
                    total_tokens=existing_usage["total_tokens"] + total_tokens,
                )

                logger.debug(
                    f"[{self.name}] Analysis token usage - "
                    f"input: {input_tokens}, output: {output_tokens}, total: {total_tokens}"
                )

            # Parse analysis response
            analysis = self._parse_analysis_response(response_text)

            logger.debug(f"[{self.name}] Completed thematic analysis")
            return analysis

        except Exception as e:
            logger.error(f"[{self.name}] Analysis failed: {e}")
            return analysis  # Return default analysis

    def _resolved_model_name(self) -> str:
        svc = self.structured_service
        return (
                (getattr(svc, "resolved_model_name", None) or "")
                or (getattr(svc, "model_name", None) or "")
                or (getattr(svc, "model", None) or "")
                or ""
        )

    async def _run_structured(
            self, query: str, outputs: Dict[str, Any], context: AgentContext
    ) -> str:
        """
        Run with structured output using LangChain service.

        This method performs the entire synthesis process using structured output,
        ensuring content pollution prevention and consistent formatting.

        IMPORTANT:
        - Some models/services can't reliably do JSON schema structured output.
        - In those cases we fall back to the same "traditional" path used in run().
        """
        import time

        start_time = time.time()

        if not self.structured_service:
            raise ValueError("Structured service not available")

        # ------------------------------------------------------------------
        # Robust pooled/ollama/llama guard (prevents json_schema calls)
        # ------------------------------------------------------------------
        resolved = (self._resolved_model_name() or "").lower()

        base_url = (getattr(self.structured_service, "base_url", "") or "").lower()
        is_ollama = ("11434" in base_url) or ("ollama" in base_url)
        is_llama = "llama" in resolved
        is_pooled = resolved in ("pooled", "pool")

        if is_llama or is_ollama or is_pooled:
            self.logger.info(
                f"[{self.name}] Disabling structured output for resolved_model='{resolved}' base_url='{base_url}'"
            )

            # Fall back immediately using the existing traditional logic.
            analysis: Dict[str, Any] = {}
            # If you want thematic analysis in fallback, enable this:
            # analysis = await self._analyze_agent_outputs(query, outputs, context)

            if self.llm:
                synthesis_result = await self._llm_powered_synthesis(
                    query, outputs, analysis, context
                )
            else:
                synthesis_result = await self._fallback_synthesis(query, outputs, context)

            return await self._format_final_output(query, synthesis_result, analysis)

        # ------------------------------------------------------------------
        # Structured output path
        # ------------------------------------------------------------------
        try:
            system_prompt = self._get_system_prompt()

            unique = self._dedupe_agent_outputs(outputs)
            outputs_text = "\n\n".join(
                [f"### {key.upper()} OUTPUT:\n{text}" for key, text in unique.items()]
            )
            contributing_agents = list(unique.keys())

            # Keep analysis defined; optionally enable the analysis call.
            analysis: Dict[str, Any] = {}
            # analysis = await self._analyze_agent_outputs(query, outputs, context)

            prompt = f"""Original Query: {query}

    Agent Outputs:
    {outputs_text}

    Contributing Agents: {", ".join(contributing_agents)}
    Themes Identified: {", ".join(analysis.get("themes", [])[:5])}
    Key Topics: {", ".join(analysis.get("key_topics", [])[:10])}
    Conflicts Found: {", ".join(analysis.get("conflicts", ["None"])[:5])}
    Complementary Insights: {", ".join(analysis.get("complementary_insights", [])[:10])}
    Knowledge Gaps: {", ".join(analysis.get("gaps", [])[:8])}
    Meta Insights: {", ".join(analysis.get("meta_insights", [])[:5])}

    Please provide a comprehensive synthesis according to the system instructions.
    Focus on the synthesized content only - do not describe your synthesis process.
    You may set word_count, but it will be computed server-side for accuracy.
    The contributing_agents field should list: {", ".join(contributing_agents)}"""

            from OSSS.ai.services.langchain_service import StructuredOutputResult

            result = await self.structured_service.get_structured_output(
                prompt=prompt,
                output_class=SynthesisOutput,
                system_prompt=system_prompt,
                max_retries=3,
            )

            if isinstance(result, SynthesisOutput):
                structured_result = result
            elif isinstance(result, StructuredOutputResult):
                parsed_result = result.parsed
                if not isinstance(parsed_result, SynthesisOutput):
                    raise ValueError(
                        f"Expected SynthesisOutput, got {type(parsed_result)}"
                    )
                structured_result = parsed_result
            else:
                raise ValueError(f"Unexpected result type: {type(result)}")

            # Server-calculated timing + word count (deterministic)
            processing_time_ms = (time.time() - start_time) * 1000
            if structured_result.processing_time_ms is None:
                structured_result = structured_result.model_copy(
                    update={"processing_time_ms": processing_time_ms}
                )
                logger.info(
                    f"[{self.name}] Injected server-calculated processing_time_ms: {processing_time_ms:.1f}ms"
                )

            computed_word_count = self._compute_word_count(structured_result.final_synthesis)
            structured_result = structured_result.model_copy(
                update={"word_count": computed_word_count}
            )
            logger.info(
                f"[{self.name}] Injected server-calculated word_count: {computed_word_count}"
            )

            # Store structured output for orchestrator/API to prefer
            context.execution_state.setdefault("structured_outputs", {})
            context.execution_state["structured_outputs"][self.name] = structured_result.model_dump()

            logger.info(
                f"[{self.name}] Structured output successful - "
                f"processing_time: {processing_time_ms:.1f}ms, "
                f"themes: {len(structured_result.key_themes)}, "
                f"word_count: {structured_result.word_count}"
            )

            return await self._format_structured_output(query, structured_result, analysis)

        except Exception as e:
            # If structured fails, fall back instead of raising (prevents emergency synthesis).
            self.logger.warning(f"[{self.name}] Structured failed, falling back: {e}")

            analysis: Dict[str, Any] = {}
            # analysis = await self._analyze_agent_outputs(query, outputs, context)

            if self.llm:
                synthesis_result = await self._llm_powered_synthesis(
                    query, outputs, analysis, context
                )
            else:
                synthesis_result = await self._fallback_synthesis(query, outputs, context)

            return await self._format_final_output(query, synthesis_result, analysis)

    async def _format_structured_output(
        self, query: str, structured_result: SynthesisOutput, analysis: Dict[str, Any]
    ) -> str:
        """Format the structured output into the final synthesis text."""
        formatted_parts = [
            f"# Comprehensive Analysis: {query}\n",
        ]

        # Add topic summary
        if structured_result.topics_extracted:
            formatted_parts.append(
                f"**Key Topics:** {', '.join(structured_result.topics_extracted[:5])}\n"
            )

        # Add theme overview
        if structured_result.key_themes:
            theme_names = [
                theme.theme_name for theme in structured_result.key_themes[:3]
            ]
            formatted_parts.append(f"**Primary Themes:** {', '.join(theme_names)}\n")

        # Add the main synthesis content
        formatted_parts.append("## Synthesis\n")
        formatted_parts.append(structured_result.final_synthesis)

        # Add meta-insights if available
        if structured_result.meta_insights:
            formatted_parts.append("\n## Meta-Insights\n")
            for insight in structured_result.meta_insights[:3]:
                formatted_parts.append(f"- {insight}")

        return "\n".join(formatted_parts)

    async def _llm_powered_synthesis(
        self,
        query: str,
        outputs: Dict[str, Any],
        analysis: Dict[str, Any],
        context: AgentContext,
    ) -> str:
        """Perform sophisticated LLM-powered synthesis."""
        try:
            # Build comprehensive synthesis prompt
            synthesis_prompt = self._build_synthesis_prompt(query, outputs, analysis)

            # Get LLM synthesis
            if not self.llm:
                return await self._fallback_synthesis(query, outputs, context)

            llm_response = await asyncio.to_thread(self.llm.generate, synthesis_prompt)
            synthesis_text = coerce_llm_text(llm_response)

            # Track token usage for synthesis (second LLM call - accumulate)
            if (
                hasattr(llm_response, "tokens_used")
                and llm_response.tokens_used is not None
            ):
                # Use detailed token breakdown if available
                input_tokens = getattr(llm_response, "input_tokens", None) or 0
                output_tokens = getattr(llm_response, "output_tokens", None) or 0
                total_tokens = llm_response.tokens_used

                # Accumulate with existing usage from analysis call
                existing_usage = context.get_agent_token_usage(self.name)

                context.add_agent_token_usage(
                    agent_name=self.name,
                    input_tokens=existing_usage["input_tokens"] + input_tokens,
                    output_tokens=existing_usage["output_tokens"] + output_tokens,
                    total_tokens=existing_usage["total_tokens"] + total_tokens,
                )

                logger.debug(
                    f"[{self.name}] Synthesis token usage - "
                    f"input: {input_tokens}, output: {output_tokens}, total: {total_tokens}. "
                    f"Total accumulated: {existing_usage['total_tokens'] + total_tokens}"
                )

            logger.debug(
                f"[{self.name}] LLM synthesis completed: {len(synthesis_text)} characters"
            )
            return synthesis_text

        except Exception as e:
            logger.error(f"[{self.name}] LLM synthesis failed: {e}")
            return await self._fallback_synthesis(query, outputs, context)

    async def _fallback_synthesis(
        self, query: str, outputs: Dict[str, Any], context: AgentContext
    ) -> str:
        """Create fallback synthesis when LLM is unavailable."""
        logger.info(f"[{self.name}] Using fallback synthesis")

        synthesis_parts = [
            f"# Synthesis for: {query}\n",
            "## Integrated Analysis\n",
            "The following synthesis combines insights from multiple analytical agents:\n",
        ]

        # Add each agent's contribution
        for agent_name, output in outputs.items():
            if agent_name != self.name:  # Don't include our own output
                synthesis_parts.append(f"### {agent_name} Analysis")
                synthesis_parts.append(self._stringify_agent_output(output))
                synthesis_parts.append("")

        # Add basic conclusion
        synthesis_parts.extend(
            [
                "## Summary",
                f"This synthesis integrates perspectives from {len(outputs)} agents to provide comprehensive analysis of: {query}",
            ]
        )

        return "\n".join(synthesis_parts)

    async def _format_final_output(
        self, query: str, synthesis_result: str, analysis: Dict[str, Any]
    ) -> str:
        """Format the final synthesis output with metadata and structure."""
        # Extract key elements for formatting
        themes = analysis.get("themes", [])
        key_topics = analysis.get("key_topics", [])

        formatted_parts = [
            f"# Comprehensive Analysis: {query}\n",
        ]

        # Add topic summary if available
        if key_topics:
            formatted_parts.append(f"**Key Topics:** {', '.join(key_topics[:5])}\n")

        # Add theme overview if available
        if themes:
            formatted_parts.append(f"**Primary Themes:** {', '.join(themes[:3])}\n")

        # Add the main synthesis content
        formatted_parts.append("## Synthesis\n")
        formatted_parts.append(synthesis_result)

        # Add meta-insights if available
        meta_insights = analysis.get("meta_insights", [])
        if meta_insights:
            formatted_parts.append("\n## Meta-Insights\n")
            for insight in meta_insights[:3]:
                formatted_parts.append(f"- {insight}")

        return "\n".join(formatted_parts)

    async def _create_emergency_fallback(
            self, query: str, outputs: Dict[str, Any]
    ) -> str:
        """Create emergency fallback when all other synthesis methods fail."""
        logger.warning(f"[{self.name}] Using emergency fallback synthesis")

        fallback_parts = [
            f"# Emergency Synthesis: {query}\n",
            "## Agent Outputs\n",
            "*Note: This is a basic concatenation due to synthesis system failure.*\n",
        ]

        for agent, output in outputs.items():
            if agent == self.name:
                continue

            fallback_parts.append(f"### {agent}")

            text = self._stringify_agent_output(output)
            if len(text) > 500:
                text = text[:500] + "..."
            fallback_parts.append(text)

            fallback_parts.append("")

        return "\n".join(fallback_parts)

    def _build_analysis_prompt(self, query: str, outputs: Dict[str, Any]) -> str:
        """Build prompt for thematic analysis of agent outputs."""
        unique = self._dedupe_agent_outputs(outputs)

        outputs_text = "\n\n".join(
            [f"### {key.upper()} OUTPUT:\n{text}" for key, text in unique.items()]
        )

        # Try to use composed prompt from PromptComposer first
        if self._composed_prompt:
            analysis_template = self._composed_prompt.get_template("analysis_prompt")
            if analysis_template:
                try:
                    formatted_prompt: str = analysis_template.format(
                        query=query, outputs_text=outputs_text
                    )
                    return formatted_prompt
                except Exception as e:
                    logger.debug(
                        f"[{self.name}] Failed to use composed analysis prompt: {e}"
                    )

        # Try to load prompt template from prompts.py
        try:
            from OSSS.ai.agents.synthesis.prompts import (
                SYNTHESIS_ANALYSIS_PROMPT_TEMPLATE,
            )

            return SYNTHESIS_ANALYSIS_PROMPT_TEMPLATE.format(
                query=query, outputs_text=outputs_text
            )
        except ImportError:
            # Fallback to embedded prompt
            return f"""As an expert analyst, perform thematic analysis of multiple agent outputs for synthesis.

ORIGINAL QUERY: {query}

AGENT OUTPUTS:
{outputs_text}

Analyze the outputs and provide a structured analysis in the following format:

THEMES: [list 3-5 main themes across all outputs]
CONFLICTS: [identify any contradictions or disagreements between agents]
COMPLEMENTARY: [highlight insights that build on each other]
GAPS: [note any important aspects not covered]
TOPICS: [extract 5-10 key topics/concepts mentioned]
META_INSIGHTS: [provide 2-3 higher-level insights about the analysis process itself]

Provide your analysis in the exact format above."""

    def _parse_analysis_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the LLM analysis response into structured data."""
        analysis: Dict[str, Any] = {
            "themes": [],
            "conflicts": [],
            "complementary_insights": [],
            "gaps": [],
            "key_topics": [],
            "meta_insights": [],
        }

        try:
            lines = response_text.strip().split("\n")
            current_section = None

            for line in lines:
                line = line.strip()
                if line.startswith("THEMES:"):
                    current_section = "themes"
                    content = line.replace("THEMES:", "").strip()
                    if content:
                        analysis["themes"] = [t.strip() for t in content.split(",")]
                elif line.startswith("CONFLICTS:"):
                    current_section = "conflicts"
                    content = line.replace("CONFLICTS:", "").strip()
                    if content:
                        analysis["conflicts"] = [c.strip() for c in content.split(",")]
                elif line.startswith("COMPLEMENTARY:"):
                    current_section = "complementary_insights"
                    content = line.replace("COMPLEMENTARY:", "").strip()
                    if content:
                        analysis["complementary_insights"] = [
                            c.strip() for c in content.split(",")
                        ]
                elif line.startswith("GAPS:"):
                    current_section = "gaps"
                    content = line.replace("GAPS:", "").strip()
                    if content:
                        analysis["gaps"] = [g.strip() for g in content.split(",")]
                elif line.startswith("TOPICS:"):
                    current_section = "key_topics"
                    content = line.replace("TOPICS:", "").strip()
                    if content:
                        analysis["key_topics"] = [t.strip() for t in content.split(",")]
                elif line.startswith("META_INSIGHTS:"):
                    current_section = "meta_insights"
                    content = line.replace("META_INSIGHTS:", "").strip()
                    if content:
                        analysis["meta_insights"] = [
                            m.strip() for m in content.split(",")
                        ]
                elif (
                    line
                    and current_section
                    and not line.startswith(
                        tuple(
                            [
                                "THEMES:",
                                "CONFLICTS:",
                                "COMPLEMENTARY:",
                                "GAPS:",
                                "TOPICS:",
                                "META_INSIGHTS:",
                            ]
                        )
                    )
                ):
                    # Continue parsing multi-line content
                    if current_section in analysis:
                        if isinstance(analysis[current_section], list):
                            analysis[current_section].append(line)

            return analysis

        except Exception as e:
            logger.error(f"[{self.name}] Failed to parse analysis response: {e}")
            return analysis

    def _build_synthesis_prompt(
        self, query: str, outputs: Dict[str, Any], analysis: Dict[str, Any]
    ) -> str:
        """Build comprehensive synthesis prompt."""
        unique = self._dedupe_agent_outputs(outputs)

        outputs_text = "\n\n".join(
            [f"### {key.upper()}:\n{text}" for key, text in unique.items()]
        )

        themes_text = ", ".join(analysis.get("themes", []))
        conflicts_text = ", ".join(analysis.get("conflicts", ["None identified"]))
        topics_text = ", ".join(analysis.get("key_topics", []))

        # Try to use composed prompt from PromptComposer first
        if self._composed_prompt:
            synthesis_template = self._composed_prompt.get_template("synthesis_prompt")
            if synthesis_template:
                try:
                    formatted_prompt: str = synthesis_template.format(
                        query=query,
                        themes_text=themes_text,
                        topics_text=topics_text,
                        conflicts_text=conflicts_text,
                        outputs_text=outputs_text,
                    )
                    return formatted_prompt
                except Exception as e:
                    logger.debug(
                        f"[{self.name}] Failed to use composed synthesis prompt: {e}"
                    )

        # Try to load prompt template from prompts.py
        try:
            from OSSS.ai.agents.synthesis.prompts import (
                SYNTHESIS_COMPOSITION_PROMPT_TEMPLATE,
            )

            return SYNTHESIS_COMPOSITION_PROMPT_TEMPLATE.format(
                query=query,
                themes_text=themes_text,
                topics_text=topics_text,
                conflicts_text=conflicts_text,
                outputs_text=outputs_text,
            )
        except ImportError:
            # Fallback to embedded prompt
            return f"""As a knowledge synthesis expert, create a comprehensive, wiki-ready synthesis of multiple expert analyses.

ORIGINAL QUERY: {query}

IDENTIFIED THEMES: {themes_text}
KEY TOPICS: {topics_text}
CONFLICTS TO RESOLVE: {conflicts_text}

EXPERT ANALYSES:
{outputs_text}

Create a sophisticated synthesis that:
1. Integrates all perspectives into a coherent narrative
2. Resolves any conflicts or contradictions intelligently
3. Highlights emergent insights from combining analyses
4. Provides a definitive, comprehensive answer to the original query
5. Uses clear, wiki-style formatting with appropriate headers
6. Includes nuanced conclusions that acknowledge complexity

COMPREHENSIVE SYNTHESIS:"""

    def define_node_metadata(self) -> Dict[str, Any]:
        """
        Define LangGraph-specific metadata for the Synthesis agent.

        Returns
        -------
        Dict[str, Any]
            Node metadata including type, dependencies, schemas, and routing logic
        """
        return {
            "node_type": NodeType.AGGREGATOR,
            "dependencies": ["refiner", "critic", "historian"],  # Waits for all agents
            "description": "Synthesizes outputs from all agents into a comprehensive summary",
            "inputs": [
                NodeInputSchema(
                    name="context",
                    description="Agent context containing all agent outputs to synthesize",
                    required=True,
                    type_hint="AgentContext",
                )
            ],
            "outputs": [
                NodeOutputSchema(
                    name="context",
                    description="Final context with synthesized summary of all agent outputs",
                    type_hint="AgentContext",
                )
            ],
            "tags": ["synthesis", "agent", "aggregator", "terminator", "final"],
        }