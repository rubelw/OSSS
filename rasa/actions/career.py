# OSSS/rasa/actions/career.py

from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher


class ActionCareerMentorSummary(Action):
    def name(self) -> Text:
        return "action_career_mentor_summary"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        interests = tracker.get_slot("interests")
        strengths = tracker.get_slot("subject_strengths")
        values = tracker.get_slot("values")
        constraints = tracker.get_slot("constraints")
        grade_level = tracker.get_slot("grade_level")

        # (You can make this much smarter over time)
        dispatcher.utter_message(
            text=(
                "Here's a quick snapshot of what you've shared:\n\n"
                f"- Interests: {interests}\n"
                f"- Subject strengths: {strengths}\n"
                f"- Values: {values}\n"
                f"- Constraints: {constraints}\n"
                f"- Grade level: {grade_level}\n\n"
                "From here, I can suggest some career clusters or example paths that "
                "fit your profile."
            )
        )

        return []
