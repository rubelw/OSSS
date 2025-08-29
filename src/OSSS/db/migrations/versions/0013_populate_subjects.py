from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from pathlib import Path
import json

# --- Alembic identifiers ---
revision = "0013_populate_subjects"
down_revision = "0012_populate_departments"
branch_labels = None
depends_on = None

# ---- Timestamp helpers ----
def _timestamps():
    return (
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

# -------- helpers --------
def _get_subjects_path() -> Path:
    """
    Resolve the path to subjects.json.
    Allows Alembic arg override, e.g.:
      alembic upgrade head -x subjects_json=/path/to/subjects.json
    """
    from alembic import context

    x = context.get_x_argument(as_dictionary=True)
    p = x.get("subjects_json") or "subjects.json"
    path = Path(p)
    if not path.is_file():
        # Fallback to the migration’s directory if a bare name was provided
        here = Path(__file__).resolve().parent
        alt = here / path.name
        if alt.is_file():
            return alt
        raise FileNotFoundError(f"subjects.json not found at '{path}' or '{alt}'. "
                                f"Pass -x subjects_json=/abs/path/subjects.json")
    return path

def _load_subjects_json(path: Path) -> dict[str, list[tuple[str, str]]]:
    """
    Load subjects.json and normalize to:
      { canon_key: [(name, code), ...], ... }
    Accepts either [{"name":..., "code":...}, ...] or [["Name","CODE"], ...].
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, list[tuple[str, str]]] = {}
    for key, items in raw.items():
        norm: list[tuple[str, str]] = []
        for it in items or []:
            if isinstance(it, dict):
                n, c = it.get("name"), it.get("code")
            else:
                # assume 2-tuple/list
                n, c = (it[0], it[1]) if isinstance(it, (list, tuple)) and len(it) >= 2 else (None, None)
            if n and c:
                norm.append((str(n), str(c)))
        if norm:
            out[str(key)] = norm
    if not out:
        raise ValueError("subjects.json contained no valid subjects.")
    return out

def _canonical_key(dept_name: str) -> str:
    """Map department names (varied spellings) to canonical keys present in subjects.json."""
    n = (dept_name or "").strip().lower()

    def any_in(subs: list[str]) -> bool:
        return any(s in n for s in subs)

    if any_in(["english", "language arts", "ela"]):
        return "english_language_arts"
    if any_in(["math", "mathematic"]):
        return "mathematics"
    if "science" in n and not any_in(["computer", "ag"]):
        return "science"
    if any_in(["social studies", "history", "gov", "civics", "economics"]):
        return "social_studies"
    if any_in(["world language", "spanish", "french", "german", "latin", "chinese"]):
        return "world_languages"
    if any_in(["fine art", "visual art", "art "]) or n == "art":
        return "fine_arts"
    if any_in(["music", "band", "choir", "orchestra", "jazz"]):
        return "music"
    if any_in(["physical education", "pe "]) or n == "pe":
        return "physical_education"
    if "health" in n:
        return "health"
    if any_in(["cte", "career", "technical education", "industrial tech", "trade"]):
        return "cte"
    if any_in(["computer science", "technology", "information technology", "it "]) or n in {"technology"}:
        return "computer_science"
    if any_in(["special education", "special ed", "sped"]):
        return "special_education"
    if any_in(["esl", "ell", "english learner"]):
        return "esl_ell"
    if any_in(["family and consumer", "family & consumer", "fcs"]):
        return "family_consumer_science"
    if any_in(["agriculture", "ag "]) or n == "agriculture":
        return "agriculture"
    if "business" in n:
        return "cte"
    return "general"

# -------- migration --------
def upgrade() -> None:
    conn = op.get_bind()

    # Load subjects-by-canonical-key from JSON
    subjects_by_canon = _load_subjects_json(_get_subjects_path())

    # Departments present in DB
    departments = conn.execute(text("SELECT id, name FROM departments")).fetchall()
    if not departments:
        return

    # Avoid duplicates on (department_id, name)
    existing = conn.execute(
        text("SELECT department_id, name FROM subjects WHERE department_id IS NOT NULL")
    ).fetchall()
    existing_set = {(str(r.department_id), (r.name or "").strip().lower()) for r in existing}

    insert_stmt = text("""
        INSERT INTO subjects (department_id, name, code, created_at, updated_at)
        VALUES (:dept_id, :name, :code, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """)

    for dept_id, dept_name in departments:
        canon = _canonical_key(dept_name or "")
        subject_list = subjects_by_canon.get(canon, subjects_by_canon.get("general", []))
        for subj_name, subj_code in subject_list:
            sig = (str(dept_id), subj_name.strip().lower())
            if sig in existing_set:
                continue
            conn.execute(insert_stmt, {"dept_id": str(dept_id), "name": subj_name, "code": subj_code})
            existing_set.add(sig)

def downgrade() -> None:
    conn = op.get_bind()

    # Load the same JSON so we only remove what we added
    try:
        subjects_by_canon = _load_subjects_json(_get_subjects_path())
    except Exception:
        # If file is missing now, be conservative and do nothing
        return

    departments = conn.execute(text("SELECT id, name FROM departments")).fetchall()
    if not departments:
        return

    delete_stmt = text("DELETE FROM subjects WHERE department_id = :dept_id AND name = :name")

    for dept_id, dept_name in departments:
        canon = _canonical_key(dept_name or "")
        subject_list = subjects_by_canon.get(canon, subjects_by_canon.get("general", []))
        for subj_name, _code in subject_list:
            conn.execute(delete_stmt, {"dept_id": str(dept_id), "name": subj_name})
