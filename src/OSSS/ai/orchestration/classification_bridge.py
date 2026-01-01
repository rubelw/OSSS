"""
Helpers for passing classifier outputs into the LangGraph orchestrator.

Goal:
- Give classifier / upstream HTTP layer a single, consistent way
  to attach classification results into the orchestrator config.
- Orchestrator then reads these from:

    * ``config["classifier"]`` (flat, legacy)
    * ``config["execution_state"]["classifier_profile"]``
    * ``config["execution_state"]["task_classification"]``
    * ``config["execution_state"]["cognitive_classification"]``
"""

from __future__ import annotations

from typing import Any, Dict, Optional


ClassifierProfile = Dict[str, Any]
TaskClassification = Dict[str, Any]
CognitiveClassification = Dict[str, Any]


def attach_classifier_to_config_inplace(
    config: Dict[str, Any],
    *,
    classifier_profile: Optional[ClassifierProfile] = None,
    task_classification: Optional[TaskClassification] = None,
    cognitive_classification: Optional[CognitiveClassification] = None,
) -> Dict[str, Any]:
    """
    Mutate ``config`` in-place to attach classifier outputs in a canonical way.

    This function:

    * Puts a flat ``config["classifier"]`` for legacy consumers.
    * Attaches a richer classifier profile into
      ``config["execution_state"]["classifier_profile"]``.
    * Mirrors task and cognitive classifications into
      ``config["execution_state"]["task_classification"]`` and
      ``config["execution_state"]["cognitive_classification"]``.

    Args:
        config: Orchestrator configuration dictionary to be mutated in-place.
        classifier_profile: Rich classifier profile (intent, domain, action, etc.).
        task_classification: Optional task-level classification details.
        cognitive_classification: Optional cognitive classification details.

    Returns:
        The same ``config`` dict for convenience.
    """
    if not isinstance(config, dict):
        raise TypeError("config must be a dict")

    exec_state = config.setdefault("execution_state", {})
    if not isinstance(exec_state, dict):
        exec_state = {}
        config["execution_state"] = exec_state

    # ---- Classifier profile (rich) ----
    if classifier_profile:
        if not isinstance(classifier_profile, dict):
            raise TypeError("classifier_profile must be a dict if provided")

        # Full, rich object for downstream nodes (refiner, data_query, final)
        exec_state["classifier_profile"] = dict(classifier_profile)

        # Flat, legacy view used by _resolve_pattern_for_run(config, ...)
        # (config["classifier"] is used there)
        config["classifier"] = {
            "intent": classifier_profile.get("intent"),
            "domain": classifier_profile.get("domain"),
            "action_type": classifier_profile.get("action_type")
                or classifier_profile.get("action"),
            "confidence": classifier_profile.get("confidence"),
        }

    # ---- Task classification (optional) ----
    if task_classification:
        if not isinstance(task_classification, dict):
            raise TypeError("task_classification must be a dict if provided")

        exec_state["task_classification"] = dict(task_classification)
        # Some nodes still look at top-level convenience keys
        config.setdefault("task_classification", task_classification)

    # ---- Cognitive classification (optional) ----
    if cognitive_classification:
        if not isinstance(cognitive_classification, dict):
            raise TypeError("cognitive_classification must be a dict if provided")

        exec_state["cognitive_classification"] = dict(cognitive_classification)
        # Top-level mirror for legacy use
        config.setdefault("cognitive_classification", cognitive_classification)

    return config


def build_orchestrator_config(
    *,
    query: str,
    base_config: Optional[Dict[str, Any]] = None,
    classifier_profile: Optional[ClassifierProfile] = None,
    task_classification: Optional[TaskClassification] = None,
    cognitive_classification: Optional[CognitiveClassification] = None,
) -> Dict[str, Any]:
    """
    Convenience helper used by your HTTP / service layer.

    Example usage:

        clf = run_classifier(query)
        config = build_orchestrator_config(
            query=query,
            base_config={
                "execution_config": {"use_rag": True, "graph_pattern": "standard"},
            },
            classifier_profile=clf,
            task_classification=clf.get("task_classification"),
            cognitive_classification=clf.get("cognitive_classification"),
        )
        ctx = await orchestrator.run(query, config=config)

    This ensures all the key fields are present for the orchestrator, including:

    * ``config["raw_query"]``
    * ``config["classifier"]``
    * ``config["execution_state"]["classifier_profile"]``
    * ``config["execution_state"]["task_classification"]``
    * ``config["execution_state"]["cognitive_classification"]``

    Args:
        query: Raw user query string.
        base_config: Optional base configuration to start from.
        classifier_profile: Rich classifier profile to attach.
        task_classification: Optional task-level classification details.
        cognitive_classification: Optional cognitive classification details.

    Returns:
        A fully populated orchestrator config dictionary.
    """
    cfg: Dict[str, Any] = dict(base_config or {})

    # Make sure raw_query is always available to the orchestrator
    cfg.setdefault("raw_query", query)

    # Attach classifier outputs in a canonical manner
    attach_classifier_to_config_inplace(
        cfg,
        classifier_profile=classifier_profile,
        task_classification=task_classification,
        cognitive_classification=cognitive_classification,
    )

    return cfg
