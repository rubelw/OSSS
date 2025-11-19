# src/MetaGPT/metagpt_server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from MetaGPT.roles_registry import ROLE_REGISTRY, DEFAULT_ROLE_NAME


app = FastAPI()


class RunRequest(BaseModel):
    query: str
    role: str | None = None   # e.g. "analyst", "data_interpreter"


class RunResponse(BaseModel):
    role: str
    result: dict | str        # custom roles might return dicts; builtin ones strings


@app.on_event("startup")
async def startup_event():
    """
    Instantiate one role object per role name and store in app.state.
    """
    instances = {}
    for role_name, RoleCls in ROLE_REGISTRY.items():
        instances[role_name] = RoleCls()
    app.state.role_instances = instances


@app.get("/roles")
async def list_roles():
    """
    Simple discovery endpoint – handy for debugging and for the A2A layer.
    """
    return {"roles": sorted(ROLE_REGISTRY.keys())}


@app.post("/run", response_model=RunResponse)
async def run(req: RunRequest):
    role_name = req.role or DEFAULT_ROLE_NAME
    instances = app.state.role_instances

    if role_name not in instances:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role_name}")

    agent = instances[role_name]
    result = await agent.run(req.query)

    # Make sure the result is JSON-serializable
    if not isinstance(result, (str, dict, list, int, float, bool, type(None))):
        result = str(result)

    return RunResponse(role=role_name, result=result)
