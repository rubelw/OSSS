#!/usr/bin/env python3

# cli.py
import os
import re
import json
from typing import List, Optional, Dict
import asyncio

import typer
import httpx
from fastapi import FastAPI
from fastapi.routing import APIRoute

def remove_auth_middleware(app):
    try:
        from starlette.middleware.authentication import AuthenticationMiddleware
        before = len(app.user_middleware)
        app.user_middleware = [m for m in app.user_middleware if m.cls is not AuthenticationMiddleware]
        if before != len(app.user_middleware):
            app.middleware_stack = app.build_middleware_stack()
    except Exception:
        pass

def override_auth_for_route(app, route: APIRoute) -> None:
    # start clean so old bad overrides don't linger
    app.dependency_overrides.clear()

    # tokens / users returned by overrides (NO ARGS!)
    def _fake_user():
        return {"sub": "cli-dev", "roles": ["admin"], "name": "CLI Dev User"}
    def _ok():
        return None
    def _token():
        return "dev-token"

    # security classes
    try:
        from fastapi.security import (
            OAuth2PasswordBearer, OAuth2AuthorizationCodeBearer,
            HTTPBearer, APIKeyHeader, APIKeyQuery, APIKeyCookie
        )
        from fastapi.security.http import HTTPAuthorizationCredentials
        SEC_CLASSES = (
            OAuth2PasswordBearer, OAuth2AuthorizationCodeBearer,
            HTTPBearer, APIKeyHeader, APIKeyQuery, APIKeyCookie
        )
        def _creds():
            # HTTPBearer returns this object
            return HTTPAuthorizationCredentials(scheme="Bearer", credentials="dev-token")
    except Exception:
        SEC_CLASSES = tuple()  # type: ignore
        _creds = None  # type: ignore

    # common app-level helpers by dotted path (map to NO-ARG funcs)
    for dotted in [
        "app.auth.require_realm_roles",
        "app.auth.get_current_user",
        "app.dependencies.get_current_user",
        "app.security.get_current_user",
        "app.security.require_admin",
        "app.api.dependencies.auth.get_current_active_user",
    ]:
        try:
            mod, name = dotted.rsplit(".", 1)
            dep = getattr(__import__(mod, fromlist=[name]), name)
            app.dependency_overrides[dep] = _fake_user if ("user" in name or "claims" in name) else _ok
        except Exception:
            pass

    # walk ONLY this route’s dependency graph (track by id to avoid unhashable Dependant)
    seen_ids: Set[int] = set()

    def walk(dep):
        if dep is None:
            return
        key = id(dep)
        if key in seen_ids:
            return
        seen_ids.add(key)

        call = getattr(dep, "call", None)
        if call is not None:
            # FastAPI security primitives
            if SEC_CLASSES and isinstance(call, SEC_CLASSES):
                if _creds and isinstance(call, HTTPBearer):  # type: ignore[name-defined]
                    app.dependency_overrides[call] = _creds
                else:
                    app.dependency_overrides[call] = _token
            else:
                # Heuristic for app auth/claims/permission guards
                mod = (getattr(call, "__module__", "") or "").lower()
                name = (getattr(call, "__name__", "") or call.__class__.__name__).lower()
                looks_auth = any(k in name for k in (
                    "auth","bearer","oauth","token","current_user","active_user","claims",
                    "require","permission","role","api_key"
                )) or mod.startswith(("app.auth", "app.security"))
                if looks_auth:
                    app.dependency_overrides[call] = _fake_user if ("user" in name or "claims" in name or "current" in name) else _ok

        for sub in getattr(dep, "dependencies", []) or []:
            walk(sub)

    walk(route.dependant)
def disable_security_overrides(app: FastAPI) -> None:
    """
    DEV ONLY. Remove auth middleware and override security deps so requests are allowed.
    """

    # A) Remove Starlette AuthenticationMiddleware (and similar) if present
    try:
        from starlette.middleware.authentication import AuthenticationMiddleware
        old_len = len(app.user_middleware)
        app.user_middleware = [m for m in app.user_middleware if m.cls is not AuthenticationMiddleware]
        if os.getenv("CLI_DEBUG") == "1":
            removed = old_len - len(app.user_middleware)
            print(f"[cli] removed {removed} AuthenticationMiddleware item(s)")
        # Rebuild middleware stack
        app.middleware_stack = app.build_middleware_stack()
    except Exception:
        pass

    # B) Collect all dependency callables used by routes
    def collect_calls() -> Set[object]:
        calls: Set[object] = set()
        def walk(dep):
            if not dep:
                return
            call = getattr(dep, "call", None)
            if call is not None:
                calls.add(call)
            for sub in getattr(dep, "dependencies", []) or []:
                walk(sub)
        for route in app.routes:
            if isinstance(route, APIRoute):
                walk(route.dependant)
        return calls

    calls = collect_calls()

    # C) Prepare fake returns
    fake_user = {"sub": "cli-dev", "roles": ["admin"], "name": "CLI Dev User"}

    # D) Override known app-level auth helpers by dotted path (add yours if needed)
    for dotted in [
        "app.auth.require_realm_roles",
        "app.auth.get_current_user",
        "app.dependencies.get_current_user",
        "app.security.get_current_user",
        "app.security.require_admin",
        "app.api.dependencies.auth.get_current_active_user",
    ]:
        try:
            modname, attr = dotted.rsplit(".", 1)
            mod = __import__(modname, fromlist=[attr])
            dep = getattr(mod, attr)
            app.dependency_overrides[dep] = (lambda *_a, **_k: fake_user) if "user" in attr else (lambda *_a, **_k: None)
        except Exception:
            pass

    # E) Override FastAPI security primitives and anything that *looks* like auth
    try:
        from fastapi.security import (
            OAuth2PasswordBearer, HTTPBearer, APIKeyHeader, APIKeyQuery, APIKeyCookie
        )
        try:
            from fastapi.security.http import HTTPAuthorizationCredentials
        except Exception:
            HTTPAuthorizationCredentials = None  # type: ignore
    except Exception:
        OAuth2PasswordBearer = HTTPBearer = APIKeyHeader = APIKeyQuery = APIKeyCookie = object  # type: ignore
        HTTPAuthorizationCredentials = None  # type: ignore

    for call in calls:
        try:
            # Security schemes (instances are callables)
            if isinstance(call, (OAuth2PasswordBearer, APIKeyHeader, APIKeyQuery, APIKeyCookie)):
                app.dependency_overrides[call] = lambda *_a, **_k: "dev-token"
                continue
            if isinstance(call, HTTPBearer):
                if HTTPAuthorizationCredentials:
                    app.dependency_overrides[call] = lambda *_a, **_k: HTTPAuthorizationCredentials(scheme="Bearer", credentials="dev-token")
                else:
                    app.dependency_overrides[call] = lambda *_a, **_k: {"scheme": "Bearer", "credentials": "dev-token"}
                continue

            # Heuristic: anything that sounds like auth/permissions
            mod = getattr(call, "__module__", "") or ""
            name = (getattr(call, "__name__", "") or call.__class__.__name__).lower()
            looks_auth = any(k in name for k in ("auth", "token", "current_user", "active_user", "require", "permission", "role", "bearer", "oauth", "api_key", "security"))
            if looks_auth or mod.startswith(("app.auth", "app.security")):
                app.dependency_overrides[call] = (lambda *_a, **_k: fake_user) if ("user" in name or "current" in name) else (lambda *_a, **_k: None)
        except Exception:
            pass

    if os.getenv("CLI_DEBUG") == "1":
        print(f"[cli] dependency_overrides count: {len(app.dependency_overrides)}")
        for k in list(app.dependency_overrides.keys())[:50]:
            print(" - override:", getattr(k, "__module__", ""), getattr(k, "__name__", k.__class__.__name__))
# ── Import your FastAPI app ────────────────────────────────────────────────────
from app.main import app as fastapi_app  # ← change if your app is elsewhere

cli = typer.Typer(help="Auto-generated CLI for FastAPI endpoints", no_args_is_help=True)


# ── Dev-only: disable security dependencies in-process ─────────────────────────
def disable_security_overrides(app: FastAPI) -> None:
    """
    DEV ONLY. Overrides auth/security dependencies so requests run as 'allowed'.
    Use with --insecure or CLI_INSECURE=1. Never enable in production.
    """
    # Example: role-based guard in app.auth
    try:
        from app.auth import require_realm_roles  # type: ignore
        app.dependency_overrides[require_realm_roles] = lambda *a, **kw: None
    except Exception:
        pass

    # Example: current user dependency
    try:
        from app.dependencies import get_current_user  # type: ignore
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": "cli-dev",
            "roles": ["admin"],
            "name": "CLI Dev User",
        }
    except Exception:
        pass

    # Optional: add more dotted paths you use for auth
    for dotted in [
        "app.security.get_current_user",
        "app.security.require_admin",
        "app.api.dependencies.auth.get_current_active_user",
    ]:
        try:
            modname, funcname = dotted.rsplit(".", 1)
            mod = __import__(modname, fromlist=[funcname])
            dep = getattr(mod, funcname)
            app.dependency_overrides[dep] = lambda *a, **kw: None
        except Exception:
            pass


# ── Helpers ───────────────────────────────────────────────────────────────────
def path_to_cmd_name(path: str) -> str:
    # e.g. "/users/{user_id}/posts" -> "users_user_id_posts"
    name = path.strip("/").replace("/", "_")
    name = re.sub(r"[{}]", "", name) or "root"
    return name


def parse_kv_pairs(pairs: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for item in pairs:
        if "=" not in item:
            raise typer.BadParameter(f"Expected key=value, got: {item}")
        k, v = item.split("=", 1)
        out[k] = v
    return out


def fill_path(path_template: str, path_params: Dict[str, str]) -> str:
    def repl(m):
        key = m.group(1)
        if key not in path_params:
            raise typer.BadParameter(f"Missing path param: {key}")
        return str(path_params[key])

    return re.sub(r"{(\w+)}", repl, path_template)


# ── Command factory ────────────────────────────────────────────────────────────
def make_command(app: FastAPI, route: APIRoute, method: str):
    cmd_name = f"{method.lower()}_{path_to_cmd_name(route.path)}"

    def _cmd(
        path: List[str] = typer.Option(
            [],
            "-p",
            "--path",
            help="Path params as key=value (repeatable).",
        ),
        query: List[str] = typer.Option(
            [],
            "-q",
            "--query",
            help="Query params as key=value (repeatable).",
        ),
        header: List[str] = typer.Option(
            [],
            "-H",
            "--header",
            help="Headers as key=value (repeatable).",
        ),
        json_data: Optional[str] = typer.Option(
            None,
            "--json",
            help="Inline JSON string for request body.",
        ),
        json_file: Optional[str] = typer.Option(
            None,
            "--json-file",
            help="Path to JSON file for request body.",
        ),
        base_url: str = typer.Option(
            "http://localhost:8000",
            "--base-url",
            help="Remote server base URL (used with --remote).",
        ),
        in_process: bool = typer.Option(
            True,
            "--in-process/--remote",
            help="Call the ASGI app in-process (no server) or over HTTP.",
        ),
        insecure: bool = typer.Option(
            False,
            "--insecure",
            help="DEV ONLY (in-process): disable auth/security dependencies.",
        ),
        token: Optional[str] = typer.Option(
            None,
            "--token",
            help="Authorization token (adds 'Authorization: Bearer <token>').",
        ),
        pretty: bool = typer.Option(
            True,
            "--pretty/--raw",
            help="Pretty-print JSON responses.",
        ),
        timeout: float = typer.Option(
            30.0,
            "--timeout",
            help="HTTP timeout in seconds.",
        ),
    ):
        path_params = parse_kv_pairs(path)
        query_params = parse_kv_pairs(query)
        headers = parse_kv_pairs(header)

        # Token support (env fallback)
        if token is None:
            token = os.getenv("API_TOKEN")
        if token and not any(k.lower() == "authorization" for k in headers):
            headers["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"

        body = None
        if json_file:
            with open(json_file, "r", encoding="utf-8") as f:
                body = json.load(f)
        elif json_data:
            body = json.loads(json_data)

        url_path = fill_path(route.path, path_params)

        if in_process:
            if insecure or os.getenv("CLI_INSECURE") == "1":
                remove_auth_middleware(app)
                override_auth_for_route(app, route)
                # ensure a bearer header exists in case anything still checks headers
                if not any(k.lower() == "authorization" for k in headers):
                    headers["Authorization"] = "Bearer dev-token"

            async def do_request():
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver",
                                             timeout=timeout) as aclient:
                    request_kwargs = dict(url=url_path, headers=headers or None, params=query_params or None)
                    if method in ("POST", "PUT", "PATCH"):
                        request_kwargs["json"] = body
                    resp = await aclient.request(method, **request_kwargs)
                    typer.echo(f"[{resp.status_code}] {resp.request.method} {resp.request.url}")
                    ct = resp.headers.get("content-type", "")
                    if pretty and "application/json" in ct:
                        try:
                            typer.echo(json.dumps(resp.json(), indent=2, ensure_ascii=False))
                        except Exception:
                            typer.echo(resp.text)
                    else:
                        typer.echo(resp.text)

            asyncio.run(do_request())
            return  # IMPORTANT: don’t fall through to any `client.close()`
        else:

            request_kwargs = dict(url=url_path, headers=headers or None, params=query_params or None)

            if method in ("POST", "PUT", "PATCH"):
                request_kwargs["json"] = body

            with httpx.Client(base_url=base_url, timeout=timeout) as client:

                resp = client.request(method, **request_kwargs)

                typer.echo(f"[{resp.status_code}] {resp.request.method} {resp.request.url}")

                ct = resp.headers.get("content-type", "")

                if pretty and "application/json" in ct:

                    try:

                        typer.echo(json.dumps(resp.json(), indent=2, ensure_ascii=False))

                    except Exception:

                        typer.echo(resp.text)

                else:

                    typer.echo(resp.text)

        try:
            request_kwargs = dict(
                url=url_path,
                headers=headers or None,
                params=query_params or None,
            )
            if method in ("POST", "PUT", "PATCH"):
                request_kwargs["json"] = body

            resp = client.request(method, **request_kwargs)

            typer.echo(f"[{resp.status_code}] {resp.request.method} {resp.request.url}")
            ct = resp.headers.get("content-type", "")
            if pretty and "application/json" in ct:
                try:
                    typer.echo(json.dumps(resp.json(), indent=2, ensure_ascii=False))
                except Exception:
                    typer.echo(resp.text)
            else:
                typer.echo(resp.text)
        finally:
            client.close()

    # Register at root
    cli.command(name=cmd_name, help=f"{method} {route.path}")(_cmd)
    return cmd_name, _cmd


# ── Build CLI from FastAPI routes ──────────────────────────────────────────────
def build_cli(app: FastAPI) -> None:
    groups: Dict[str, typer.Typer] = {}

    def group_for(tag: str) -> typer.Typer:
        tag_norm = tag.lower().replace(" ", "_")
        if tag_norm not in groups:
            groups[tag_norm] = typer.Typer(help=f"Commands for tag: {tag_norm}")
            cli.add_typer(groups[tag_norm], name=tag_norm)
        return groups[tag_norm]

    for r in app.routes:
        if not isinstance(r, APIRoute):
            continue

        methods = sorted(m for m in r.methods if m in {"GET", "POST", "PUT", "PATCH", "DELETE"})
        if not methods:
            continue

        for m in methods:
            cmd_name, cmd_fn = make_command(app, r, m)
            tag = (r.tags[0] if r.tags else "misc")
            group_for(tag).command(name=cmd_name, help=f"{m} {r.path}")(cmd_fn)


# ── Utility: list discovered endpoints ─────────────────────────────────────────
@cli.command("list")
def list_cmd():
    """List discovered endpoints and their tag groups."""
    found = []
    for r in fastapi_app.routes:
        if isinstance(r, APIRoute):
            methods = ",".join(sorted(m for m in r.methods if m in {"GET", "POST", "PUT", "PATCH", "DELETE"}))
            tag = (r.tags[0] if r.tags else "misc")
            found.append((tag, methods, r.path))
    for tag, methods, path in sorted(found):
        typer.echo(f"[{tag}] {methods:20s} {path}")


# ── Build commands now ─────────────────────────────────────────────────────────
build_cli(fastapi_app)

if __name__ == "__main__":
    cli()

