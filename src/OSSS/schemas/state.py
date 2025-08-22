# src/OSSS/schemas/state.py
from pydantic import BaseModel, ConfigDict

class StateOut(BaseModel):
    code: str
    name: str
    model_config = ConfigDict(from_attributes=True)
