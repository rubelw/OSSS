class PreflightRouter:
    def decide(self, exec_state: dict) -> dict:
        text = (exec_state.get("raw_user_text") or exec_state.get("user_question") or "").strip()
        low = text.lower()

        if low.startswith("query "):
            return {"entry_target": "data_query", "entry_locked": True, "entry_reason": "query_prefix"}

        # optionally include your existing DBQueryRouter heuristics:
        # if has_db_table etc...
        if self._looks_like_db_query(low, exec_state):
            return {"entry_target": "data_query", "entry_locked": True, "entry_reason": "db_query_heuristic"}

        return {"entry_target": None, "entry_locked": False, "entry_reason": "default"}

    def apply(self, exec_state: dict, decision: dict) -> None:
        if decision.get("entry_target"):
            exec_state["entry_target"] = decision["entry_target"]
        exec_state["entry_locked"] = bool(decision.get("entry_locked"))
        exec_state["entry_reason"] = decision.get("entry_reason") or ""
