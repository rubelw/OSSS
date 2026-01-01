from __future__ import annotations

from typing import List, TYPE_CHECKING, Any
import json

if TYPE_CHECKING:
    # Optional import to avoid circular dependencies at runtime.
    # Adjust the path if your FinalConfig lives somewhere else.
    from OSSS.ai.agents.final.config import FinalConfig


FINAL_USER_PROMPT_TEMPLATE = """RAG_SNIPPET_PRESENT: {rag_present}

USER QUESTION:
{user_question}
{refiner_block}

RAG CONTEXT:
{rag_section}{data_query_section}

Now produce the final answer for the end user.
"""


FINAL_SYSTEM_PROMPT = """You are the FINAL agent for OSSS, the last step in a multi-agent pipeline.

Your responsibilities:
1. Read the end-user question.
2. Use any retrieved context (RAG) that has been provided to you.
3. Produce a concise, clear, well-structured answer suitable for the user.
4. Respect all safety and factuality constraints described below.

You will see a field called RAG_SNIPPET_PRESENT in the user message:
- If RAG_SNIPPET_PRESENT is "True", then the RAG CONTEXT section
  contains context that you MAY rely on as long as you quote or summarize it accurately.
- If RAG_SNIPPET_PRESENT is "False", then no reliable retrieved context is available.
  In that case you MUST NOT claim that you used retrieved documents or context.

Structured data-query mode (ABSOLUTE RULES):
- If the USER QUESTION begins with the token "query " (any casing):
  - Treat this as a structured data query.
  - Ignore any "REFINER CONTEXT" section if present.
  - Ignore the RAG CONTEXT section entirely.
  - If any markdown table(s) are present in the prompt (for example from a data_query
    agent), you MUST respond by outputting ONLY those table(s), unchanged.
  - You MUST NOT add:
    - headings or titles,
    - narrative summaries,
    - bullet-point explanations,
    - or any other prose above or below the table(s).
  - The entire assistant reply in this mode should be just the markdown table content.

General rules:
- Prefer bullet points and short sections when it improves readability
  (except in structured data-query mode, as described above).
- Be direct and avoid unnecessary meta-commentary.
- If the question is ambiguous, briefly explain the ambiguity and answer the
  most likely interpretation while clearly labeling assumptions.
- If you lack enough information, say you don’t know rather than guessing.
- Do not reference internal implementation details of the system.

ROLE-IDENTITY SAFETY RULES (CRITICAL):
- Some questions ask who currently holds a real-world role, such as:
  superintendent, principal, mayor, director, president, CEO, head of school,
  chancellor, or dean.
- If the question is about who currently holds a real-world role, you MUST NOT
  invent or guess a person’s name under any circumstances.
- If the retrieved context (RAG) does not clearly and explicitly name the person
  who holds that role, you MUST answer that you don’t know and recommend that the
  user consult an official source (district, school, or government website).
- When RAG_SNIPPET_PRESENT is "False", you are not allowed to answer
  such role-identity questions with any specific name at all.

RAG usage:
- Only treat text in the RAG CONTEXT section as retrieved context.
- Do not fabricate citations or claim you saw information that is not actually
  present in the RAG section or the user question.
- If the RAG section says no relevant context was found, behave as if you have
  no external documents and answer based only on the question and your general
  knowledge, still obeying the role-identity rules above.

Your output:
- Should read as a polished, user-facing answer, except in structured data-query
  mode where it must be just the markdown table(s).
- Should not expose internal flags or implementation details (like how agents
  are orchestrated).
- Must not mention that you are the "FINAL" agent or describe pipeline internals.
"""


def _normalize_rag_metadata(meta: Any) -> str:
    """
    Kept for backward compatibility, but NOTE:
    - We no longer inject RAG or data_query metadata into the LLM prompt
      to reduce token usage and improve latency.
    - Callers may still use this helper for logging or debugging outside of prompts.

    Accepts:
    - str: returned as-is (stripped)
    - dict / list: JSON-dumps with small indentation
    - anything else: str(...)
    """
    if meta is None:
        return ""
    if isinstance(meta, str):
        return meta.strip()

    try:
        return json.dumps(meta, indent=2, sort_keys=True)
    except TypeError:
        return str(meta)


def build_final_prompt(
    user_question: str,
    refiner_text: str,
    rag_present: bool,
    rag_section: str,
    original_user_question: str | None = None,
    data_query_markdown: str | None = None,
    *,
    # Optional config + metadata; currently not injected into the prompt body
    # to keep token counts lower, but retained for API compatibility.
    config: "FinalConfig | None" = None,
    rag_metadata: Any | None = None,
    data_query_metadata: Any | None = None,
) -> str:
    """
    Build the user-facing prompt for the FinalAgent.

    Special case:
    - If the *original* user question begins with "query " (any casing), we treat it as a
      structured data query and:
        * DO NOT include the refiner block at all.
        * DO NOT include any RAG snippet (pretend RAG is absent), regardless of config.
    """
    # What we’ll display as "USER QUESTION:"
    uq = (user_question or "").strip() or "[missing user question]"

    # Use the *original* question, if available, to decide if this was a lexical query
    detector_text = (original_user_question or user_question or "").strip()
    detector_lower = detector_text.lower()
    is_structured_query = detector_lower.startswith("query ")

    # Normalize refiner text
    refiner_text = (refiner_text or "").strip()

    # ---- Refiner block -------------------------------------------------------
    if (
        refiner_text
        and refiner_text != uq
        and not is_structured_query
    ):
        lines: List[str] = [
            "",
            "REFINER CONTEXT (for disambiguation):",
            refiner_text,
        ]
        refiner_block = "\n".join(lines)
    else:
        refiner_block = ""

    # ---- RAG section ---------------------------------------------------------
    if is_structured_query:
        # Hard-disable RAG for structured lexical "query ..." requests
        rag_present_for_prompt = False
        rag_section_final = "No retrieved context provided."
    else:
        rag_present_for_prompt = bool(rag_present)
        rag_section_final = (rag_section or "").strip() or "No retrieved context provided."

    # ---- data_query tables block ---------------------------------------------
    dq = (data_query_markdown or "").strip()
    if dq:
        # Only include this section if we actually have tables to show
        data_query_section = f"\n\nDATA QUERY TABLES:\n{dq}"
    else:
        data_query_section = ""

    return FINAL_USER_PROMPT_TEMPLATE.format(
        rag_present=str(rag_present_for_prompt),
        user_question=uq,
        refiner_block=refiner_block,
        rag_section=rag_section_final,
        data_query_section=data_query_section,
    )
