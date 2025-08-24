from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class RolePermissionOut(ORMBase):
    role_id: str
    permission_id: str
    created_at: datetime
    updated_at: datetime
