from __future__ import annotations
from typing import Any, Dict, List, Text
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import re

def _norm_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).lower() for v in value]
    return [str(value).lower()]

# Simple rules: map (interests, subjects, values, constraints) → clusters + roles + edu on-ramps.
CAREER_DB = [
    {
        "cluster": "IT & Software",
        "signals": {
            "interests": ["technology", "coding", "software"],
            "subjects": ["computer science", "math"],
            "values": ["high salary", "remote work", "creativity"],
        },
        "roles": ["Software Developer", "Data Analyst", "Cybersecurity Tech"],
        "edu": ["HS CS + AP CS", "Dual-credit IT", "CompTIA A+/Network+", "2-yr AAS or 4-yr CS"],
    },
    {
        "cluster": "Healthcare",
        "signals": {
                "interests": ["healthcare", "helping people", "medicine"],
                "subjects": ["biology", "science"],
                "values": ["helps people", "job stability"],
        },
        "roles": ["Nurse (RN/LPN)", "Medical Assistant", "EMT"],
        "edu": ["HS Bio/Anatomy", "CPR/EMT Basic", "CNA", "2-yr ASN or 4-yr BSN"],
    },
    {
        "cluster": "Business & Marketing",
        "signals": {
            "interests": ["business", "marketing", "finance"],
            "subjects": ["math", "english"],
            "values": ["high salary", "creativity"],
        },
        "roles": ["Marketing Coordinator", "Sales Rep", "Business Analyst"],
        "edu": ["HS DECA/FBLA", "Dual-credit Bus/Acct", "Google Analytics", "AA/BA"],
    },
    {
        "cluster": "Skilled Trades & Construction",
        "signals": {
            "interests": ["building", "trades"],
            "subjects": ["shop", "math"],
            "values": ["job stability", "hands-on"],
        },
        "roles": ["Electrician Apprentice", "Carpenter", "HVAC Tech"],
        "edu": ["CTE pathways", "Pre-apprenticeship", "OSHA-10", "Registered Apprenticeship"],
    },
    {
        "cluster": "Arts, Media & Design",
        "signals": {
            "interests": ["art", "design"],
            "subjects": ["english", "history"],
            "values": ["creativity"],
        },
        "roles": ["Graphic Designer", "UX Intern", "Content Creator"],
        "edu": ["HS Art/Design", "Portfolio", "Adobe Certified", "AA/BFA"],
    },
    {
        "cluster": "Public Service & Safety",
        "signals": {
            "interests": ["helping people", "outdoors", "animals"],
            "subjects": ["history", "science"],
            "values": ["helps people", "job stability"],
        },
        "roles": ["Teacher Aide → Teacher", "Police/Fire Cadet", "Parks & Wildlife Tech"],
        "edu": ["HS service clubs", "EMT/Fire Academy", "2-yr AA or 4-yr BA/BS"],
    },
]

def _score(signals: Dict[str, List[str]], interests, subjects, values):
    s = 0
    interests = set(_norm_list(interests))
    subjects  = set(_norm_list(subjects))
    values    = set(_norm_list(values))
    s += len(interests.intersection(signals.get("interests", [])))
    s += len(subjects.intersection(signals.get("subjects", [])))
    s += len(values.intersection(signals.get("values", [])))
    return s

def _applies_constraints(cluster: str, constraints: List[str]) -> bool:
    c = " ".join(_norm_list(constraints))
    if "apprentice" in c and cluster in {"Skilled Trades & Construction"}:
        return True
    if re.search(r"\b(two[- ]?year|2[- ]?year)\b", c) and cluster in {"IT & Software","Business & Marketing","Skilled Trades & Construction"}:
        return True
    if "not a 4-year" in c or "not a four-year" in c or "no college" in c:
        # Prefer trades, certificates, and AAS routes
        return cluster in {"Skilled Trades & Construction","Public Service & Safety","Healthcare"}
    # default: let it pass
    return True

class ActionSuggestCareers(Action):
    def name(self) -> Text:
        return "action_suggest_careers"

    def run(self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        grade = tracker.get_slot("grade_level")
        interests = tracker.get_slot("interests")
        subjects = tracker.get_slot("subject_strengths")
        values = tracker.get_slot("values")
        constraints = tracker.get_slot("constraints")

        ranked = []
        for row in CAREER_DB:
            score = _score(row["signals"], interests, subjects, values)
            if score > 0 and _applies_constraints(row["cluster"], constraints or []):
                ranked.append((score, row))

        ranked.sort(key=lambda x: x[0], reverse=True)
        top = [r[1] for r in ranked[:3]] or CAREER_DB[:3]

        lines = []
        lines.append(f"**Career ideas based on your answers (grade {grade})**:")
        for i, r in enumerate(top, 1):
            roles = ", ".join(r["roles"])
            edu = "; ".join(r["edu"])
            lines.append(f"{i}. **{r['cluster']}** — roles: {roles}.")
            lines.append(f"   • Suggested on-ramps: {edu}")

        dispatcher.utter_message(text="\n".join(lines))

        return [
            SlotSet("interests", interests),
            SlotSet("subject_strengths", subjects),
            SlotSet("values", values),
            SlotSet("constraints", constraints),
        ]
