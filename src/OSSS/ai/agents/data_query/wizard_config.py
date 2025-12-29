# src/OSSS/ai/agents/data_query/wizard_config.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import json
from pathlib import Path

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
# Domain-specific helpers
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


# Map string names in JSON -> actual Python callables
_NORMALIZER_REGISTRY: Dict[str, NormalizerFn] = {
    "normalize_consent_status": normalize_consent_status,
    # add more here as you define them
}


JSON_PATH = Path(__file__).resolve().parent / "wizard_configs.json"


def _load_wizard_configs_from_json(path: Path) -> Dict[str, WizardConfig]:
    """
    Load wizard configs from JSON.

    Supports both shapes:

      1) {
           "collections": {
             "consents": {
               "collection": "consents",
               "fields": [...]
             },
             ...
           }
         }

      2) {
           "consents": {
             "collection": "consents",
             "fields": [...]
           },
           ...
         }

    If 'collection' is missing on a config, we fall back to its dict key.
    """
    if not path.exists():
        logger.info("[wizard_config] JSON config not found at %s; using empty registry", path)
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.exception(
            "[wizard_config] Failed to load JSON config; using empty registry",
            extra={"json_path": str(path)},
        )
        return {}

    if not isinstance(data, dict):
        logger.error(
            "[wizard_config] JSON root is not an object; using empty registry",
            extra={"json_type": type(data).__name__},
        )
        return {}

    # Accept either root["collections"] or the root itself as the collections map
    if "collections" in data and isinstance(data["collections"], dict):
        collections_data = data["collections"]
    else:
        collections_data = data

    result: Dict[str, WizardConfig] = {}

    for cfg_key, cfg in collections_data.items():
        if not isinstance(cfg, dict):
            logger.warning(
                "[wizard_config] Skipping non-dict config entry",
                extra={"key": cfg_key, "value_type": type(cfg).__name__},
            )
            continue

        collection_name = cfg.get("collection") or cfg_key
        raw_fields = cfg.get("fields", [])

        if not isinstance(raw_fields, list):
            logger.warning(
                "[wizard_config] 'fields' is not a list; skipping collection",
                extra={"collection": collection_name, "fields_type": type(raw_fields).__name__},
            )
            continue

        fields: List[WizardFieldConfig] = []

        for f in raw_fields:
            if not isinstance(f, dict):
                logger.warning(
                    "[wizard_config] Skipping non-dict field config",
                    extra={"collection": collection_name, "field_value_type": type(f).__name__},
                )
                continue

            name = f.get("name")
            if not name:
                logger.warning(
                    "[wizard_config] Field missing 'name'; skipping",
                    extra={"collection": collection_name, "field_config": f},
                )
                continue

            label = f.get("label") or name.replace("_", " ").title()
            required = bool(f.get("required", True))
            prompt = f.get("prompt")
            summary_label = f.get("summary_label") or label
            default_value = f.get("default_value")

            normalizer_name = f.get("normalizer")
            normalizer = None
            if isinstance(normalizer_name, str):
                normalizer = _NORMALIZER_REGISTRY.get(normalizer_name)
                if normalizer is None:
                    logger.warning(
                        "[wizard_config] Unknown normalizer; leaving as None",
                        extra={
                            "collection": collection_name,
                            "field": name,
                            "normalizer_name": normalizer_name,
                        },
                    )

            fields.append(
                WizardFieldConfig(
                    name=name,
                    label=label,
                    required=required,
                    prompt=prompt,
                    summary_label=summary_label,
                    normalizer=normalizer,
                    default_value=default_value,
                )
            )

        if not fields:
            logger.info(
                "[wizard_config] No valid fields for collection; skipping",
                extra={"collection": collection_name},
            )
            continue

        result[collection_name] = WizardConfig(
            collection=collection_name,
            fields=fields,
        )

    logger.info(
        "[wizard_config] Loaded %d wizard configs from %s",
        len(result),
        str(path),
    )
    return result


# Global registry loaded at import time
WIZARD_CONFIGS: Dict[str, WizardConfig] = _load_wizard_configs_from_json(JSON_PATH)


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
