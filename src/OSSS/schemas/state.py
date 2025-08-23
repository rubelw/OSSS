from __future__ import annotations
from typing import Optional

from .base import ORMModel


class StateBase(ORMModel):
    code: str
    name: str


class StateCreate(StateBase):
    pass


class StateUpdate(ORMModel):
    name: Optional[str] = None


class StateOut(StateBase):
    pass
