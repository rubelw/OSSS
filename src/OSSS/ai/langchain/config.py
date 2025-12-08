# src/OSSS/ai/langchain/config.py
from __future__ import annotations
from .base import SimpleChatAgent
from .registry import register_langchain_agent

# Intent -> LangChain agent name
INTENT_TO_LC_AGENT = {
    "student_info": "lc.student_info_table",
    #"students_missing_assignments": "lc.students_missing_assignments",
    # ...
}

# Config-driven simple agents
SIMPLE_AGENTS_CONFIG = [
    {
        "name": "default_chat",
        "prompt": "You are a helpful OSSS assistant.",
    },
    {
        "name": "lc.faq_policies",
        "prompt": "You answer questions about DCG Board policies clearly and accurately.",
    },
    # add many more FAQ-style agents here
]

for cfg in SIMPLE_AGENTS_CONFIG:
    register_langchain_agent(
        SimpleChatAgent(
            name=cfg["name"],
            system_prompt=cfg["prompt"],
        )
    )

# Import “complex” agents so they register themselves too
from .agents import student_info, students_missing_assignments  # noqa: F401
