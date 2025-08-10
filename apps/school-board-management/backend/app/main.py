from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routers import meetings, policies
from .auth import current_user

app = FastAPI(title="OSSS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meetings.router)
app.include_router(policies.router)

@app.get("/me")
def me(user: dict = Depends(current_user)):
    return {
        "sub": user.get("sub"),
        "email": user.get("email"),
        "roles": user.get("realm_access", {}).get("roles", []),
        "aud": user.get("aud")
    }

@app.get("/")
def health():
    return {"ok": True}
