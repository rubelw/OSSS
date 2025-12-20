# OSSS/ai/langgraph_backend/spec_builders/guarded.py
def build_guarded_spec(plan: ExecutionPlan, node_functions: dict[str, Callable]) -> GraphSpec:
    # enforce guard pipeline, build conditional edges, etc.
