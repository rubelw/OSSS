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
    "api_base": os.getenv("OSSS_API_BASE", "http://localhost:8000"),
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
def config_set_base(api_base: str = typer.Argument(..., help="e.g. http://localhost:8000")):
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

@app.command("menu")
def menu():
    cfg = load_config()
    console.print(Panel.fit(f"OSSS CLI — API: [cyan]{cfg['api_base']}[/]"))
    while True:
        console.print(
            "\n[bold]Menu[/]\n"
            "1) List schools\n"
            "2) Get school\n"
            "3) Create school\n"
            "4) Update school\n"
            "5) Delete school\n"
            "c) Config\n"
            "q) Quit"
        )
        choice = Prompt.ask("Select", default="1")
        try:
            if choice == "1":
                schools_list()
            elif choice == "2":
                sid = Prompt.ask("School ID")
                schools_get(sid)
            elif choice == "3":
                name = Prompt.ask("Name")
                district_id = Prompt.ask("District ID")
                tz = Prompt.ask("Timezone", default="")
                code = Prompt.ask("School Code", default="")
                schools_create(name=name, district_id=district_id,
                               timezone=(tz or None), school_code=(code or None))
            elif choice == "4":
                sid = Prompt.ask("School ID")
                console.print("Press Enter to skip a field")
                name = Prompt.ask("Name", default="")
                district_id = Prompt.ask("District ID", default="")
                tz = Prompt.ask("Timezone", default="")
                code = Prompt.ask("School Code", default="")
                schools_update(
                    school_id=sid,
                    name=(name or None),
                    district_id=(district_id or None),
                    timezone=(tz or None),
                    school_code=(code or None),
                )
            elif choice == "5":
                sid = Prompt.ask("School ID")
                schools_delete(sid, yes=False)
            elif choice.lower() == "c":
                _config_menu()
            elif choice.lower() == "q":
                console.print("Bye!")
                break
            else:
                console.print("[yellow]Unknown choice[/]")
        except SystemExit:
            pass
        except Exception as e:
            console.print(f"[red]Error:[/] {e}")

def _config_menu():
    cfg = load_config()
    console.print(Panel.fit(json.dumps(cfg, indent=2), title="Current Config"))
    console.print("1) Set API base\n2) Set token\nb) Back")
    ch = Prompt.ask("Select", default="b")
    if ch == "1":
        base = Prompt.ask("API base", default=cfg["api_base"])
        cfg["api_base"] = base.rstrip("/")
        save_config(cfg)
        console.print("[green]Saved[/]")
    elif ch == "2":
        token = Prompt.ask("Token (stored locally)", password=True)
        cfg["token"] = token
        save_config(cfg)
        console.print("[green]Saved[/]")

def _main():
    if len(sys.argv) == 1:
        menu()
    else:
        app()

if __name__ == "__main__":
    _main()
