from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from datetime import date, datetime
from typing import Dict, List, Tuple



# Pull the shims from your app (preferred)
try:
    from app.models.base import GUID, JSONB, TSVectorType  # GUID/JSONB TypeDecorator; TSVectorType for PG tsvector
except Exception:
    import uuid
    from sqlalchemy.types import TypeDecorator, CHAR

    class GUID(TypeDecorator):
        impl = CHAR
        cache_ok = True
        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import UUID as PGUUID
                return dialect.type_descriptor(PGUUID(as_uuid=True))
            return dialect.type_descriptor(sa.CHAR(36))
        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(str(value))
            return str(value)
        def process_result_value(self, value, dialect):
            return None if value is None else uuid.UUID(value)

    try:
        from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
    except Exception:
        PGJSONB = None

    class JSONB(TypeDecorator):
        impl = sa.JSON
        cache_ok = True
        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql" and PGJSONB is not None:
                return dialect.type_descriptor(PGJSONB())
            return dialect.type_descriptor(sa.JSON())

    try:
        from sqlalchemy.dialects.postgresql import TSVECTOR as PG_TSVECTOR
        class TSVectorType(PG_TSVECTOR):
            pass
    except Exception:
        class TSVectorType(sa.Text):
            pass

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



# Canonical subject lists for common K-12 departments
# Each item is (name, code)
SUBJECTS_BY_CANON: Dict[str, List[Tuple[str, str]]] = {
    "english_language_arts": [
        ("English 9", "ELA9"),
        ("English 10", "ELA10"),
        ("English 11", "ELA11"),
        ("English 12", "ELA12"),
        ("Literature", "LIT"),
        ("Writing/Composition", "COMP"),
        ("Journalism", "JOUR"),
        ("Speech/Communications", "SPEECH"),
        ("Reading", "READ"),
    ],
    "mathematics": [
        ("Math 6", "MATH6"),
        ("Pre-Algebra", "PREALG"),
        ("Algebra I", "ALG1"),
        ("Geometry", "GEOM"),
        ("Algebra II", "ALG2"),
        ("Precalculus", "PRECALC"),
        ("Calculus", "CALC"),
        ("Statistics", "STATS"),
    ],
    "science": [
        ("Earth Science", "EARTH"),
        ("Physical Science", "PHYSCI"),
        ("Biology", "BIO"),
        ("Chemistry", "CHEM"),
        ("Physics", "PHYS"),
        ("Environmental Science", "ENVS"),
        ("Anatomy & Physiology", "ANAT"),
    ],
    "social_studies": [
        ("World History", "WHIST"),
        ("U.S. History", "USHIST"),
        ("Government/Civics", "GOV"),
        ("Economics", "ECON"),
        ("Geography", "GEOG"),
        ("Psychology", "PSYCH"),
        ("Sociology", "SOC"),
    ],
    "world_languages": [
        ("Spanish I", "SPAN1"),
        ("Spanish II", "SPAN2"),
        ("French I", "FREN1"),
        ("French II", "FREN2"),
        ("German I", "GERM1"),
        ("German II", "GERM2"),
    ],
    "fine_arts": [
        ("Art I", "ART1"),
        ("Art II", "ART2"),
        ("Drawing", "DRAW"),
        ("Painting", "PAINT"),
        ("Sculpture", "SCULPT"),
        ("Digital Art", "DIGART"),
    ],
    "music": [
        ("Band", "BAND"),
        ("Choir", "CHOIR"),
        ("Orchestra", "ORCH"),
        ("Jazz Band", "JAZZ"),
        ("Music Theory", "MUSTH"),
    ],
    "physical_education": [
        ("PE 9", "PE9"),
        ("PE 10", "PE10"),
        ("Weight Training", "WEIGHTS"),
        ("Lifetime Fitness", "FIT"),
    ],
    "health": [
        ("Health", "HEALTH"),
        ("Nutrition & Wellness", "NUTR"),
    ],
    "cte": [
        ("Business Essentials", "BUS"),
        ("Accounting", "ACCT"),
        ("Marketing", "MKTG"),
        ("Entrepreneurship", "ENTR"),
        ("Computer Applications", "COMPAPP"),
        ("Engineering/PLTW", "ENGR"),
        ("Robotics", "ROBOT"),
        ("Culinary Arts", "CUL"),
        ("Construction Trades", "CONST"),
        ("Automotive Technology", "AUTO"),
    ],
    "computer_science": [
        ("Intro to Computer Science", "ICS"),
        ("AP Computer Science Principles", "APCSP"),
        ("AP Computer Science A", "APCSA"),
        ("Web Development", "WEBDEV"),
        ("Cybersecurity", "CYBER"),
        ("Data Science", "DATASCI"),
    ],
    "special_education": [
        ("Resource English", "R-ELA"),
        ("Resource Math", "R-MATH"),
        ("Study Skills", "STUDY"),
    ],
    "esl_ell": [
        ("ELL Beginner", "ELL1"),
        ("ELL Intermediate", "ELL2"),
        ("ELL Advanced", "ELL3"),
    ],
    "family_consumer_science": [
        ("Child Development", "CHILD"),
        ("Foods & Nutrition", "FOODS"),
        ("Family & Consumer Science", "FCS"),
    ],
    "agriculture": [
        ("Agricultural Science", "AGSCI"),
        ("Animal Science", "ANSCI"),
        ("Plant Science", "PLANT"),
    ],
    # Fallback if we recognize nothing else
    "general": [
        ("General Studies", "GEN"),
    ],
}


def _canonical_key(dept_name: str) -> str:
    """Map department names (varied spellings) to canonical keys above."""
    n = dept_name.strip().lower()

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
    if any_in(["fine art", "visual art", "art "] ) or n == "art":
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

    # If department name itself looks like a subject (e.g., "Business")
    if "business" in n:
        return "cte"

    return "general"


def upgrade() -> None:
    conn = op.get_bind()

    # Make sure subjects table exists (defensive)
    # and gather existing departments
    departments = conn.execute(
        text("SELECT id, name FROM departments")
    ).fetchall()

    if not departments:
        return  # nothing to seed

    # Preload existing subjects to avoid duplicates
    existing = conn.execute(
        text("SELECT department_id, name FROM subjects WHERE department_id IS NOT NULL")
    ).fetchall()
    existing_set = {(str(r.department_id), r.name.strip().lower()) for r in existing}

    insert_stmt = text(
        """
        INSERT INTO subjects (department_id, name, code, created_at, updated_at)
        VALUES (:dept_id, :name, :code, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
    )

    total = 0
    for dept_id, dept_name in departments:
        key = _canonical_key(dept_name or "")
        subjects = SUBJECTS_BY_CANON.get(key, SUBJECTS_BY_CANON["general"])

        for subj_name, subj_code in subjects:
            sig = (str(dept_id), subj_name.strip().lower())
            if sig in existing_set:
                continue
            conn.execute(insert_stmt, {"dept_id": str(dept_id), "name": subj_name, "code": subj_code})
            existing_set.add(sig)
            total += 1

    if total:
        conn.execute(text("COMMIT"))  # end implicit transaction if needed


def downgrade() -> None:
    conn = op.get_bind()
    departments = conn.execute(text("SELECT id, name FROM departments")).fetchall()
    if not departments:
        return

    # Build the set of (dept_id, subject_name) we seeded and delete precisely those
    to_delete = []
    for dept_id, dept_name in departments:
        key = _canonical_key(dept_name or "")
        subjects = SUBJECTS_BY_CANON.get(key, SUBJECTS_BY_CANON["general"])
        for subj_name, _ in subjects:
            to_delete.append((str(dept_id), subj_name))

    if not to_delete:
        return

    # Delete in chunks to avoid huge IN clauses (probably small anyway)
    delete_stmt = text(
        "DELETE FROM subjects WHERE department_id = :dept_id AND name = :name"
    )
    for dept_id, name in to_delete:
        conn.execute(delete_stmt, {"dept_id": dept_id, "name": name})

    conn.execute(text("COMMIT"))