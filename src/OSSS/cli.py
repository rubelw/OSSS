#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
import json, os
from pathlib import Path
from importlib import resources as pkg_resources  # Python 3.9+

# Minimal built-in fallback so the menu always loads
EMBEDDED_DEFAULT_MENU = {
    "title": "OSSS CLI",
    "header": "OSSS CLI — API: {api_base}",
    "menu": [
        {"key": "1", "label": "List schools", "action": "schools_list"},
        {"key": "2", "label": "Get school", "action": "schools_get", "params": [{"name": "school_id", "prompt": "School ID"}]},
        {"key": "3", "label": "Create school", "action": "schools_create",
         "params": [
            {"name": "name", "prompt": "Name"},
            {"name": "district_id", "prompt": "District ID"},
            {"name": "timezone", "prompt": "Timezone", "default": "", "none_if_empty": True},
            {"name": "school_code", "prompt": "School Code", "default": "", "none_if_empty": True}
         ]},
        {"key": "4", "label": "Update school", "action": "schools_update",
         "params": [
            {"name": "school_id", "prompt": "School ID"},
            {"name": "name", "prompt": "Name", "default": "", "none_if_empty": True},
            {"name": "district_id", "prompt": "District ID", "default": "", "none_if_empty": True},
            {"name": "timezone", "prompt": "Timezone", "default": "", "none_if_empty": True},
            {"name": "school_code", "prompt": "School Code", "default": "", "none_if_empty": True}
         ]},
        {"key": "5", "label": "Delete school", "action": "schools_delete",
         "params": [{"name": "school_id", "prompt": "School ID"}, {"name": "yes", "value": False}]},
        {"key": "q", "label": "Quit", "action": "quit"}
    ],
    "submenus": {}
}

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore
from tomli_w import dump as toml_dump  # writes TOML

app = typer.Typer(add_completion=False, help="OSSS FastAPI CLI")
cfg_app = typer.Typer(help="Configure API base and auth")
app.add_typer(cfg_app, name="config")

console = Console()
CONFIG_PATH = Path.home() / ".ossscli.toml"

DEFAULTS = {
    "api_base": os.getenv("OSSS_API_BASE", "http://localhost:8081"),
    "token": os.getenv("OSSS_API_TOKEN", ""),
    "timeout": 20,
}

def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("rb") as f:
            data = tomllib.load(f)
    else:
        data = {}
    for k, v in DEFAULTS.items():
        data.setdefault(k, v)
    return data

def save_config(cfg: Dict[str, Any]) -> None:
    with CONFIG_PATH.open("wb") as f:
        toml_dump(cfg, f)

def client(cfg: Dict[str, Any]) -> httpx.Client:
    headers = {}
    if cfg.get("token"):
        headers["Authorization"] = f"Bearer {cfg['token']}"
    return httpx.Client(base_url=cfg["api_base"], headers=headers, timeout=cfg.get("timeout", 20))

def show_json(obj: Any) -> None:
    console.print_json(data=obj if isinstance(obj, (dict, list)) else json.loads(obj))

def show_table(items: list[dict[str, Any]], columns: list[str]) -> None:
    t = Table(show_lines=False)
    for col in columns:
        t.add_column(col)
    for it in items:
        t.add_row(*(str(it.get(c, "")) for c in columns))
    console.print(t)

@cfg_app.command("show")
def config_show():
    cfg = load_config()
    console.print(Panel.fit(json.dumps(cfg, indent=2), title="Config"))

@cfg_app.command("set-base")
def config_set_base(api_base: str = typer.Argument(..., help="e.g. http://localhost:8081")):
    cfg = load_config()
    cfg["api_base"] = api_base.rstrip("/")
    save_config(cfg)
    console.print(f"[green]Saved[/] api_base = {cfg['api_base']}")

@cfg_app.command("set-token")
def config_set_token(token: str = typer.Argument(..., help="Bearer token (Keycloak, etc.)")):
    cfg = load_config()
    cfg["token"] = token
    save_config(cfg)
    console.print(f"[green]Saved[/] token")

# ---- Schools resource (clone this section for other resources) ---- #

schools_app = typer.Typer(help="Manage schools")
app.add_typer(schools_app, name="schools")

def _handle_resp(r: httpx.Response):
    if r.headers.get("content-type","").startswith("application/json"):
        data = r.json()
    else:
        data = r.text
    if r.is_success:
        return data
    msg = data if isinstance(data, str) else json.dumps(data, indent=2)
    console.print(f"[red]HTTP {r.status_code}[/]: {msg}")
    raise typer.Exit(1)

def _confirm_delete(kind: str, ident: Any) -> bool:
    return Confirm.ask(f"Delete {kind} [bold]{ident}[/]?")

@schools_app.command("list")
def schools_list(limit: int = 50, cursor: Optional[str] = None):
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

@schools_app.command("get")
def schools_get(school_id: str):
    cfg = load_config()
    with client(cfg) as c:
        r = c.get(f"/schools/{school_id}")
        data = _handle_resp(r)
    show_json(data)

@schools_app.command("create")
def schools_create(
    name: str = typer.Option(...),
    district_id: str = typer.Option(...),
    timezone: Optional[str] = typer.Option(None),
    school_code: Optional[str] = typer.Option(None),
):
    payload = {"name": name, "district_id": district_id}
    if timezone: payload["timezone"] = timezone
    if school_code: payload["school_code"] = school_code
    cfg = load_config()
    with client(cfg) as c:
        r = c.post("/schools", json=payload, headers={"Content-Type": "application/json"})
        data = _handle_resp(r)
    console.print("[green]Created[/] ✅")
    show_json(data)

@schools_app.command("update")
def schools_update(
    school_id: str,
    name: Optional[str] = typer.Option(None),
    district_id: Optional[str] = typer.Option(None),
    timezone: Optional[str] = typer.Option(None),
    school_code: Optional[str] = typer.Option(None),
):
    payload = {k:v for k,v in {
        "name": name, "district_id": district_id, "timezone": timezone, "school_code": school_code
    }.items() if v is not None}
    if not payload:
        console.print("[yellow]Nothing to update[/]")
        raise typer.Exit(0)
    cfg = load_config()
    with client(cfg) as c:
        r = c.put(f"/schools/{school_id}", json=payload, headers={"Content-Type": "application/json"})
        data = _handle_resp(r)
    console.print("[green]Updated[/] ✅")
    show_json(data)

@schools_app.command("delete")
def schools_delete(school_id: str, yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirm")):
    if not yes and not _confirm_delete("school", school_id):
        raise typer.Exit(0)
    cfg = load_config()
    with client(cfg) as c:
        r = c.delete(f"/schools/{school_id}")
        _handle_resp(r)
    console.print("[green]Deleted[/] ✅")

# ---- Interactive menu ---- #
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Callable

from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

try:
    # Py3.9+ recommended
    import importlib.resources as pkg_resources
except Exception:  # pragma: no cover
    import importlib_resources as pkg_resources  # type: ignore

# Adjust these imports to your actual module paths
# from .api import schools_list, schools_get, schools_create, schools_update, schools_delete
# from .config import load_config, save_config
# from .app import app, console

# ---------- Menu JSON loading ----------

def _expand_placeholders(s: str, cfg: Dict[str, Any]) -> str:
    try:
        return s.format_map({**cfg})
    except Exception:
        return s

def _read_json_file(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_menu_json(cfg):
    # 0) Explicit override via env
    env_path = os.getenv("OSSS_MENU_FILE")
    if env_path and Path(env_path).is_file():
        return _read_json_file(Path(env_path))

    # 1) User config
    user_cfg = Path.home() / ".config" / "osss-cli" / "menu.json"
    if user_cfg.is_file():
        return _read_json_file(user_cfg)

    # 2) Packaged default — resolve current top-level package dynamically
    # Example: if this file is OSSS/cli.py, __package__ might be "OSSS"
    top_pkg = (__package__ or "").split(".", 1)[0] or "OSSS"

    # Try "<top_pkg>.assets/menu.json" then "<top_pkg>/assets/menu.json" by path
    last_err = None
    candidates = [
        f"{top_pkg}.assets",  # package with resources
        top_pkg,              # top package; we'll try joinpath('assets/menu.json')
    ]
    for pkg_name in candidates:
        try:
            files = pkg_resources.files(pkg_name)
            # direct asset
            candidate = files.joinpath("menu.json")
            if candidate.is_file():
                with candidate.open("r", encoding="utf-8") as f:
                    return json.load(f)
            # assets/menu.json
            candidate = files.joinpath("assets").joinpath("menu.json")
            if candidate.is_file():
                with candidate.open("r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            last_err = e

    # 3) Dev fallback: next to this file as ./assets/menu.json
    local = Path(__file__).with_name("assets") / "menu.json"
    if local.is_file():
        return _read_json_file(local)

    # 4) Embedded fallback to guarantee functionality
    return EMBEDDED_DEFAULT_MENU

# ---------- Actions registry ----------

class _QuitMenu(Exception):
    pass

class _BackMenu(Exception):
    pass

def _act_schools_list(**kw):
    return schools_list()

def _act_schools_get(**kw):
    # accept "school_id" or fallback "sid"
    sid = kw.get("school_id") or kw.get("sid")
    return schools_get(sid)

def _act_schools_create(**kw):
    return schools_create(
        name=kw.get("name"),
        district_id=kw.get("district_id"),
        timezone=kw.get("timezone"),
        school_code=kw.get("school_code"),
    )

def _act_schools_update(**kw):
    return schools_update(
        school_id=kw.get("school_id") or kw.get("sid"),
        name=kw.get("name"),
        district_id=kw.get("district_id"),
        timezone=kw.get("timezone"),
        school_code=kw.get("school_code"),
    )

def _act_schools_delete(**kw):
    return schools_delete(kw.get("school_id") or kw.get("sid"), yes=kw.get("yes", False))

def _act_config_set(**kw):
    cfg = load_config()
    # support arbitrary key=value updates, but default to api_base
    key = next((k for k in kw.keys() if k in ("api_base", "api_base_url", "api_base_uri", "api")), "api_base")
    val = kw.get(key)
    if key == "api_base" and isinstance(val, str):
        val = val.rstrip("/")
    cfg[key] = val
    save_config(cfg)
    console.print("[green]Saved[/]")

def _act_config_set_secret(**kw):
    cfg = load_config()
    token = kw.get("token")
    if token is not None:
        cfg["token"] = token
        save_config(cfg)
        console.print("[green]Saved[/]")

def _act_quit(**kw):
    raise _QuitMenu()

def _act_back(**kw):
    raise _BackMenu()


ACTION_REGISTRY: Dict[str, Callable[..., Any]] = {
    "schools_list": _act_schools_list,
    "schools_get": _act_schools_get,
    "schools_create": _act_schools_create,
    "schools_update": _act_schools_update,
    "schools_delete": _act_schools_delete,
    "config_set": _act_config_set,
    "config_set_secret": _act_config_set_secret,
    "quit": _act_quit,
    "back": _act_back,
}


# ---------- Prompt helpers from JSON spec ----------

def _gather_params(params_spec, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    params_spec: list of objects, each may contain:
      - name (str) [required]
      - prompt (str) [optional] -> if present, ask user
      - default (str) [optional] -> rendered via placeholders
      - secret (bool) [optional] -> Prompt with password=True
      - value (Any) [optional] -> constant value (no prompt)
      - none_if_empty (bool) [optional] -> if user enters "", store None
    """
    result: Dict[str, Any] = {}
    for p in params_spec or []:
        name = p["name"]
        if "value" in p:
            result[name] = p["value"]
            continue

        default = p.get("default")
        if isinstance(default, str):
            default = _expand_placeholders(default, cfg)

        if "prompt" in p:
            val = Prompt.ask(
                p["prompt"],
                default=str(default) if default is not None else None,
                password=bool(p.get("secret", False)),
            )
            if p.get("none_if_empty") and (val == "" or val is None):
                val = None
            result[name] = val
        else:
            # no prompt -> use default (possibly None)
            result[name] = default
    return result


def _render_menu(menu_def: Dict[str, Any], cfg: Dict[str, Any]) -> None:
    """
    Renders a menu loop based on a menu definition:
      {
        "title": str,
        "menu": [ {"key": "...", "label": "...", "action": "name" or "submenu": "id", "params": [...] }, ... ]
      }
    """
    title = menu_def.get("title", "Menu")
    while True:
        table = Table(title=title, show_header=False)
        table.add_column("Key", no_wrap=True, style="bold")
        table.add_column("Action")
        for item in menu_def.get("menu", []):
            table.add_row(f"{item['key']})", item["label"])
        console.print(table)

        choice = Prompt.ask("Select", default=str(menu_def.get("default", ""))).strip()
        # find item by key (case-insensitive)
        item = next((i for i in menu_def.get("menu", []) if i["key"].lower() == choice.lower()), None)
        if not item:
            console.print("[yellow]Unknown choice[/]")
            continue

        try:
            if "submenu" in item:
                # descend into submenu
                submenu_id = item["submenu"]
                sub = _MENU_SPEC["submenus"].get(submenu_id)
                if not sub:
                    console.print(f"[red]Submenu not found:[/] {submenu_id}")
                    continue
                _render_menu(sub, cfg)
                continue

            # action
            action = item.get("action")
            if not action:
                console.print("[yellow]No action defined[/]")
                continue

            fn = ACTION_REGISTRY.get(action)
            if not fn:
                console.print(f"[yellow]Unrecognized action:[/] {action}")
                continue

            # collect params (if any)
            params = _gather_params(item.get("params", []), cfg)
            # perform call
            fn(**params)

        except _BackMenu:
            # return to parent menu
            return
        except _QuitMenu:
            raise
        except SystemExit:
            pass
        except Exception as e:
            console.print(f"[red]Error:[/] {e}")


# ---------- Public entrypoint ----------

def menu():
    cfg = load_config()
    # Load spec & render header panel if defined
    global _MENU_SPEC
    _MENU_SPEC = load_menu_json(cfg)

    header = _MENU_SPEC.get("header")
    if isinstance(header, str):
        console.print(Panel.fit(_expand_placeholders(header, cfg)))
    else:
        # fallback to previous header
        console.print(Panel.fit(f"OSSS CLI — API: [cyan]{cfg['api_base']}[/]"))

    try:
        # top-level menu
        top = {
            "title": _MENU_SPEC.get("title", "OSSS CLI"),
            "menu": _MENU_SPEC.get("menu", []),
            "default": _MENU_SPEC.get("default", "1"),
        }
        _render_menu(top, cfg)
    except _QuitMenu:
        console.print("Bye!")


def _main():
    if len(sys.argv) == 1:
        menu()
    else:
        app()


if __name__ == "__main__":
    _main()
