#!/usr/bin/env python3
"""
List routes from a FastAPI application.

Usage:
    python list_fastapi_endpoints.py OSSS.main.app
    python list_fastapi_endpoints.py OSSS.main:app
"""

from importlib import import_module
import os
import argparse
from fastapi import FastAPI
from typing import Iterable

# -------------------------------------------------------------------
# Set default Keycloak settings so Settings() does not raise.
# Override these with real values in your shell environment or .env
# when running in production.
os.environ.setdefault("KEYCLOAK_BASE_URL", "https://your-keycloak-host/")
os.environ.setdefault("KEYCLOAK_REALM", "osss")
os.environ.setdefault("KEYCLOAK_AUDIENCE", "osss-api")
# For private clients that use the OAuth2 password grant, supply a client_id and secret
os.environ.setdefault("KEYCLOAK_CLIENT_ID", "your-client-id")
os.environ.setdefault("KEYCLOAK_CLIENT_SECRET", "your-client-secret")
# -------------------------------------------------------------------

def list_routes(app: FastAPI) -> Iterable[str]:
    for route in app.routes:
        methods = ",".join(sorted(route.methods - {"HEAD", "OPTIONS"}))
        yield f"{methods:7s} {route.path} -> {route.name}"

def load_app(app_path: str) -> FastAPI:
    """
    Load a FastAPI app from either 'module:app' or dotted 'module.submodule.app'.
    """
    if ":" in app_path:
        module_name, app_var = app_path.split(":", 1)
    else:
        *module_parts, app_var = app_path.split(".")
        module_name = ".".join(module_parts)

    module = import_module(module_name)
    app = getattr(module, app_var, None)
    if not isinstance(app, FastAPI):
        raise RuntimeError(f"{app_path!r} does not resolve to a FastAPI instance")
    return app

def main() -> None:
    parser = argparse.ArgumentParser(description="List FastAPI routes.")
    parser.add_argument(
        "app_path",
        help="Dotted or colon‑separated path to FastAPI app (e.g. 'OSSS.main.app' or 'OSSS.main:app')",
    )
    args = parser.parse_args()
    app = load_app(args.app_path)
    print("METHOD  PATH                     -> NAME")
    print("----------------------------------------------")
    for line in list_routes(app):
        print(line)

if __name__ == "__main__":
    main()
