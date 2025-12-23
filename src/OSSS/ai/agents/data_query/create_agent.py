# src/OSSS/ai/agents/data_query/create_agent.py
from __future__ import annotations
from .write_base import DataWriteBaseAgent

class DataCreateAgent(DataWriteBaseAgent):
    agent_name = "data_create"
    method = "POST"
    path_attr = "create_path"
