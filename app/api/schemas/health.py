"""Health check API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(..., description="Application health status (e.g. 'ok')")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application semantic version")
    database_connected: bool = Field(..., description="Database connectivity status")
    database_dialect: Optional[str] = Field(
        default=None,
        description="Active metadata database dialect (postgresql or sqlite)",
    )
    storage_backend: Optional[str] = Field(
        default=None,
        description="Active JPG object storage backend (local or r2)",
    )
    timestamp: datetime = Field(..., description="UTC timestamp of the check")

