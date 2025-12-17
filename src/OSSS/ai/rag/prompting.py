from typing import List, Dict
from .retriever import RetrievedChunk

def build_rag_messages(
    user_messages: List[Dict[str, str]],
    chunks: List[RetrievedChunk],
) -> List[Dict[str, str]]:
    # Pull the latest user question (simple approach)
    question = ""
    for m in reversed(user_messages):
        if m.get("role") == "user":
            question = m.get("content", "")
            break

    context_blocks = []
    for i, c in enumerate(chunks, start=1):
        context_blocks.append(
            f"[{i}] source={c.source} score={c.score:.3f}\n{c.text}"
        )

    system = {
        "role": "system",
        "content": (
            "You are a helpful assistant. "
            "Use the provided context to answer. "
            "If the context is insufficient, say so. "
            "When you use a fact from context, cite it like [1], [2], etc."
        ),
    }

    context_msg = {
        "role": "system",
        "content": "CONTEXT:\n\n" + ("\n\n---\n\n".join(context_blocks) if context_blocks else "(no context)"),
    }

    # Keep conversation, but ensure grounding context is included
    return [system, context_msg, *user_messages]
