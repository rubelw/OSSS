# src/OSSS/services/google_client.py
from __future__ import annotations

import json
import threading
from typing import Iterable, List, Optional, Tuple, Dict

from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from OSSS.settings import settings

# ----- scopes --------------------------------------------------------------

def _normalize_scopes(scopes: Optional[Iterable[str] | str]) -> List[str]:
    """
    Accepts list/tuple, space-separated string, or CSV string.
    Falls back to minimal Classroom scopes for courses + rosters.
    """
    if scopes is None:
        return [
            "https://www.googleapis.com/auth/classroom.courses",
            "https://www.googleapis.com/auth/classroom.rosters",
        ]
    if isinstance(scopes, str):
        parts = [p.strip() for p in scopes.replace(",", " ").split()]
        return [p for p in parts if p]
    return list(scopes)

_SCOPES = _normalize_scopes(getattr(settings, "GC_SCOPES", None))

# ----- service-account helpers + tiny cache --------------------------------

_sa_cache: Dict[Tuple[str, Tuple[str, ...]], object] = {}
_sa_cache_lock = threading.Lock()

def _sa_credentials(impersonate: Optional[str] = None):
    """
    Build service-account credentials (optionally with DWD impersonation).
    Requires either settings.GC_SA_JSON or settings.GC_SA_JSON_PATH.
    """
    sa_json = getattr(settings, "GC_SA_JSON", None)
    sa_path = getattr(settings, "GC_SA_JSON_PATH", None)

    if sa_json:
        info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    elif sa_path:
        creds = service_account.Credentials.from_service_account_file(sa_path, scopes=_SCOPES)
    else:
        raise RuntimeError(
            "Service-account auth requires GC_SA_JSON or GC_SA_JSON_PATH in settings."
        )

    if impersonate:
        creds = creds.with_subject(impersonate)
    return creds

# ----- public factories -----------------------------------------------------

def classroom_service_impersonate(teacher_email: str):
    """
    Domain-Wide Delegation:
    Returns a Google Classroom client impersonating `teacher_email`.
    Caches one client per (subject, scopes) to avoid repeated discovery.
    """
    key = (teacher_email.lower(), tuple(sorted(_SCOPES)))
    with _sa_cache_lock:
        svc = _sa_cache.get(key)
        if svc is not None:
            return svc
        creds = _sa_credentials(impersonate=teacher_email)
        svc = build("classroom", "v1", credentials=creds, cache_discovery=False)
        _sa_cache[key] = svc
        return svc


def classroom_service_user(creds_json: dict):
    """
    Per-user OAuth:
    `creds_json` is the stored OAuth token for the user (e.g., a teacher).
    Refreshes if needed and returns a Classroom client.
    """
    creds = Credentials.from_authorized_user_info(creds_json, scopes=_SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise RuntimeError("Provided OAuth credentials are invalid and cannot be refreshed.")
    return build("classroom", "v1", credentials=creds, cache_discovery=False)
