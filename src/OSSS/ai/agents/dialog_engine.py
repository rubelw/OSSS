import json
from typing import Dict, Any, Optional, Tuple

from .utils.dialog_utils import (
    parse_yes_no_choice,
    parse_school_year_choice,
    get_default_school_year_options,
)

PARSERS = {
    "yes_no_numeric": parse_yes_no_choice,
    "school_year_choice": parse_school_year_choice,
    "non_empty_text": lambda s: s.strip() or None,
    "email": lambda s: s if ("@" in s and "." in s) else None,
}

class DialogEngine:
    def __init__(self, flow: Dict[str, Any]):
        self.flow = flow
        self.steps_by_id = {step["id"]: step for step in flow["steps"]}

    def render_prompt(self, step_id: str, state: RegistrationSessionState, retry: bool = False) -> str:
        step = self.steps_by_id[step_id]
        text = step.get("retry_prompt") if retry else step["prompt"]

        # Example of simple templating; you could swap in Jinja2 if you want
        text = text.replace("{{school_year}}", state.school_year or "")
        text = text.replace("{{parent_first_name}}", state.parent_first_name or "")
        text = text.replace("{{parent_last_name}}", state.parent_last_name or "")

        if "{{school_year_menu}}" in text:
            options = get_default_school_year_options()
            menu_lines = [f"{i+1}. **{opt}**" for i, opt in enumerate(options)]
            text = text.replace("{{school_year_menu}}", "\n".join(menu_lines))

        return text

    def step_for_state(self, state: RegistrationSessionState) -> Optional[str]:
        """Pick the next step whose slot is not yet filled (and docs confirmed, etc.)."""
        for step in self.flow["steps"]:
            slot = step.get("slot")
            if slot is None:
                # Only used via explicit transitions like on_result
                continue
            if getattr(state, slot) is None:
                return step["id"]
        return None

    def handle_turn(
        self,
        state: RegistrationSessionState,
        user_query: str,
        last_step_id: Optional[str],
        last_was_retry: bool = False,
    ) -> Tuple[str, RegistrationSessionState, Optional[str]]:
        """
        Returns: (prompt_to_show, updated_state, next_step_id)
        """
        # 1. If we have a last_step_id and user has just responded, parse & store
        if last_step_id is not None:
            step = self.steps_by_id[last_step_id]
            parser_name = step.get("parser")
            slot = step.get("slot")
            parser = PARSERS.get(parser_name)

            parsed = parser(user_query) if parser else user_query

            if parsed is None:
                # Need retry for this same step
                prompt = self.render_prompt(last_step_id, state, retry=True)
                return prompt, state, last_step_id

            # Store slot value if there is one
            if slot:
                setattr(state, slot, parsed)

            # Branching based on result
            if "on_result" in step:
                key = "true" if parsed is True else "false"
                next_step_id = step["on_result"].get(key)
                if not next_step_id:
                    next_step_id = self.step_for_state(state)
            else:
                next_step_id = step.get("next") or self.step_for_state(state)
        else:
            # No previous step: start with first missing slot / first step
            next_step_id = self.step_for_state(state)

        # 2. If no next step, we're done
        if not next_step_id:
            return "", state, None  # engine says "proceed"

        # 3. Render prompt for next step
        prompt = self.render_prompt(next_step_id, state, retry=False)
        return prompt, state, next_step_id
