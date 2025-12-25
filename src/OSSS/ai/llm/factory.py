# llm/factory.py
import os
from typing import Optional, Dict, Any, cast

from OSSS.ai.llm.llm_interface import LLMInterface
from OSSS.ai.llm.openai import OpenAIChatLLM
from OSSS.ai.llm.stub import StubLLM
from OSSS.ai.config.openai_config import OpenAIConfig
from OSSS.ai.llm.provider_enum import LLMProvider

from OSSS.ai.config.llm_config import load_llm_config
from OSSS.ai.observability import get_logger

log = get_logger("OSSS.ai.llm.factory")


def _normalize_openai_base_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not url:
        return url
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url


def _assert_not_self_gateway(url: str, *, agent: str) -> None:
    bad = {
        "http://app:8000/v1",
        "http://app:8000",
        "http://localhost:8000/v1",
        "http://localhost:8000",
        "http://127.0.0.1:8000/v1",
        "http://127.0.0.1:8000",
    }
    if url.rstrip("/") in {b.rstrip("/") for b in bad}:
        raise ValueError(
            f"{agent}_llm provider=gateway is configured to {url!r}, which looks like the OSSS API itself. "
            f"Set OSSS_AI_GATEWAY_BASE_URL (or per-agent base_url) to your *actual* gateway."
        )


def _get_llm_agent_defaults(llm_cfg: Dict[str, Any], agent: str) -> Dict[str, Any]:
    agents = llm_cfg.get("agents")
    if not isinstance(agents, dict):
        return {}
    agent_defaults = agents.get(agent, {})
    return agent_defaults if isinstance(agent_defaults, dict) else {}


def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(v)


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


class LLMFactory:
    @staticmethod
    def create(
        llm_name: Optional[LLMProvider] = None,
        *,
        agent_name: Optional[str] = None,
        execution_config: Optional[Dict[str, Any]] = None,
    ) -> LLMInterface:
        execution_config = execution_config or {}
        if not isinstance(execution_config, dict):
            execution_config = {}

        llm_cfg = load_llm_config()
        if not isinstance(llm_cfg, dict):
            llm_cfg = {}
        llm_cfg = cast(Dict[str, Any], llm_cfg)

        agent = (agent_name or "").strip().lower()

        # ✅ include final so request-level RAG flags can affect it
        if agent in {"critic", "refiner", "historian", "synthesis", "final"}:
            cfg_key = f"{agent}_llm"
            agent_cfg = execution_config.get(cfg_key, {})
            if not isinstance(agent_cfg, dict):
                agent_cfg = {}

            agent_defaults = _get_llm_agent_defaults(llm_cfg, agent)
            provider_cfg = agent_defaults.get("provider")
            model_cfg = agent_defaults.get("model")
            base_url_cfg = agent_defaults.get("base_url")
            extra_body_cfg = agent_defaults.get("extra_body")

            provider_env = os.getenv(f"OSSS_{agent.upper()}_LLM_PROVIDER")

            default_provider = "ollama" if agent == "critic" else "gateway"

            provider_raw = (
                (agent_cfg.get("provider") or provider_env or provider_cfg or default_provider)
                .strip()
                .lower()
            )

            # Model defaults
            if agent == "critic":
                default_model = os.getenv("OSSS_CRITIC_OLLAMA_MODEL") or "qwen2.5:1.5b-instruct"
            elif agent == "refiner":
                default_model = os.getenv("OSSS_REFINER_MODEL") or "llama3.1:latest"
            elif agent == "historian":
                default_model = os.getenv("OSSS_HISTORIAN_MODEL") or "llama3.1:latest"
            elif agent == "final":
                default_model = os.getenv("OSSS_FINAL_MODEL") or "llama3.1:latest"
            else:
                default_model = os.getenv("OSSS_SYNTHESIS_MODEL") or "llama3.1:latest"

            model = agent_cfg.get("model") or model_cfg or default_model

            log.info(
                "[llm_factory] resolved agent llm",
                agent=agent,
                provider=provider_raw,
                model=model,
                provider_env=os.getenv(f"OSSS_{agent.upper()}_LLM_PROVIDER"),
                has_agent_cfg=bool(agent_cfg),
                agent_cfg_keys=list(agent_cfg.keys()),
                llm_cfg_loaded=bool(llm_cfg),
                llm_cfg_agents_keys=list((llm_cfg.get("agents") or {}).keys())
                if isinstance(llm_cfg.get("agents"), dict)
                else None,
                llm_cfg_agent_defaults=agent_defaults,
            )

            # --------------------------------------------------------------
            # extra_body precedence:
            #   1) llm.json agent_defaults.extra_body
            #   2) execution_config[agent_key].extra_body
            #   3) env OSSS_<AGENT>_USE_RAG (optional)
            #   4) request-level execution_config.use_rag/top_k  ✅ MUST WIN
            # --------------------------------------------------------------
            extra_body: Dict[str, Any] = {}

            if isinstance(extra_body_cfg, dict):
                extra_body.update(extra_body_cfg)

            extra_body_req = agent_cfg.get("extra_body")
            if isinstance(extra_body_req, dict):
                extra_body.update(extra_body_req)

            # Default: only answer-producing agents get RAG by default
            # (still overridden by env/request-level)
            rag_default = agent in {"final", "synthesis"}
            extra_body.setdefault("use_rag", rag_default)

            # Env override (still overridden by request-level)
            use_rag_env = os.getenv(f"OSSS_{agent.upper()}_USE_RAG")
            if use_rag_env is not None:
                extra_body["use_rag"] = use_rag_env.strip().lower() in {"1", "true", "yes", "y"}

            # ✅ Request-level override (THE FIX)
            use_rag_req = execution_config.get("use_rag")
            top_k_req = execution_config.get("top_k")

            # Restrict request-level RAG enablement to these agents
            rag_enabled_agents = {"final", "synthesis"}

            if use_rag_req is not None:
                want_rag = _truthy(use_rag_req)
                extra_body["use_rag"] = bool(want_rag and (agent in rag_enabled_agents))
                if not extra_body["use_rag"]:
                    extra_body.pop("top_k", None)

            if top_k_req is not None:
                if _truthy(extra_body.get("use_rag")):
                    tk = _safe_int(top_k_req)
                    if tk is not None and tk > 0:
                        extra_body["top_k"] = tk

            log.debug(
                "[llm_factory] resolved extra_body",
                agent=agent,
                use_rag=extra_body.get("use_rag"),
                top_k=extra_body.get("top_k"),
                extra_body_keys=list(extra_body.keys()),
            )

            # --------------------------------------------------------------
            # Providers
            # --------------------------------------------------------------
            if provider_raw in {"gateway", "rag", "ai_gateway"}:
                base_url_raw = (
                    agent_cfg.get("base_url")
                    or os.getenv("OSSS_AI_GATEWAY_BASE_URL")
                    or base_url_cfg
                )
                if not base_url_raw:
                    raise ValueError(
                        f"{agent}_llm provider=gateway requires OSSS_AI_GATEWAY_BASE_URL "
                        f"(or execution_config['{agent}_llm']['base_url']). Refusing to default to app:8000."
                    )

                base_url = _normalize_openai_base_url(str(base_url_raw))
                _assert_not_self_gateway(base_url, agent=agent)

                return OpenAIChatLLM(
                    api_key=agent_cfg.get("api_key")
                    or os.getenv("OSSS_AI_GATEWAY_API_KEY")
                    or "gateway",
                    model=model,
                    base_url=base_url,
                    extra_body=extra_body,
                )

            if provider_raw == "ollama":
                ollama_global = llm_cfg.get("ollama", {})
                if not isinstance(ollama_global, dict):
                    ollama_global = {}

                base_url_raw = (
                    agent_cfg.get("base_url")
                    or os.getenv("OSSS_OLLAMA_BASE_URL")
                    or base_url_cfg
                    or ollama_global.get("base_url")
                    or "http://host.containers.internal:11434"
                )
                base_url = _normalize_openai_base_url(str(base_url_raw))

                return OpenAIChatLLM(
                    api_key=agent_cfg.get("api_key")
                    or os.getenv("OSSS_OLLAMA_API_KEY")
                    or "ollama",
                    model=model,
                    base_url=base_url,
                    extra_body=extra_body,
                )

            if provider_raw == "openai":
                config = OpenAIConfig.load()
                model = agent_cfg.get("model") or model_cfg or config.model
                return OpenAIChatLLM(
                    api_key=config.api_key,
                    model=model,
                    base_url=config.base_url,
                    extra_body=extra_body,
                )

            if provider_raw == "stub":
                return StubLLM()

            raise ValueError(f"Unsupported {agent} provider: {provider_raw}")

        # ------------------------------------------------------------------
        # Default factory behavior (existing logic)
        # ------------------------------------------------------------------
        llm_name = llm_name or LLMProvider(os.getenv("OSSS_LLM", "openai").lower())

        if llm_name == LLMProvider.OPENAI:
            config = OpenAIConfig.load()
            return OpenAIChatLLM(
                api_key=config.api_key,
                model=config.model,
                base_url=config.base_url,
            )
        elif llm_name == LLMProvider.STUB:
            return StubLLM()
        else:
            raise ValueError(f"Unsupported LLM type: {llm_name}")
