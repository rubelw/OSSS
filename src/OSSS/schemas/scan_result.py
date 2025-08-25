# src/OSSS/schemas/scan_result.py
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ScanResultCreate(BaseModel):
    """Schema for creating a scan result (POST/PUT)."""
    ok: bool = Field(..., description="True if the scan was valid/accepted")
    ticket_id: Optional[str] = Field(None, description="Ticket ID if recognized")
    status: Optional[str] = Field(None, description="Ticket status after scan (e.g., issued, checked_in, void)")
    message: str = Field(..., description="Human-readable outcome message")


class ScanResult(BaseModel):
    """Response after attempting to scan/validate a ticket."""
    ok: bool = Field(..., description="True if the scan was valid/accepted")
    ticket_id: Optional[str] = Field(None, description="Ticket ID if recognized")
    status: Optional[str] = Field(None, description="Ticket status after scan (e.g., issued, checked_in, void)")
    message: str = Field(..., description="Human-readable outcome message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "ok": True,
                "ticket_id": "0f5b3a5b-2e8b-4f5d-8f61-f0b8e0f2a4e1",
                "status": "checked_in",
                "message": "Ticket accepted. Welcome!",
            }
        }
    }
