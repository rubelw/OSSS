# OSSS Data Model — Core Schema Definitions

The `data_model/` directory contains the central **data model definitions** used by the OSSS backend and related services.
This includes database schemas, ORM definitions, and structured entity definitions that represent the core domain of the OSSS platform.

These models support:
- API validation & serialization
- database migrations
- backend business logic
- analytics and reporting pipelines
- AI-driven reasoning over structured data

---

## 🎯 Purpose

This directory provides the canonical source of truth for **persistent entities** in OSSS.  
By defining shared models here, OSSS ensures consistent schema usage across services and allows multiple layers of the system
to reason over data using shared types.

Typical responsibilities of the OSSS data model include:

- defining student, course, enrollment, and administrative entities
- specifying relationships between educational records
- supporting domain rules through metadata and schema constraints
- enabling migration tooling such as Alembic

---

## 📁 What You May Find Here

```text
data_model/
├── base.py         # base ORM configuration, declarative base
├── student.py      # student entities and personal data structures
├── course.py       # course catalog, subjects, and academic offerings
├── enrollment.py   # enrollment logic, grade levels, student-course links
├── staff.py        # staff, personnel, HR relationships
├── schedule.py     # class schedules, bell times, sections
└── __init__.py     # package exports
```

> Actual structure depends on your version of OSSS.  
> Check your local repository for the authoritative list of models.

---

## 🧠 Relationship to OSSS Architecture

```
Frontend (Next.js)
        ↓
Backend (FastAPI)
        ↓
Data Model (schema + relationships)
        ↓
Database (PostgreSQL or compatible)
```

The backend uses models from this directory to:

- validate incoming API requests
- persist and query records
- expose structured OpenAPI schemas
- serve data to frontend applications and orchestration engines

---

## 🚀 Usage Example (SQLAlchemy)

```python
from data_model.student import Student
from sqlalchemy.orm import Session

def lookup_student(db: Session, student_id: str) -> Student | None:
    return (
        db.query(Student)
        .filter(Student.external_id == student_id)
        .first()
    )
```

> Replace `Student` import based on your project structure.

---

## 🧪 Development Notes

- Migrations should import models from here to ensure correct schema generation.
- Changing model definitions may require running migration scripts.
- Downstream service logic should depend on **types**, not internal database state.

---

## 📚 Related Documentation

- `docs/backend/openapi.md` — generated API schema
- `src/OSSS/` — backend using these models
- `src/a2a_server/` — agents that consume structured data

---

## 🧾 License

The OSSS data model is part of the core OSSS project and is covered by the project's main license.
