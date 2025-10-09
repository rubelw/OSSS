# src/OSSS/tests/test_health.py
from __future__ import annotations

import os
import pytest
import requests

BASE = os.getenv("APP_BASE_URL", "").rstrip("/") or None
LIVE_MODE = bool(BASE)


@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
def test_healthz():
    """Integration test for live /healthz endpoint."""
    r = requests.get(BASE + "/healthz", timeout=8)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
