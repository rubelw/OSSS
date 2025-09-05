#!/usr/bin/env python3

# ----- console logger + .env loader + HTTP logging (stdout, detailed) -----
import os, sys, json, logging
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

LOG_ENABLED = os.getenv("TEST_LOG", "1") != "0"
DEBUG_HTTP = os.getenv("DEBUG_HTTP", "1") != "0"
MAX_BODY = int(os.getenv("TEST_LOG_MAX_BODY", "1200"))

def _get_logger() -> logging.Logger:
    logger = logging.getLogger("osss.tests")
    # single stdout handler
    has_stdout = any(isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stdout
                     for h in logger.handlers)
    if not has_stdout:
        h = logging.StreamHandler(stream=sys.stdout)
        h.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(h)
    logger.propagate = False
    level_name = os.getenv("TEST_LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))
    return logger

log = _get_logger()

def _emit_console(line: str):
    try:
        print(line, file=sys.stdout, flush=True)
    except Exception:
        pass

def _log_info(msg: str):
    if LOG_ENABLED:
        log.info(msg)
        _emit_console(f"[INFO] {msg}")

def _log_debug(msg: str):
    if LOG_ENABLED and log.isEnabledFor(logging.DEBUG):
        log.debug(msg)
        _emit_console(f"[DEBUG] {msg}")

# ----- .env loader (looks upward) -----
def _load_env_if_present() -> Optional[Path]:
    try:
        from dotenv import load_dotenv, find_dotenv
    except Exception:
        _log_debug("python-dotenv not installed; skipping .env auto-load.")
        return None

    here = Path(__file__).resolve()
    candidates = []
    # allow explicit override
    env_file = os.getenv("ENV_FILE")
    if env_file:
        candidates.append(Path(env_file))
    # walk up a few levels from this file
    for i in range(0, 5):
        p = here.parents[i] / ".env"
        candidates.append(p)
    # cwd variants
    candidates += [Path(".env"), Path(".env.local")]
    # python-dotenv search (uses cwd)
    found = find_dotenv(usecwd=True)

    for p in candidates:
        if p.is_file():
            load_dotenv(p, override=False)
            _log_info(f".env loaded from: {p}")
            return p
    if found:
        load_dotenv(found, override=False)
        _log_info(f".env loaded via find_dotenv: {found}")
        return Path(found)
    _log_debug("No .env file found in known locations.")
    return None

_ENV_LOADED_FROM = _load_env_if_present()

# ----- redaction helpers -----
def _redact(v: Any) -> Any:
    if not isinstance(v, (str, bytes)):
        return v
    s = v.decode() if isinstance(v, bytes) else v
    if not s:
        return s
    # redact common secrets/tokens
    if len(s) > 6:
        return s[:3] + "…" + s[-3:]
    return "***"

def _safe_headers(h: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    h = dict(h or {})
    for k in list(h.keys()):
        lk = k.lower()
        if lk in ("authorization", "proxy-authorization"):
            h[k] = "<redacted>"
        if "secret" in lk or "token" in lk:
            h[k] = "<redacted>"
    return h

def _fmt_body(resp) -> str:
    try:
        data = resp.json()
        txt = json.dumps(data, ensure_ascii=False)  # pretty if you like: indent=2
    except Exception:
        txt = getattr(resp, "text", "") or ""
    if len(txt) > MAX_BODY:
        return txt[:MAX_BODY] + "…(truncated)"
    return txt

def _http_log_request(method: str, url: str, *, headers=None, params=None, data=None, json_body=None):
    if not DEBUG_HTTP:
        return
    try:
        body_tag = "json" if json_body is not None else ("data" if data is not None else None)
        _log_debug(
            f"HTTP {method} → {url} "
            f"headers={_safe_headers(headers)} "
            f"params={params} "
            f"{body_tag}={'<present>' if body_tag else None}"
        )
    except Exception:
        pass

def _http_log_response(method: str, url: str, resp):
    if not DEBUG_HTTP:
        return
    try:
        _log_debug(f"HTTP {method} ← {url} status={resp.status_code} body={_fmt_body(resp)}")
    except Exception:
        pass

# ----- async request wrappers that always log -----
import inspect, asyncio

def _url(path: str) -> str:
    base = os.getenv("APP_BASE_URL", "").rstrip("/") or None
    return f"{base}{path}" if base else path

async def _aget(client, url: str, **kwargs):
    _http_log_request("GET", url, headers=kwargs.get("headers"), params=kwargs.get("params"))
    get_fn = getattr(client, "get")
    if inspect.iscoroutinefunction(get_fn):
        resp = await get_fn(url, **kwargs)
    else:
        resp = await asyncio.to_thread(get_fn, url, **kwargs)
    _http_log_response("GET", url, resp)
    return resp

async def _apost(client, url: str, *, headers=None, data=None, json=None, **kwargs):
    _http_log_request("POST", url, headers=headers, data=data, json_body=json)
    post_fn = getattr(client, "post")
    if inspect.iscoroutinefunction(post_fn):
        resp = await post_fn(url, headers=headers, data=data, json=json, **kwargs)
    else:
        resp = await asyncio.to_thread(post_fn, url, headers=headers, data=data, json=json, **kwargs)
    _http_log_response("POST", url, resp)
    return resp

# ----- Keycloak OAuth2: password grant with detailed logs -----
def _kc_token_endpoint(issuer: str) -> str:
    return f"{issuer.rstrip('/')}/protocol/openid-connect/token"

def _kc_logout_endpoint(issuer: str) -> str:
    return f"{issuer.rstrip('/')}/protocol/openid-connect/logout"

def _basic_auth_header(cid: str, csec: str) -> Dict[str, str]:
    import base64
    raw = f"{cid}:{csec}".encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}

def fetch_token_password_grant(*, issuer: str, client_id: str, client_secret: str,
                               username: str, password: str, scope: str = "openid") -> Dict[str, Any]:
    import requests as _rq
    url = _kc_token_endpoint(issuer)
    common = {"grant_type": "password", "username": username, "password": password, "scope": scope}
    _log_info(f"Keycloak token: POST {url} (password grant, client_secret_basic) client_id={client_id}")

    # Attempt 1: client_secret_basic
    try:
        r1 = _rq.post(url, data=common, headers=_basic_auth_header(client_id, client_secret), timeout=15)
        _http_log_response("POST", url, r1)
        if r1.status_code == 200:
            tok = r1.json()
            # redact in log
            safe = {k: ("<redacted>" if "token" in k else v) for k, v in tok.items()}
            _log_info(f"Keycloak token success (basic): keys={list(safe.keys())}")
            return tok
        _log_debug(f"Keycloak token (basic) failed status={r1.status_code} body={_fmt_body(r1)}")
    except Exception as e:
        _log_debug(f"Keycloak token (basic) request error: {e}")

    # Attempt 2: client_secret_post
    payload = dict(common, client_id=client_id, client_secret=client_secret)
    _log_info(f"Keycloak token: POST {url} (client_secret_post) client_id={client_id}")
    r2 = _rq.post(url, data=payload, timeout=15)
    _http_log_response("POST", url, r2)
    if r2.status_code == 200:
        tok = r2.json()
        safe = {k: ("<redacted>" if "token" in k else v) for k, v in tok.items()}
        _log_info(f"Keycloak token success (post): keys={list(safe.keys())}")
        return tok

    # Fail with diagnostics
    _log_info(f"Keycloak token failed both methods. basic={getattr(r1,'status_code', 'NA')} post={r2.status_code}")
    raise AssertionError(
        "Keycloak password grant failed.\n"
        f"  URL: {url}\n"
        f"  basic.status={getattr(r1,'status_code','NA')} body={_fmt_body(r1) if 'r1' in locals() else 'NA'}\n"
        f"  post.status={r2.status_code} body={_fmt_body(r2)}"
    )

def keycloak_logout(*, issuer: str, client_id: str, client_secret: str, refresh_token: Optional[str]) -> None:
    if not refresh_token:
        _log_debug("Keycloak logout skipped (no refresh_token).")
        return
    import requests as _rq
    url = _kc_logout_endpoint(issuer)
    _log_info(f"Keycloak logout: POST {url} (client_secret_post)")
    resp = _rq.post(url, data={"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token}, timeout=10)
    _http_log_response("POST", url, resp)
