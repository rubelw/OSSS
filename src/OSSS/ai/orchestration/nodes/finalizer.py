@node_metrics
async def finalizer_node(state: OSSSState, runtime: Runtime[OSSSContext]) -> Dict[str, Any]:
    """
    Final canonical output normalizer for UI consumption.
    This node MUST always run last.
    """
    now = _now_iso()

    agent_outputs = state.get("agent_outputs", {})
    meta = state.get("agent_output_meta", {}) or {}

    # 1️⃣ Choose message source (priority order)
    message = ""
    sources = []
    agent_used = None

    if "final_response" in agent_outputs:
        message = agent_outputs["final_response"].get("message", "")
        sources = agent_outputs["final_response"].get("sources", [])
        agent_used = "final_response"

    elif "answer_search" in agent_outputs:
        message = agent_outputs["answer_search"].get("answer_text", "")
        sources = agent_outputs["answer_search"].get("sources", [])
        agent_used = "answer_search"

    elif "synthesis" in agent_outputs:
        message = agent_outputs["synthesis"]
        agent_used = "synthesis"

    elif "guard" in agent_outputs and not agent_outputs["guard"].get("allowed", True):
        message = agent_outputs["guard"].get("message", "Request blocked.")
        agent_used = "guard"

    # 2️⃣ Query profile passthrough
    qp = meta.get("_query_profile", {})

    ui_payload = {
        "message": message or "(No response generated)",
        "sources": sources or [],
        "status": "ok",
        "agent": agent_used,
        "intent": qp.get("intent"),
        "sub_intent": qp.get("sub_intent"),
        "tone": qp.get("tone"),
        "timestamp": now,
    }

    state["ui"] = ui_payload

    return {
        "ui": ui_payload,
        "finalized": True,
    }
