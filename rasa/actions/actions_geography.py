from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

class ActionAnswerGeography(Action):
    def name(self) -> Text:
        return "action_answer_geography"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        geo_topic = tracker.get_slot("geo_topic")
        geo_level = tracker.get_slot("geo_level")
        geo_question = tracker.get_slot("geo_question")

        # TODO: hook this up to your LLM / tutor backend
        dispatcher.utter_message(
            text=(
                f"Topic: {geo_topic} | Level: {geo_level}\n\n"
                f"Question: {geo_question}\n\n"
                "Here’s where I’d call the OSSS geography tutor service."
            )
        )
        return []
