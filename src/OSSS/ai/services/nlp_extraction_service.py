# src/OSSS/ai/services/nlp_extraction_service.py

from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class NLPExtractionService:
    """
    Lightweight NLP-based extraction for:
      - entities (names, orgs, grades, etc.)
      - date_filters (raw date mentions, phrases like 'this year', etc.)
      - flags (simple booleans like has_date, has_grade, etc.)

    This is intentionally:
      - best-effort
      - non-LLM
      - optional (fails open if spaCy isn't available)

    You can later specialize this for schools (grades, terms, etc.).
    """

    def __init__(
        self,
        enabled: bool = True,
        model_name: str = "en_core_web_sm",
    ) -> None:
        self.enabled = enabled
        self.model_name = model_name
        self._nlp = None

        if not enabled:
            logger.info("[NLPExtractionService] Disabled via config")
            return

        try:
            import spacy  # type: ignore

            self._nlp = spacy.load(model_name)
            logger.info(
                "[NLPExtractionService] Loaded spaCy model '%s'",
                model_name,
            )
        except Exception as e:
            logger.warning(
                "[NLPExtractionService] Failed to load spaCy model '%s': %s. "
                "NLP extraction will be no-op.",
                model_name,
                e,
            )
            self.enabled = False
            self._nlp = None

    def extract(self, text: str) -> Dict[str, Any]:
        """
        Main entrypoint.

        Returns a dict like:
        {
          "entities": {
            "named_entities": { "PERSON": [...], "ORG": [...], ... },
            "subjects": [...],   # noun-ish candidates
            "verbs": [...],      # verb lemmas
          },
          "date_filters": {
            "raw_mentions": [...],   # "this year", "2024-25", "yesterday"
          },
          "flags": {
            "has_date": bool,
            "has_person": bool,
            "has_org": bool,
          },
        }
        """
        if not text or not self.enabled or self._nlp is None:
            return {
                "entities": {},
                "date_filters": {},
                "flags": {},
            }

        doc = self._nlp(text)

        # --- Named entities ------------------------------------------------
        ents_by_label: Dict[str, List[str]] = {}
        for ent in doc.ents:
            ents_by_label.setdefault(ent.label_, []).append(ent.text)

        # --- Simple subject/verb candidates --------------------------------
        noun_heads: List[str] = []
        verb_lemmas: List[str] = []

        try:
            for token in doc:
                if token.pos_ in {"NOUN", "PROPN"} and token.dep_ in {
                    "nsubj",
                    "nsubjpass",
                    "dobj",
                    "pobj",
                    "attr",
                    "ROOT",
                }:
                    noun_heads.append(token.text)
                if token.pos_ == "VERB":
                    verb_lemmas.append(token.lemma_)
        except Exception as e:
            logger.debug(
                "[NLPExtractionService] token-level extraction failed: %s",
                e,
            )

        # --- Date filters --------------------------------------------------
        raw_date_mentions: List[str] = ents_by_label.get("DATE", []).copy()

        # Very simple phrase-based supplement (you can extend this later)
        text_lower = text.lower()
        extra_date_phrases: List[str] = []
        for phrase in [
            "this year",
            "last year",
            "next year",
            "this semester",
            "last semester",
            "next semester",
            "this term",
            "last term",
            "next term",
            "today",
            "yesterday",
            "tomorrow",
        ]:
            if phrase in text_lower:
                extra_date_phrases.append(phrase)

        raw_date_mentions.extend(extra_date_phrases)

        date_filters = {}
        if raw_date_mentions:
            # You can later normalize these into structured ranges.
            date_filters["raw_mentions"] = raw_date_mentions

        # --- Flags ---------------------------------------------------------
        flags = {
            "has_date": bool(raw_date_mentions),
            "has_person": bool(ents_by_label.get("PERSON")),
            "has_org": bool(ents_by_label.get("ORG")),
        }

        entities = {
            "named_entities": ents_by_label,
            "subjects": noun_heads,
            "verbs": verb_lemmas,
        }

        return {
            "entities": entities,
            "date_filters": date_filters,
            "flags": flags,
        }
