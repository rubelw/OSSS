
# OSSS Generated FastAPI Resources

Drop-in, dynamic CRUD routers for every SQLAlchemy model under `OSSS.db.models`.

## What this provides
- `create_router_for_model(model, ...)` – build a CRUD router for a single model.
- `generate_routers_for_all_models(prefix_base="/api")` – auto-discovers models and returns routers.
- Routers return simple JSON dicts via a lightweight serializer (no Pydantic schema coupling).
- Endpoints exposed per model:
  - `GET {prefix}` – list with `skip`, `limit`
  - `GET {prefix}/{id}` – retrieve by primary key
  - `POST {prefix}` – create (body is a JSON object of columns)
  - `PATCH {prefix}/{id}` – partial update (body fields are applied if present)
  - `PUT {prefix}/{id}` – full replace (upsert if `allow_put_create=True` when building router)
  - `DELETE {prefix}/{id}` – delete (idempotent)

## Quick start

```python
# app/main.py (or OSSS/api/app.py)
from fastapi import FastAPI
from generated_resources.register_all import generate_routers_for_all_models

app = FastAPI()

for name, router in generate_routers_for_all_models(prefix_base="/api"):
    app.include_router(router)
```

By default, the code attempts to import a DB session dependency from one of:
- `OSSS.db.session:get_session`
- `OSSS.db.session:get_db`
- `OSSS.db.base:get_session`
- `OSSS.db.base:get_db`

If none are found, you'll get a clear runtime error. In that case, provide your own dependency:

```python
# Suppose you expose `get_session()` in your project:
from OSSS.db.session import get_session
from generated_resources.factory import create_router_for_model
from OSSS.db.models import YourModel

router = create_router_for_model(YourModel, prefix="/api/yourmodels", get_db=get_session)
app.include_router(router)
```

## Notes & Limitations
- Only single-column primary keys are supported out of the box. Composite PK models are skipped.
- Payloads are filtered to known model columns; unknown fields are ignored.
- Responses are plain dicts; if you already have Pydantic schemas, you can wrap the routes or adapt the serializer.
- Relationships are not expanded to avoid recursion; customize `serialization.to_dict` if needed.
- For models with server defaults or automatic timestamps, you can POST with partial payloads.
- Authorization, validation, and business rules are **not** included – add FastAPI `Depends(...)` as needed.
```
