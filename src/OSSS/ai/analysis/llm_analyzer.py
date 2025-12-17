# OSSS/ai/analysis/llm_analyzer.py
from __future__ import annotations

from typing import Any, Dict, Optional

from OSSS.ai.analysis.models import QueryProfile
from OSSS.ai.analysis.rules.types import RuleAction, RuleCategory, make_hit
from OSSS.ai.analysis.pipeline import analyze_query  # deterministic fallback

# Use whatever LLM wrapper you already have in OSSS
from OSSS.ai.llm.openai import OpenAIChatLLM
from OSSS.ai.config.openai_config import OpenAIConfig


async def analyze_query_with_llm(
    query: str,
    *,
    llm: Optional[OpenAIChatLLM] = None,
    fallback_to_rules: bool = True,
) -> QueryProfile:
    """
    LLM-based query analysis. Returns QueryProfile.

    If the LLM call fails, returns deterministic analyze_query(query) (optional).
    """
    q = (query or "").strip()
    if not q:
        return QueryProfile()

    if llm is None:
        cfg = OpenAIConfig.load()
        llm = OpenAIChatLLM(
            api_key=cfg.api_key,
            model=cfg.model,
            base_url=cfg.base_url,
        )

    try:
        # NOTE: implement your LLM call here. Pseudocode:
        # result = await llm.structured_chat_completion(schema=QueryProfile, prompt=...)
        #
        # If you don't have “structured output” helper, ask for JSON and parse.

        result_dict: Dict[str, Any] = await llm.classify_query_profile_json(q)  # <--- implement
        # Normalize into QueryProfile (pydantic will validate)
        prof = QueryProfile.model_validate(result_dict)

        # Ensure matched_rules are RuleHit objects (not dicts/strings)
        # If LLM returns empty, create minimal trace
        if not prof.matched_rules:
            prof.matched_rules = [
                make_hit(
                    rule="llm:query_profile:classified",
                    action=RuleAction.ROUTE,
                    category=RuleCategory.POLICY,
                    score=prof.sub_intent_confidence or prof.intent_confidence or 0.5,
                    note="LLM classified query profile",
                )
            ]

        return prof

    except Exception as e:
        if fallback_to_rules:
            prof = analyze_query(q)
            # add trace that LLM failed (still structured)
            prof.matched_rules.append(
                make_hit(
                    rule="llm:query_profile:error_fallback",
                    action=RuleAction.READ,
                    category=RuleCategory.POLICY,
                    score=0.0,
                    error=str(e),
                )
            )
            return prof
        return QueryProfile(
            matched_rules=[
                make_hit(
                    rule="llm:query_profile:error",
                    action=RuleAction.READ,
                    category=RuleCategory.POLICY,
                    score=0.0,
                    error=str(e),
                )
            ]
        )


async def analyze_agent_queries_with_llm(
    agent_queries: Dict[str, str],
    *,
    llm: Optional[OpenAIChatLLM] = None,
) -> Dict[str, QueryProfile]:
    """
    Analyze each agent query with the LLM and return per-agent QueryProfile.
    """
    results: Dict[str, QueryProfile] = {}
    for agent_name, q in agent_queries.items():
        results[agent_name] = await analyze_query_with_llm(q, llm=llm)
    return results
