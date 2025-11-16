# rasa/actions/career.py
from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet


class ActionSuggestCareers(Action):
    def name(self) -> Text:
        return "action_suggest_careers"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        interest = tracker.get_slot("career_interest")
        level = tracker.get_slot("career_level")

        # simple example logic; you’ll replace with your real mentor logic
        if not interest:
            dispatcher.utter_message(
                text="Tell me one subject or activity you enjoy at school."
            )
            return []

        suggestions = []
        if "math" in interest.lower():
            suggestions.append("data analyst")
            suggestions.append("civil engineer")
        if "art" in interest.lower():
            suggestions.append("graphic designer")

        if not suggestions:
            dispatcher.utter_message(
                text=f"Based on '{interest}', I’d like to explore a few different paths with you."
            )
        else:
            dispatcher.utter_message(
                text=(
                    f"Since you’re interested in **{interest}** "
                    f"at a **{level or 'basic'}** level, here are some ideas: "
                    + ", ".join(suggestions)
                )
            )

        return []

class ActionCareerResources(Action):
    def name(self) -> Text:
        return "action_career_resources"

    def run(self, dispatcher, tracker, domain):
        path = tracker.get_slot("career_path") or "general career exploration"
        dispatcher.utter_message(
            text=f"Here are some resources for {path}: local CTE programs, online intro courses, and job shadowing ideas."
        )
        return []
