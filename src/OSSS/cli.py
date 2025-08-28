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

def humanize(s: str) -> str:
    """Convert snake_case to 'Title Case' labels."""
    return s.replace('_', ' ').replace('-', ' ').strip().title()

def make_role_command(role_name: str):
    """Factory to create a simple command that prints the role's label."""
    label = humanize(role_name)
    @click.command(name=role_name, help=f"{label}")
    def _cmd():
        click.echo(label)
    return _cmd

def _prog_name() -> str:
    # What the user runs on the command line. If you rename this file, the
    # completion snippets will still work as long as you use that new name.
    return os.path.basename(sys.argv[0]) or "cli"

def _envvar_name(prog: str) -> str:
    # Click expects _PROG_COMPLETE=... (PROG uppercased, - → _)
    return f"_{prog.replace('-', '_').upper()}_COMPLETE"


def completion_snippet(shell: str, prog: str) -> str:
    envvar = _envvar_name(prog)
    if shell == "bash":
        return f"""# --- Hardened OSSS Click completion (macOS-safe) ---
        # - Works on bash 3.2 (mac default) and bash 4/5.
        # - If a custom fzf completer (_osss_complete_with_help) is already registered, do nothing.

        if [ -n "$BASH_VERSION" ]; then
          # Skip if our custom fzf completer is in place
          if complete -p {prog} 2>/dev/null | grep -q '_osss_complete_with_help'; then
            :
          else
            # bash 4/5: native Click completion
            if [ "${{BASH_VERSINFO[0]:-3}}" -ge 4 ]; then
              eval "$({envvar}=bash_source {prog})"
            else
              # bash 3.2: strip unsupported bits from Click’s bash script
              eval "$({envvar}=bash_source {prog} | sed -e 's/-o nosort//g' -e '/^compopt /d')"
              # Optional readability tweaks
              bind 'set print-completions-horizontally off'
              bind 'set page-completions on'
              bind 'set show-all-if-ambiguous on'
              bind 'set completion-ignore-case on'
            fi
          fi
        fi
        """
    if shell == "zsh":
        return f'eval "$({envvar}=zsh_source {prog})"'
    if shell == "fish":
        return f"eval ({envvar}=fish_source {prog})"
    if shell in ("powershell", "pwsh"):
        return f'$env:{envvar} = "powershell"; iex (& {prog} | Out-String)'
    raise click.ClickException(f"Unsupported shell: {shell}")


def detect_shell() -> str | None:
    sh = os.environ.get("SHELL", "").lower()
    if "zsh" in sh:
        return "zsh"
    if "bash" in sh:
        return "bash"
    # fish sets SHELL as fish; on Windows, prefer powershell
    if "fish" in sh:
        return "fish"
    if os.name == "nt":
        return "powershell"
    return None


def rc_path_for(shell: str) -> Path:
    home = Path.home()
    if shell == "bash":
        # Favor .bashrc; on macOS interactive shells may use .bash_profile
        return home / ".bashrc"
    if shell == "zsh":
        return home / ".zshrc"
    if shell == "fish":
        return home / ".config" / "fish" / "config.fish"
    if shell in ("powershell", "pwsh"):
        # Typical user profile script
        return Path(os.path.expanduser("~/Documents/PowerShell/Microsoft.PowerShell_profile.ps1"))
    # Fallback
    return home / ".profile"


# ------------------------------
# Root CLI
# ------------------------------
@click.group(help="OSSS CLI (Click edition)")
def cli() -> None:
    """Top-level command group."""

# ------------------------------
# Completion utilities (standalone group)
# ------------------------------
@click.group(name="completion", help="Show or install shell completion for this CLI")
def completion_group() -> None:
    pass


@completion_group.command("show", help="Print the completion snippet for your shell")
@click.option("--shell", type=click.Choice(["bash", "zsh", "fish", "powershell", "pwsh"]), default=None,
              help="Shell to target (auto-detected if omitted)")
def completion_show(shell: str | None) -> None:
    if shell is None:
        shell = detect_shell() or "bash"
    prog = _prog_name()
    snippet = completion_snippet(shell, prog)
    click.echo(f"# Add the following line to your shell rc file to enable TAB completion for '{prog}':")
    click.echo(f"#   {rc_path_for(shell)}")
    click.echo(snippet)


@completion_group.command("install", help="Append the completion snippet to your shell rc file")
@click.option("--shell", type=click.Choice(["bash", "zsh", "fish", "powershell", "pwsh"]), default=None,
              help="Shell to target (auto-detected if omitted)")
def completion_install(shell: str | None) -> None:
    if shell is None:
        shell = detect_shell() or "bash"
    prog = _prog_name()
    snippet = completion_snippet(shell, prog)
    rc = rc_path_for(shell)
    rc.parent.mkdir(parents=True, exist_ok=True)
    line = f"\n# OSSS CLI completion for '{prog}'\n{snippet}\n"
    try:
        with rc.open("a", encoding="utf-8") as f:
            f.write(line)
        click.secho(f"✔ Installed completion in {rc}", fg="green")
        click.echo("Open a new shell OR source your rc file to activate it, e.g.:")
        if shell in ("bash", "zsh", "fish"):
            click.echo(f"  source {rc}")
        elif shell in ("powershell", "pwsh"):
            click.echo("  . $PROFILE")
    except Exception as e:
        raise click.ClickException(f"Failed to write completion to {rc}: {e}")




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

# ---------------------------------------------------------------------------
# Top-level: osss (NEW parent for all remaining groups)
# ---------------------------------------------------------------------------
@click.group(name="osss", help="OSSS functional areas (all domain groups are nested here).")
def osss_group():
    pass



# ======================================================================
# 1) Governance & District Executive Leadership
# ======================================================================
@click.group(name="governance_and_district_executive_leadership", help="Governance & District Executive Leadership")
def governance_and_district_executive_leadership_group() -> None:
    pass


@click.group(name="board_governance", help="Board & Governance")
def board_governance_group() -> None:
    pass


@click.group(name="executive_cabinet", help="Executive Cabinet")
def executive_cabinet_group() -> None:
    pass


for r in ["board_chair", "board_vice_chair", "board_clerk", "school_board_member_trustee"]:
    board_governance_group.add_command(make_role_command(r))

for r in [
    "superintendent",
    "head_of_school",
    "deputy_superintendent",
    "associate_superintendent",
    "assistant_superintendent",
    "chief_of_staff",
    "general_counsel",
    "ombudsperson",
    "chief_equity_officer",
    "chief_schools_officer",
    "chief_academic_officer",
]:
    executive_cabinet_group.add_command(make_role_command(r))


# ======================================================================
# 2) School Leadership, Teaching & Learning (Instruction)
# ======================================================================
@click.group(name="school_leadership_teaching_learning_instruction", help="School Leadership, Teaching & Learning (Instruction)")
def school_leadership_teaching_learning_instruction_group() -> None:
    pass


@click.group(name="school_leadership", help="School Leadership")
def school_leadership_group() -> None:
    pass


@click.group(name="teachers_classroom_roles", help="Teachers & Classroom Roles")
def teachers_classroom_roles_group() -> None:
    pass


@click.group(name="instructional_support_library_media", help="Instructional Support & Library/Media")
def instructional_support_library_media_group() -> None:
    pass


@click.group(name="curriculum_pd_accountability_instruction", help="Curriculum, PD & Accountability (Instruction-Facing)")
def curriculum_pd_accountability_instruction_group() -> None:
    pass


for r in [
    "principal",
    "assistant_principal",
    "associate_principal",
    "vice_principal",
    "dean_of_students",
    "dean_of_academics",
    "grade_level_dean",
    "head_of_upper_school",
    "head_of_middle_school",
    "head_of_lower_school",
    "director_of_residential_life",
]:
    school_leadership_group.add_command(make_role_command(r))

for r in [
    "classroom_teacher",
    "elementary_teacher",
    "middle_school_teacher",
    "high_school_teacher",
    "art_teacher",
    "music_teacher",
    "theater_teacher",
    "physical_education_teacher",
    "health_teacher",
    "world_languages_teacher",
    "computer_science_teacher",
    "cte_teacher",
    "early_childhood_teacher",
    "reading_interventionist",
    "math_interventionist",
    "substitute_teacher",
    "long_term_substitute",
    "teacher_resident",
    "student_teacher",
    "instructional_fellow",
]:
    teachers_classroom_roles_group.add_command(make_role_command(r))

for r in ["instructional_coach", "literacy_coach", "math_coach", "mentor_teacher", "media_specialist", "teacher_librarian", "librarian"]:
    instructional_support_library_media_group.add_command(make_role_command(r))

for r in [
    "director_of_curriculum_and_instruction",
    "instructional_materials_coordinator",
    "textbook_coordinator",
    "professional_development_coordinator",
    "teacher_induction_coordinator",
    "accreditation_coordinator",
    "ib_coordinator",
    "ap_coordinator",
]:
    curriculum_pd_accountability_instruction_group.add_command(make_role_command(r))


# ======================================================================
# 3) Student Services, Health & Special Education
# ======================================================================
@click.group(name="student_services_health_special_education", help="Student Services, Health & Special Education")
def student_services_health_special_education_group() -> None:
    pass


@click.group(name="counseling_health_attendance", help="Counseling, Health & Attendance")
def counseling_health_attendance_group() -> None:
    pass


@click.group(name="special_education_related_services", help="Special Education & Related Services")
def special_education_related_services_group() -> None:
    pass


@click.group(name="assessment_testing_ops", help="Assessment & Testing Operations")
def assessment_testing_ops_group() -> None:
    pass


@click.group(name="front_office_student_support", help="Front Office Student Support")
def front_office_student_support_group() -> None:
    pass


for r in [
    "school_counselor",
    "guidance_counselor",
    "school_social_worker",
    "family_liaison",
    "school_nurse",
    "health_aide",
    "attendance_officer",
    "truancy_officer",
    "mckinney_vento_liaison",
    "foster_care_liaison",
    "behavior_support_coach",
    "restorative_practices_coordinator",
    "mtss_coordinator",
    "rti_coordinator",
    "registrar",
    "records_clerk",
    "testing_and_assessment_coordinator",
    "college_counselor",
    "financial_aid_advisor",
]:
    counseling_health_attendance_group.add_command(make_role_command(r))

for r in [
    "director_of_special_education",
    "special_education_teacher",
    "sped_case_manager",
    "school_psychologist",
    "speech_language_pathologist",
    "occupational_therapist",
    "certified_occupational_therapy_assistant",
    "physical_therapist",
    "physical_therapist_assistant",
    "board_certified_behavior_analyst",
    "behavior_interventionist",
    "vision_specialist",
    "orientation_and_mobility_specialist",
    "deaf_hard_of_hearing_teacher",
    "504_coordinator",
    "sped_compliance_coordinator",
    "paraprofessional",
    "instructional_aide",
    "teachers_aide",
    "sign_language_interpreter",
    "transition_specialist",
    "vocational_specialist",
]:
    special_education_related_services_group.add_command(make_role_command(r))

for r in ["testing_site_manager"]:
    assessment_testing_ops_group.add_command(make_role_command(r))

for r in ["school_secretary", "administrative_assistant", "office_manager", "receptionist", "attendance_clerk", "student_services_clerk", "health_office_clerk"]:
    front_office_student_support_group.add_command(make_role_command(r))


# ======================================================================
# 4) Student Life, Activities & Enrichment
# ======================================================================
@click.group(name="student_life_activities_enrichment", help="Student Life, Activities & Enrichment")
def student_life_activities_enrichment_group() -> None:
    pass


@click.group(name="athletics_activities", help="Athletics & Activities")
def athletics_activities_group() -> None:
    pass


@click.group(name="performing_arts", help="Performing Arts")
def performing_arts_group() -> None:
    pass


@click.group(name="early_childhood_out_of_school", help="Early Childhood & Out-of-School Time")
def early_childhood_out_of_school_group() -> None:
    pass


@click.group(name="faith_based", help="Faith-Based (if applicable)")
def faith_based_group() -> None:
    pass


@click.group(name="alternative_virtual_cte_international", help="Alternative/Virtual/CTE & International")
def alternative_virtual_cte_international_group() -> None:
    pass


for r in [
    "activities_director",
    "athletics_director",
    "assistant_athletics_director",
    "head_coach",
    "assistant_coach",
    "athletic_trainer",
    "strength_and_conditioning_coach",
    "club_sponsor",
    "activity_sponsor",
    "robotics_coach",
    "debate_coach",
    "esports_coach",
    "yearbook_advisor",
    "student_government_advisor",
]:
    athletics_activities_group.add_command(make_role_command(r))

for r in ["performing_arts_director", "theater_director", "band_director", "choir_director"]:
    performing_arts_group.add_command(make_role_command(r))

for r in [
    "director_of_early_childhood",
    "preschool_teacher",
    "preschool_assistant",
    "before_school_program_director",
    "after_school_program_director",
    "extended_day_coordinator",
    "summer_school_coordinator",
    "enrichment_coordinator",
]:
    early_childhood_out_of_school_group.add_command(make_role_command(r))

for r in ["chaplain", "campus_minister", "religion_teacher", "theology_teacher", "service_learning_coordinator"]:
    faith_based_group.add_command(make_role_command(r))

for r in [
    "alternative_education_director",
    "virtual_online_program_director",
    "cte_director",
    "pathways_coordinator",
    "apprenticeship_coordinator",
    "international_student_program_director",
    "homestay_coordinator",
]:
    alternative_virtual_cte_international_group.add_command(make_role_command(r))


# ======================================================================
# 5) Operations, Facilities, Transportation, Nutrition & Safety
# ======================================================================
@click.group(name="operations_facilities_transportation_nutrition_safety", help="Operations, Facilities, Transportation, Nutrition & Safety")
def operations_facilities_transportation_nutrition_safety_group() -> None:
    pass


@click.group(name="facilities_maintenance", help="Facilities & Maintenance")
def facilities_maintenance_group() -> None:
    pass


@click.group(name="transportation_fleet", help="Transportation & Fleet")
def transportation_fleet_group() -> None:
    pass


@click.group(name="nutrition_services", help="Nutrition Services")
def nutrition_services_group() -> None:
    pass


@click.group(name="safety_security", help="Safety & Security")
def safety_security_group() -> None:
    pass


for r in [
    "chief_operations_officer",
    "director_of_facilities",
    "facilities_manager",
    "plant_manager",
    "maintenance_technician",
    "electrician",
    "plumber",
    "hvac_technician",
    "carpenter",
    "painter",
    "locksmith",
    "groundskeeper",
    "irrigation_technician",
    "custodial_supervisor",
    "custodian",
    "porter",
    "night_lead",
    "warehouse_receiving",
    "inventory_specialist",
    "energy_manager",
    "sustainability_manager",
    "print_shop_manager",
    "mailroom_clerk",
]:
    facilities_maintenance_group.add_command(make_role_command(r))

for r in [
    "director_of_transportation",
    "routing_scheduling_coordinator",
    "dispatcher",
    "bus_driver",
    "activity_driver",
    "bus_aide_monitor",
    "fleet_manager",
    "mechanic",
    "diesel_technician",
    "shop_foreman",
    "crossing_guard",
]:
    transportation_fleet_group.add_command(make_role_command(r))

for r in [
    "director_of_nutrition_services",
    "food_service_director",
    "cafeteria_manager",
    "kitchen_manager",
    "cook",
    "prep_cook",
    "baker",
    "cashier_point_of_sale_operator",
    "dietitian",
    "nutritionist",
]:
    nutrition_services_group.add_command(make_role_command(r))

for r in [
    "director_of_safety_security",
    "emergency_management_director",
    "school_resource_officer",
    "campus_police_officer",
    "security_guard",
    "campus_supervisor",
    "emergency_preparedness_coordinator",
]:
    safety_security_group.add_command(make_role_command(r))


# ======================================================================
# 6) Central Services: Finance, HR, Technology & Data, Comms/Engagement, Enrollment
# ======================================================================
@click.group(name="central_services_finance_hr_tech_data_comms_enrollment", help="Central Services: Finance, HR, Tech & Data, Comms/Engagement, Enrollment")
def central_services_finance_hr_tech_data_comms_enrollment_group() -> None:
    pass


@click.group(name="finance_grants_compliance", help="Finance, Grants & Compliance")
def finance_grants_compliance_group() -> None:
    pass


@click.group(name="human_resources", help="Human Resources")
def human_resources_group() -> None:
    pass


@click.group(name="technology_data", help="Technology & Data")
def technology_data_group() -> None:
    pass


@click.group(name="communications_engagement_development_marketing", help="Comms, Engagement, Development & Marketing")
def communications_engagement_development_marketing_group() -> None:
    pass


@click.group(name="enrollment_admissions", help="Enrollment & Admissions")
def enrollment_admissions_group() -> None:
    pass


for r in [
    "chief_financial_officer",
    "business_manager",
    "controller",
    "accountant",
    "payroll_manager",
    "payroll_specialist",
    "accounts_payable_specialist",
    "accounts_receivable_specialist",
    "grants_manager",
    "grant_writer",
    "federal_programs_director",
    "purchasing_director",
    "buyer",
    "risk_manager",
    "insurance_coordinator",
    "compliance_officer",
    "records_retention_manager",
    "e_rate_coordinator",
    "archivist",
]:
    finance_grants_compliance_group.add_command(make_role_command(r))

for r in [
    "chief_human_resources_officer",
    "human_resources_director",
    "hr_manager",
    "hr_generalist",
    "recruiter",
    "benefits_manager",
    "benefits_specialist",
]:
    human_resources_group.add_command(make_role_command(r))

for r in [
    "chief_information_officer",
    "chief_technology_officer",
    "director_of_technology",
    "it_director",
    "network_administrator",
    "systems_administrator",
    "cloud_administrator",
    "server_administrator",
    "information_security_officer",
    "database_administrator",
    "help_desk_manager",
    "help_desk_technician",
    "field_technician",
    "web_administrator",
    "webmaster",
    "av_media_technician",
    "sis_administrator",
    "data_engineer",
    "data_analyst",
    "etl_developer",
    "director_of_data_analytics",
    "sis_clerk",
    "data_clerk",
]:
    technology_data_group.add_command(make_role_command(r))

for r in [
    "chief_communications_officer",
    "communications_director",
    "public_relations_director",
    "media_relations_manager",
    "family_engagement_coordinator",
    "community_engagement_coordinator",
    "translation_services_coordinator",
    "interpreter_services_coordinator",
    "alumni_relations_director",
    "advancement_development_director",
    "annual_giving_manager",
    "capital_campaign_manager",
    "major_gifts_officer",
    "marketing_director",
    "marketing_manager",
    "graphic_designer",
    "social_media_manager",
    "volunteer_coordinator",
]:
    communications_engagement_development_marketing_group.add_command(make_role_command(r))

for r in ["admissions_director", "enrollment_director", "financial_aid_director"]:
    enrollment_admissions_group.add_command(make_role_command(r))


# ------------------------------
# Compose the tree (now that everything exists)
# ------------------------------
cli.add_command(completion_group)

#1) OSSS
cli.add_command(osss_group)
# nest domain groups under osss
osss_group.add_command(governance_and_district_executive_leadership_group)
osss_group.add_command(operations_facilities_transportation_nutrition_safety_group)
osss_group.add_command(school_leadership_teaching_learning_instruction_group)
osss_group.add_command(student_life_activities_enrichment_group)
osss_group.add_command(student_services_health_special_education_group)
osss_group.add_command(central_services_finance_hr_tech_data_comms_enrollment_group)


# 1) Governance
governance_and_district_executive_leadership_group.add_command(board_governance_group)
governance_and_district_executive_leadership_group.add_command(executive_cabinet_group)

# 2) Instruction
school_leadership_teaching_learning_instruction_group.add_command(school_leadership_group)
school_leadership_teaching_learning_instruction_group.add_command(teachers_classroom_roles_group)
school_leadership_teaching_learning_instruction_group.add_command(instructional_support_library_media_group)
school_leadership_teaching_learning_instruction_group.add_command(curriculum_pd_accountability_instruction_group)

# 3) Student Services
student_services_health_special_education_group.add_command(counseling_health_attendance_group)
student_services_health_special_education_group.add_command(special_education_related_services_group)
student_services_health_special_education_group.add_command(assessment_testing_ops_group)
student_services_health_special_education_group.add_command(front_office_student_support_group)

# 4) Student Life
student_life_activities_enrichment_group.add_command(athletics_activities_group)
student_life_activities_enrichment_group.add_command(performing_arts_group)
student_life_activities_enrichment_group.add_command(early_childhood_out_of_school_group)
student_life_activities_enrichment_group.add_command(faith_based_group)
student_life_activities_enrichment_group.add_command(alternative_virtual_cte_international_group)

# 5) Operations
operations_facilities_transportation_nutrition_safety_group.add_command(facilities_maintenance_group)
operations_facilities_transportation_nutrition_safety_group.add_command(transportation_fleet_group)
operations_facilities_transportation_nutrition_safety_group.add_command(nutrition_services_group)
operations_facilities_transportation_nutrition_safety_group.add_command(safety_security_group)

# 6) Central Services
central_services_finance_hr_tech_data_comms_enrollment_group.add_command(finance_grants_compliance_group)
central_services_finance_hr_tech_data_comms_enrollment_group.add_command(human_resources_group)
central_services_finance_hr_tech_data_comms_enrollment_group.add_command(technology_data_group)
central_services_finance_hr_tech_data_comms_enrollment_group.add_command(communications_engagement_development_marketing_group)
central_services_finance_hr_tech_data_comms_enrollment_group.add_command(enrollment_admissions_group)

def _main():
    if len(sys.argv) == 1:
        menu()
    else:
        cli()

if __name__ == "__main__":
    _main()
