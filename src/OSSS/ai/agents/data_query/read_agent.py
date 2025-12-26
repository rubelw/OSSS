# src/OSSS/ai/agents/data_query/read_agent.py
from __future__ import annotations

"""
Compatibility wrapper for the dynamic DataQueryAgent.

Historically, the data query logic lived here and was hard-coded to /api/warrantys.
We now use the dynamic implementation in agent.py that is driven by:
- routes.json (DataQueryRoute)
- execution_config.data_query.* (topic, base_url, params, etc.)

This module simply re-exports DataQueryAgent so any older imports still work.
"""

from OSSS.ai.agents.data_query.agent import DataQueryAgent

__all__ = ["DataQueryAgent"]
