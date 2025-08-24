# src/OSSS/schemas/scan_request.py
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    """Request payload to scan/validate a ticket QR code."""
    qr_code: str = Field(..., description="QR token encoded on the ticket")
    location: Optional[str] = Field(
        None,
        description="Optional location or gate identifier where the scan occurred",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "qr_code": "QRCODE-EXAMPLE-XYZ",
                "location": "Main Gate A",
            }
        }
    }
