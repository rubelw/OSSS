# src/OSSS/ai/agents/data_views/delete_agent.py
from __future__ import annotations
from .write_base import DataWriteBaseAgent

class DataDeleteAgent(DataWriteBaseAgent):
    agent_name = "data_delete"
    method = "DELETE"
    path_attr = "delete_path"
