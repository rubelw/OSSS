from fastapi import APIRouter, Form, Response, Header, HTTPException, status
import base64, httpx
from OSSS.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])

BASE = str(settings.KEYCLOAK_BASE_URL).rstrip("/")
TOKEN_URL = f"{BASE}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"

def _parse_basic(auth_header: str | None):
    if not auth_header or not auth_header.lower().startswith("basic "):
        return None, None
    try:
        raw = base64.b64decode(auth_header.split(" ", 1)[1]).decode()
        cid, csec = raw.split(":", 1)
        return cid, csec
    except Exception:
        return None, None

@router.post("/token")
async def token_proxy(
    grant_type: str = Form("password"),
    username: str | None = Form(None),
    password: str | None = Form(None),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    scope: str | None = Form(None),
    authorization: str | None = Header(None),  # optional Basic <base64(client:secret)>
):
    # Infer client from Authorization header or settings if not sent by Swagger
    hdr_id, hdr_secret = _parse_basic(authorization)
    cid = client_id or hdr_id or settings.SWAGGER_CLIENT_ID
    csec = client_secret or hdr_secret or settings.SWAGGER_CLIENT_SECRET

    if not cid:
        raise HTTPException(status_code=400, detail="client_id missing (set SWAGGER_CLIENT_ID or send Basic auth)")

    if grant_type == "password":
        if not username or not password:
            raise HTTPException(status_code=400, detail="username/password required for password grant")

    data = {"grant_type": grant_type, "client_id": cid}
    if csec:
        data["client_secret"] = csec
    if scope:
        data["scope"] = scope
    if grant_type == "password":
        data["username"] = username or ""
        data["password"] = password or ""

    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(TOKEN_URL, data=data)
        return Response(r.content, status_code=r.status_code, media_type="application/json")
