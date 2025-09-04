from __future__ import annotations
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel

def _now():
    return datetime.now(timezone.utc)

class TokenSet(BaseModel):
    access_token: str
    refresh_token: str | None = None
    # server-side computed expiries in UTC
    access_expires_at: datetime
    refresh_expires_at: datetime | None = None

    @classmethod
    def from_oidc_response(cls, data: dict) -> "TokenSet":
        # Keycloak fields: access_token, expires_in, refresh_token, refresh_expires_in
        access_token = data["access_token"]
        access_exp = _now() + timedelta(seconds=int(data.get("expires_in", 0)))
        refresh_tok = data.get("refresh_token")
        refresh_exp = None
        if refresh_tok and "refresh_expires_in" in data:
            refresh_exp = _now() + timedelta(seconds=int(data["refresh_expires_in"]))
        return cls(
            access_token=access_token,
            refresh_token=refresh_tok,
            access_expires_at=access_exp,
            refresh_expires_at=refresh_exp,
        )
