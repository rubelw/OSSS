"""
System and user prompts for the FinalAgent.

This module contains the system and user-level prompt templates used by the
FinalAgent to turn multi-agent context + RAG snippets into a clean, end-user
answer, while enforcing strict role-identity and RAG usage rules.
"""

from __future__ import annotations

from typing import List

FINAL_USER_PROMPT_TEMPLATE = """RAG_SNIPPET_PRESENT: {rag_present}

USER QUESTION:
{user_question}{extra_blocks}

RETRIEVED CONTEXT (RAG):
{rag_section}

Now produce the final answer for the end user.
"""

FINAL_SYSTEM_PROMPT = """You are the FINAL agent for OSSS, the last step in a multi-agent pipeline.

Your responsibilities:
1. Read the end-user question.
2. Use any retrieved context (RAG) that has been provided to you.
3. Produce a concise, clear, well-structured answer suitable for the user.
4. Respect all safety and factuality constraints described below.

You will see a field called RAG_SNIPPET_PRESENT in the user message:
- If RAG_SNIPPET_PRESENT is "True", then the RETRIEVED CONTEXT (RAG) section
  contains context that you MAY rely on as long as you quote or summarize it accurately.
- If RAG_SNIPPET_PRESENT is "False", then no reliable retrieved context is available.
  In that case you MUST NOT claim that you used retrieved documents or context.

Structured data-query mode (ABSOLUTE RULES):
- If the USER QUESTION begins with the token "query " (any casing):
  - Treat this as a structured data query.
  - Ignore any "REFINER CONTEXT" section if present.
  - Ignore the RETRIEVED CONTEXT (RAG) section entirely.
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
- Only treat text in the RETRIEVED CONTEXT (RAG) section as retrieved context.
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


def build_final_prompt(
    user_question: str,
    refiner_text: str,
    rag_present: bool,
    rag_section: str,
    original_user_question: str | None = None,
    data_query_markdown: str | None = None,
) -> str:
    """
    Build the user-facing prompt for the FinalAgent.

    Special case:
    - If the *original* user question begins with "query " (any casing), we treat it as a
      structured data query and:
        * Show the original query (including "query ") as the USER QUESTION.
        * DO NOT include the refiner block at all.
        * DO NOT include any RAG snippet (pretend RAG is absent).
        * If data_query_markdown is provided, we include it as raw markdown tables
          so the FinalAgent can echo ONLY those tables back to the user.
    """
    # Visible USER QUESTION is always the original, if we have it
    if original_user_question and original_user_question.strip():
        uq = original_user_question.strip()
    else:
        uq = (user_question or "").strip() or "[missing user question]"

    # Use the same visible text to decide if this was a lexical "query ..." request
    detector_lower = uq.lower()
    is_structured_query = detector_lower.startswith("query ")

    # Normalize refiner text
    refiner_text = (refiner_text or "").strip()

    # ---- Refiner block -------------------------------------------------------
    if (
        refiner_text
        and refiner_text != uq
        and not is_structured_query
    ):
        refiner_block_lines: List[str] = [
            "",
            "REFINER CONTEXT (may help disambiguate / improve search terms):",
            refiner_text,
        ]
        refiner_block = "\n".join(refiner_block_lines)
    else:
        # For structured "query ..." we *always* omit refiner context.
        refiner_block = ""

    # ---- Data-query block ----------------------------------------------------
    dq = (data_query_markdown or "").strip()
    if dq:
        if is_structured_query:
            # In structured mode, we want the FinalAgent to see only the tables
            # as extra content, with no labels or prose around them.
            data_query_block = "\n\n" + dq
        else:
            # In non-structured mode, label the section so FINAL can weave it into prose.
            data_query_block = "\n\nDATA QUERY RESULTS (markdown tables):\n" + dq
    else:
        data_query_block = ""

    extra_blocks = refiner_block + data_query_block

    # ---- RAG section ---------------------------------------------------------
    if is_structured_query:
        # Hard-disable RAG for structured lexical "query ..." requests
        rag_present_for_prompt = False
        rag_section_final = "No retrieved context provided."
    else:
        rag_present_for_prompt = bool(rag_present)
        rag_section_final = (rag_section or "").strip() or "No retrieved context provided."

    return FINAL_USER_PROMPT_TEMPLATE.format(
        rag_present=str(rag_present_for_prompt),
        user_question=uq,
        extra_blocks=extra_blocks,
        rag_section=rag_section_final,
    )
