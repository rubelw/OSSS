#!/usr/bin/env python3
from __future__ import annotations

import sys
import os
import json
import time
import base64
from pathlib import Path
from typing import Any, Dict, Optional

import click
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm

# --- TOML IO (py3.11 stdlib reader + tomli_w for writing) ---
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore
from tomli_w import dump as toml_dump

# -----------------------------------------------------------------------------
# Globals / Config
# -----------------------------------------------------------------------------
console = Console()
CONFIG_PATH = Path.home() / ".ossscli.toml"

# Environment key mapping -> config keys
ENV_MAP = {
    # API
    "OSSS_API_BASE": "api_base",
    "OSSS_API_TOKEN": "token",
    "OSSS_API_TIMEOUT": "timeout",
    # Keycloak
    "KC_BASE": "kc_base",
    "KC_REALM": "kc_realm",
    "KC_CLIENT_ID": "kc_client_id",
    "KC_CLIENT_SECRET": "kc_client_secret",
    "KC_SCOPE": "kc_scope",
}

DEFAULTS: Dict[str, Any] = {
    # API server
    "api_base": "http://localhost:8081",
    "timeout": 20,
    "token": "",  # kept for compatibility; mirrors kc_access_token after login

    # Keycloak defaults
    "kc_base": "http://localhost:8085",
    "kc_realm": "OSSS",
    "kc_client_id": "osss-cli",
    "kc_client_secret": "",
    "kc_scope": "openid profile email roles",

    # tokens (populated by auth login/refresh)
    "kc_access_token": "",
    "kc_refresh_token": "",
    "kc_expires_at": 0.0,
}

# Explicit override path for .env: always try ../../.env from the current working directory
DOTENV_OVERRIDE_PATH = (Path.cwd() / "../../.env").resolve()

# -----------------------------------------------------------------------------
# .env loading (no external dependency)
# -----------------------------------------------------------------------------
def _parse_dotenv(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists() or not path.is_file():
        return env
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if v and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
            v = v[1:-1]
        env[k] = v
    return env

def _load_env_vars() -> Dict[str, str]:
    """Load env from ../../.env (relative to CWD) and OS env (OS overrides file)."""
    file_env: Dict[str, str] = _parse_dotenv(DOTENV_OVERRIDE_PATH)
    merged: Dict[str, str] = dict(file_env)
    for k in ENV_MAP.keys():
        if k in os.environ and os.environ[k] != "":
            merged[k] = os.environ[k]
    return merged

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _kc_urls(cfg: Dict[str, Any]) -> Dict[str, str]:
    base = (cfg.get("kc_base") or DEFAULTS["kc_base"]).rstrip("/")
    realm = cfg.get("kc_realm") or DEFAULTS["kc_realm"]
    root = f"{base}/realms/{realm}/protocol/openid-connect"
    return {
        "token": f"{root}/token",
        "userinfo": f"{root}/userinfo",
        "logout": f"{root}/logout",
    }

def _jwt_payload(token: str) -> Dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        pad = "=" * (-len(parts[1]) % 4)
        raw = base64.urlsafe_b64decode(parts[1] + pad)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}

def load_config() -> Dict[str, Any]:
    """Effective config precedence:
       DEFAULTS < saved config (~/.ossscli.toml) < ../../.env < OS env
       (tokens are persisted in config; env won't blank them out)
    """
    cfg = dict(DEFAULTS)

    # Load saved config
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("rb") as f:
            file_cfg = tomllib.load(f)
        cfg.update({k: v for k, v in file_cfg.items() if v not in ("", None)})

    # Load explicit ../../.env and OS env
    env_vars = _load_env_vars()
    for env_key, conf_key in ENV_MAP.items():
        val = env_vars.get(env_key, None)
        if val not in (None, ""):
            if conf_key == "timeout":
                try:
                    cfg[conf_key] = int(val)
                    continue
                except ValueError:
                    pass
            cfg[conf_key] = val

    return cfg

def save_config(cfg: Dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if cfg.get("kc_access_token"):
        cfg["token"] = cfg["kc_access_token"]
    with CONFIG_PATH.open("wb") as f:
        toml_dump(cfg, f)

def _maybe_refresh(cfg: Dict[str, Any]) -> Dict[str, Any]:
    now = time.time()
    exp = float(cfg.get("kc_expires_at") or 0.0)
    rt = cfg.get("kc_refresh_token") or ""
    if rt and (not cfg.get("kc_access_token") or now >= exp - 10):
        urls = _kc_urls(cfg)
        data = {
            "grant_type": "refresh_token",
            "client_id": cfg["kc_client_id"],
            "refresh_token": rt,
        }
        if cfg.get("kc_client_secret"):
            data["client_secret"] = cfg["kc_client_secret"]
        try:
            with httpx.Client(timeout=int(cfg.get("timeout", 20))) as c:
                r = c.post(urls["token"], data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
            if r.is_success:
                tok = r.json()
                cfg["kc_access_token"] = tok.get("access_token", "")
                cfg["kc_refresh_token"] = tok.get("refresh_token", rt)
                cfg["kc_expires_at"] = time.time() + float(tok.get("expires_in", 60)) - 30
                cfg["token"] = cfg["kc_access_token"]
                save_config(cfg)
                console.log("[green]Token refreshed[/]")
            else:
                console.log(f"[red]Refresh failed:[/] {r.status_code} {r.text}")
        except Exception as e:
            console.log(f"[red]Refresh error:[/] {e}")
    return cfg

def client(cfg: Dict[str, Any]) -> httpx.Client:
    cfg = _maybe_refresh(cfg)
    headers: Dict[str, str] = {"Accept": "application/json"}
    token = cfg.get("kc_access_token") or cfg.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=cfg["api_base"], headers=headers, timeout=int(cfg.get("timeout", 20)))

def show_json(obj: Any) -> None:
    if isinstance(obj, (dict, list)):
        console.print_json(data=obj)
    else:
        console.print_json(obj)

def show_table(items: list[dict[str, Any]], columns: list[str]) -> None:
    t = Table(show_lines=False)
    for col in columns:
        t.add_column(col)
    for it in items:
        t.add_row(*(str(it.get(c, "")) for c in columns))
    console.print(t)

def _handle_resp(r: httpx.Response):
    ctype = (r.headers.get("content-type") or "").split(";")[0].strip()
    data = r.json() if ctype == "application/json" else r.text
    if r.is_success:
        return data
    msg = data if isinstance(data, str) else json.dumps(data, indent=2)
    console.print(f"[red]HTTP {r.status_code}[/]: {msg}")
    raise click.Abort()

def _confirm_delete(kind: str, ident: Any) -> bool:
    return Confirm.ask(f"Delete {kind} [bold]{ident}[/]?")

# -----------------------------------------------------------------------------
# Click Application
# -----------------------------------------------------------------------------
@click.group(help="OSSS CLI (Click edition)")
def cli() -> None:
    """Top-level command group."""

# ---- config subgroup ----
@cli.group("config", help="View or set CLI configuration")
def config_group() -> None:
    pass

@config_group.command("show", help="Show effective configuration")
def config_show() -> None:
    cfg = load_config()
    redacted = {**cfg, "kc_client_secret": "***" if cfg.get("kc_client_secret") else ""}
    # include which .env path we read for clarity
    redacted["_env_path"] = str(DOTENV_OVERRIDE_PATH)
    console.print(Panel.fit(json.dumps(redacted, indent=2), title="Config"))

@config_group.command("set-base", help="Set API base URL, e.g., http://localhost:8081")
@click.argument("api_base", metavar="API_BASE")
def config_set_base(api_base: str) -> None:
    cfg = load_config()
    cfg["api_base"] = api_base
    save_config(cfg)
    console.print(f"[green]Saved[/] api_base = [cyan]{api_base}[/]")

@config_group.command("set-token", help="Set bearer token used for API calls")
@click.argument("token", metavar="TOKEN")
def config_set_token(token: str) -> None:
    cfg = load_config()
    cfg["kc_access_token"] = token
    cfg["token"] = token
    cfg["kc_expires_at"] = time.time() + 60  # unknown; force refresh if refresh_token exists
    save_config(cfg)
    console.print(f"[green]Saved[/] token")

@config_group.command("from-env", help="Load ../../.env and OS env into saved config")
def config_from_env() -> None:
    cfg = load_config()
    env_vars = _load_env_vars()
    changed = False
    for env_key, conf_key in ENV_MAP.items():
        val = env_vars.get(env_key, None)
        if val not in (None, ""):
            if conf_key in {"kc_access_token", "kc_refresh_token"}:
                continue
            cfg[conf_key] = val
            changed = True
    if changed:
        save_config(cfg)
        console.print("[green]Config updated from env[/]")
    else:
        console.print("[yellow]No changes from env[/]")

# ---- auth subgroup (Keycloak) ----
@cli.group("auth", help="Authenticate with Keycloak")
def auth_group() -> None:
    pass

@auth_group.command("login", help="Login via Direct Access Grants (password flow)")
@click.option("--username", prompt=True)
@click.option("--password", prompt=True, hide_input=True)
@click.option("--client-id", default=None, help="Override client_id")
@click.option("--client-secret", default=None, help="Override client_secret")
@click.option("--realm", default=None, help="Override realm")
@click.option("--base", "base_url", default=None, help="Override Keycloak base, e.g. http://localhost:8085")
@click.option("--scope", default=None, help="Override OIDC scope (space-separated)")
def auth_login(username: str, password: str, client_id: Optional[str], client_secret: Optional[str],
               realm: Optional[str], base_url: Optional[str], scope: Optional[str]) -> None:
    cfg = load_config()
    if client_id: cfg["kc_client_id"] = client_id
    if client_secret is not None: cfg["kc_client_secret"] = client_secret
    if realm: cfg["kc_realm"] = realm
    if base_url: cfg["kc_base"] = base_url
    if scope: cfg["kc_scope"] = scope

    urls = _kc_urls(cfg)
    data = {
        "grant_type": "password",
        "client_id": cfg["kc_client_id"],
        "username": username,
        "password": password,
        "scope": cfg.get("kc_scope", "openid profile email roles"),
    }
    if cfg.get("kc_client_secret"):
        data["client_secret"] = cfg["kc_client_secret"]

    with httpx.Client(timeout=int(cfg.get("timeout", 20))) as c:
        r = c.post(urls["token"], data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    if not r.is_success:
        console.print(f"[red]Login failed[/] {r.status_code}: {r.text}")
        raise click.Abort()

    tok = r.json()
    cfg["kc_access_token"] = tok.get("access_token", "")
    cfg["kc_refresh_token"] = tok.get("refresh_token", "")
    cfg["kc_expires_at"] = time.time() + float(tok.get("expires_in", 60)) - 30
    cfg["token"] = cfg["kc_access_token"]
    save_config(cfg)

    claims = _jwt_payload(cfg["kc_access_token"])
    roles = (claims.get("realm_access", {}) or {}).get("roles", [])
    console.print("[green]Logged in[/] ✅")
    console.print(f"user: [cyan]{claims.get('preferred_username') or claims.get('sub')}[/]  realm: [cyan]{cfg['kc_realm']}[/]")
    if roles:
        console.print("roles:", ", ".join(roles))

@auth_group.command("refresh", help="Force a token refresh using the stored refresh_token")
def auth_refresh() -> None:
    cfg = load_config()
    before = cfg.get("kc_access_token")
    _maybe_refresh(cfg)
    after = cfg.get("kc_access_token")
    if after and after != before:
        console.print("[green]Refreshed[/] ✅")
    else:
        console.print("[yellow]No refresh performed[/] (missing/expired refresh token?)")

@auth_group.command("logout", help="Logout (revokes refresh token if possible)")
def auth_logout() -> None:
    cfg = load_config()
    urls = _kc_urls(cfg)
    data = {
        "client_id": cfg["kc_client_id"],
        "refresh_token": cfg.get("kc_refresh_token", ""),
    }
    if cfg.get("kc_client_secret"):
        data["client_secret"] = cfg["kc_client_secret"]

    ok = False
    if data["refresh_token"]:
        try:
            with httpx.Client(timeout=int(cfg.get("timeout", 20))) as c:
                r = c.post(urls["logout"], data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
            ok = r.is_success
        except Exception as e:
            console.log(f"[red]Logout error:[/] {e}")

    for k in ["kc_access_token", "kc_refresh_token", "kc_expires_at", "token"]:
        cfg[k] = "" if k != "kc_expires_at" else 0.0
    save_config(cfg)
    console.print("[green]Logged out[/] ✅" if ok else "[yellow]Local tokens cleared[/]")

@auth_group.command("whoami", help="Show current user/claims from token or userinfo endpoint")
def auth_whoami() -> None:
    cfg = load_config()
    cfg = _maybe_refresh(cfg)
    token = cfg.get("kc_access_token") or cfg.get("token")
    if not token:
        console.print("[red]Not authenticated[/] (no access token)")
        raise click.Abort()

    urls = _kc_urls(cfg)
    try:
        with httpx.Client(timeout=int(cfg.get("timeout", 20))) as c:
            r = c.get(urls["userinfo"], headers={"Authorization": f"Bearer {token}"})
        if r.is_success:
            data = r.json()
            console.print(Panel.fit(json.dumps(data, indent=2), title="userinfo"))
            return
    except Exception:
        pass

    claims = _jwt_payload(token)
    if claims:
        console.print(Panel.fit(json.dumps(claims, indent=2), title="access_token (decoded)"))
    else:
        console.print("[red]Could not retrieve user info[/]")

# ---- schools subgroup ----
@cli.group("schools", help="Manage schools resources")
def schools_group() -> None:
    pass

@schools_group.command("list", help="List schools")
@click.option("--limit", default=50, show_default=True, type=int)
@click.option("--cursor", default=None)
def schools_list(limit: int, cursor: Optional[str]) -> None:
    cfg = load_config()
    with client(cfg) as c:
        r = c.get("/schools", params={"limit": limit, "cursor": cursor})
        data = _handle_resp(r)

    items = data.get("items", data) if isinstance(data, dict) else data
    if isinstance(items, list) and items and isinstance(items[0], dict):
        cols = ["id", "name", "district_id", "timezone"]
        cols = [c for c in cols if any(c in it for it in items)]
        show_table(items, cols)
    else:
        show_json(items)

@schools_group.command("get", help="Get a school by ID")
@click.argument("school_id")
def schools_get(school_id: str) -> None:
    cfg = load_config()
    with client(cfg) as c:
        r = c.get(f"/schools/{school_id}")
        data = _handle_resp(r)
    show_json(data)

@schools_group.command("create", help="Create a school")
@click.option("--name", required=True, help="School name")
@click.option("--district-id", "district_id", required=True, help="District id")
@click.option("--timezone", default=None)
@click.option("--school-code", "school_code", default=None)
def schools_create(name: str, district_id: str, timezone: Optional[str], school_code: Optional[str]) -> None:
    payload: Dict[str, Any] = {"name": name, "district_id": district_id}
    if timezone: payload["timezone"] = timezone
    if school_code: payload["school_code"] = school_code
    cfg = load_config()
    with client(cfg) as c:
        r = c.post("/schools", json=payload, headers={"Content-Type": "application/json"})
        data = _handle_resp(r)
    console.print("[green]Created[/] ✅")
    show_json(data)

@schools_group.command("update", help="Update a school (partial)")
@click.argument("school_id")
@click.option("--name", default=None)
@click.option("--district-id", "district_id", default=None)
@click.option("--timezone", default=None)
@click.option("--school-code", "school_code", default=None)
def schools_update(school_id: str, name: Optional[str], district_id: Optional[str], timezone: Optional[str], school_code: Optional[str]) -> None:
    payload = {k: v for k, v in {
        "name": name, "district_id": district_id, "timezone": timezone, "school_code": school_code
    }.items() if v is not None}
    if not payload:
        console.print("[yellow]Nothing to update[/]")
        raise click.Abort()
    cfg = load_config()
    with client(cfg) as c:
        r = c.put(f"/schools/{school_id}", json=payload, headers={"Content-Type": "application/json"})
        data = _handle_resp(r)
    console.print("[green]Updated[/] ✅")
    show_json(data)

@schools_group.command("delete", help="Delete a school by ID")
@click.argument("school_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirm")
def schools_delete(school_id: str, yes: bool) -> None:
    if not yes and not _confirm_delete("school", school_id):
        console.print("[yellow]Cancelled[/]")
        return
    cfg = load_config()
    with client(cfg) as c:
        r = c.delete(f"/schools/{school_id}")
        _handle_resp(r)
    console.print("[green]Deleted[/] ✅")

# -----------------------------------------------------------------------------
# Interactive menu (unchanged; invoke when no args)
# -----------------------------------------------------------------------------
def menu() -> None:
    cfg = load_config()
    console.print(Panel.fit(
        f"OSSS CLI — API: [cyan]{cfg['api_base']}[/]  |  KC: [cyan]{cfg['kc_base']}[/]/realms/{cfg['kc_realm']}"
    ))
    while True:
        console.print("\n[bold]Main Menu[/]")
        console.print(" 1) Config: show")
        console.print(" 2) Config: from-env")
        console.print(" 3) Auth: login")
        console.print(" 4) Auth: whoami")
        console.print(" 5) Schools: list")
        console.print(" q) Quit")
        choice = input("Select> ").strip().lower()
        try:
            if choice == "1":
                config_show(standalone_mode=False)  # type: ignore
            elif choice == "2":
                config_from_env(standalone_mode=False)  # type: ignore
            elif choice == "3":
                auth_login(standalone_mode=False)  # prompts
            elif choice == "4":
                auth_whoami(standalone_mode=False)  # type: ignore
            elif choice == "5":
                schools_list.callback(limit=50, cursor=None)  # type: ignore
            elif choice in {"q", "quit"}:
                console.print("Bye!")
                return
        except click.Abort:
            pass

def _main():
    if len(sys.argv) == 1:
        menu()
    else:
        cli()

if __name__ == "__main__":
    _main()
