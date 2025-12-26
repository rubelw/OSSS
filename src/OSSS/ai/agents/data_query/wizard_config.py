# src/OSSS/ai/agents/data_query/wizard_config.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from OSSS.ai.observability import get_logger

logger = get_logger(__name__)


NormalizerFn = Callable[[str], Any]


@dataclass(frozen=True)
class WizardFieldConfig:
    """
    Configuration for a single wizard field for a given collection.
    """
    name: str                      # field key in payload (e.g. "student", "status")
    label: str                     # human label ("Student", "Status")
    required: bool = True
    prompt: Optional[str] = None   # question to ask user
    summary_label: Optional[str] = None  # label in confirmation summary
    normalizer: Optional[NormalizerFn] = None  # special parsing logic
    default_value: Optional[Any] = None        # e.g. "today" for dates


@dataclass(frozen=True)
class WizardConfig:
    """
    Wizard configuration for a single collection / table.
    """
    collection: str                # e.g. "consents"
    fields: List[WizardFieldConfig]

    @property
    def required_fields(self) -> List[WizardFieldConfig]:
        return [f for f in self.fields if f.required]

    @property
    def optional_fields(self) -> List[WizardFieldConfig]:
        return [f for f in self.fields if not f.required]

    def field_by_name(self, name: str) -> Optional[WizardFieldConfig]:
        for f in self.fields:
            if f.name == name:
                return f
        return None


# ---------------------------------------------------------------------------
# Domain-specific helpers (you can move these here from agent.py)
# ---------------------------------------------------------------------------

def normalize_consent_status(answer: str) -> str:
    text = (answer or "").strip().lower()
    if not text:
        return ""
    if any(w in text for w in ["grant", "granted", "yes", "yep", "allow",
                               "allowed", "approve", "approved", "ok", "okay"]):
        return "granted"
    if any(w in text for w in ["deny", "denied", "no", "nope",
                               "disallow", "refuse", "decline"]):
        return "denied"
    return text


# ---------------------------------------------------------------------------
# STATIC REGISTRY OF WIZARD CONFIGS
# (later you can generate this from DBML / metadata)
# ---------------------------------------------------------------------------

WIZARD_CONFIGS: Dict[str, WizardConfig] = {
    "consents": WizardConfig(
        collection="consents",
        fields=[
            WizardFieldConfig(
                name="student",
                label="Student",
                required=True,
                prompt="Which student is this consent for? Please provide the full student name.",
                summary_label="Student",
            ),
            WizardFieldConfig(
                name="guardian",
                label="Guardian",
                required=True,
                prompt="Who gave this consent? Please provide the guardian’s name or relationship.",
                summary_label="Guardian",
            ),
            WizardFieldConfig(
                name="consent_type",
                label="Consent type",
                required=True,
                prompt="What kind of consent is this? For example: media release, field trip, technology use, etc.",
                summary_label="Type",
            ),
            WizardFieldConfig(
                name="status",
                label="Status",
                required=True,
                prompt="Was consent granted or denied?",
                summary_label="Status",
                normalizer=normalize_consent_status,
            ),
            WizardFieldConfig(
                name="effective_date",
                label="Effective date",
                required=False,
                prompt="What date should this consent be effective from? If it’s today, you can just say 'today'.",
                summary_label="Effective date",
                default_value="today",
            ),
            WizardFieldConfig(
                name="notes",
                label="Notes",
                required=False,
                prompt="Any notes you’d like to include? You can say 'no' if there are none.",
                summary_label="Notes",
            ),
        ],
    ),
    # Later: add more collections here – all tables from DBML if you want:
    # "students": WizardConfig(...),
    # "enrollments": WizardConfig(...),
}


def get_wizard_config_for_collection(collection: str | None) -> Optional[WizardConfig]:
    if not collection:
        return None
    cfg = WIZARD_CONFIGS.get(collection)
    if not cfg:
        logger.debug(
            "[wizard_config] no wizard config for collection",
            extra={"collection": collection},
        )
    return cfg
