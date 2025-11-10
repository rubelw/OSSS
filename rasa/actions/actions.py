import os
from typing import Any, Dict, List, Text

import httpx
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

# ====== Configuration ======
BACKEND = os.getenv("LLM_BACKEND", "OLLAMA").upper()  # OLLAMA or OPENAI_COMPAT

# Ollama (local)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# OpenAI-compatible (LM Studio or other)
OA_URL = os.getenv("OA_URL", "http://localhost:1234/v1")
OA_MODEL = os.getenv("OA_MODEL", "gpt-4o-mini")
OA_API_KEY = os.getenv("OA_API_KEY", "lm-studio")  # LM Studio usually accepts any key

SYSTEM_BASE = (
    "You are an AI mentor for students. Be clear, encouraging, and step-by-step.\n"
    "Ask brief clarifying questions when needed. Prefer scaffolding over giving final answers.\n"
    "If in 'socratic' mode, use short prompts and elicit thinking. If in 'direct' mode, explain explicitly with examples."
)

def system_prompt(mode: str, learner_notes: str) -> str:
    mode_line = f"Current mentor mode: {mode or 'socratic'}."
    notes = f"Learner notes: {learner_notes}" if learner_notes else "Learner notes: (none provided)."
    return f"{SYSTEM_BASE}\n{mode_line}\n{notes}"

def conversation_history(tracker: Tracker, k: int = 6) -> List[Dict[str, str]]:
    msgs: List[Dict[str, str]] = []
    # add recent user/bot turns for coherence
    turns: List[Dict[str, str]] = []
    for e in tracker.events[::-1]:
        if e.get("event") == "bot" and e.get("text"):
            turns.append({"role": "assistant", "content": e["text"]})
        elif e.get("event") == "user" and e.get("text"):
            turns.append({"role": "user", "content": e["text"]})
        if len(turns) >= 2 * k:
            break
    return list(reversed(turns))

async def call_ollama(prompt: str, sys_prompt: str, history: List[Dict[str, str]]) -> str:
    # Use chat endpoint if available; else generate with concatenated prompt
    # Simple: concat history
    ctx = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
    full = f"{sys_prompt}\n\n{ctx}\n\nUSER: {prompt}\nASSISTANT:"
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{OLLAMA_URL}/api/generate", json={
            "model": OLLAMA_MODEL,
            "prompt": full,
            "stream": False
        })
        r.raise_for_status()
        return r.json().get("response", "").strip()

async def call_openai_compat(prompt: str, sys_prompt: str, history: List[Dict[str, str]]) -> str:
    messages = [{"role": "system", "content": sys_prompt}] + history + [{"role": "user", "content": prompt}]
    headers = {"Authorization": f"Bearer {OA_API_KEY}"}
    payload = {"model": OA_MODEL, "messages": messages, "temperature": 0.2, "max_tokens": 800}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{OA_URL}/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()

class ActionAIMentor(Action):
    def name(self) -> Text:
        return "action_ai_mentor"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_utterance = tracker.latest_message.get("text", "").strip()
        mode = tracker.get_slot("mentor_mode") or "socratic"
        notes = tracker.get_slot("learner_notes") or ""
        sys_p = system_prompt(mode, notes)
        hist = conversation_history(tracker)

        # keep last_topic if the user mentioned an entity
        topic = None
        ents = tracker.latest_message.get("entities") or []
        for e in ents:
            if e.get("entity") == "topic":
                topic = e.get("value")

        try:
            if BACKEND == "OPENAI_COMPAT":
                reply = await call_openai_compat(user_utterance, sys_p, hist)
            else:
                reply = await call_ollama(user_utterance, sys_p, hist)
            dispatcher.utter_message(text=reply[:1800])
            events: List[Any] = []
            if topic:
                events.append(SlotSet("last_topic", topic))
            return events
        except Exception as e:
            dispatcher.utter_message(text=f"Sorry—my mentor engine ran into an error: {e}")
            return []

class ActionSetMode(Action):
    def name(self) -> Text:
        return "action_set_mode"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        text = (tracker.latest_message.get("text") or "").lower()
        if "direct" in text:
            mode = "direct"
        elif "socratic" in text or "hints" in text:
            mode = "socratic"
        else:
            mode = (tracker.get_slot("mentor_mode") or "socratic")
        return [SlotSet("mentor_mode", mode)]

class ActionStoreContext(Action):
    def name(self) -> Text:
        return "action_store_context"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # naive: append latest user text into learner_notes
        existing = tracker.get_slot("learner_notes") or ""
        new_text = tracker.latest_message.get("text", "")
        merged = (existing + " | " + new_text).strip(" |")
        return [SlotSet("learner_notes", merged)]
