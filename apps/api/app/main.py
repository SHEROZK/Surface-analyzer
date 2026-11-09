from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Surface Analyzer API",
    version="0.1.0",
    description="API for tile and surface visualization projects.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime


class Capability(BaseModel):
    id: str
    name: str
    status: str
    description: str


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"name": "Surface Analyzer API", "docs": "/docs", "health": "/health"}


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="surface-analyzer-api",
        timestamp=datetime.now(timezone.utc),
    )


@app.get("/api/v1/capabilities", response_model=list[Capability], tags=["platform"])
async def capabilities() -> list[Capability]:
    """Expose the initial product capabilities and implementation status."""
    items: list[dict[str, Any]] = [
        {"id": "catalog", "name": "Tile catalog", "status": "planned", "description": "Manage tile products and material maps."},
        {"id": "projects", "name": "Visualization projects", "status": "planned", "description": "Create projects and upload room photographs."},
        {"id": "surface-analysis", "name": "Surface analysis", "status": "planned", "description": "Detect surfaces and allow editable masks and polygons."},
        {"id": "photo-renderer", "name": "Photo renderer", "status": "planned", "description": "Apply tile materials with perspective, scale, rotation, and grout controls."},
        {"id": "camera-preview", "name": "Live camera preview", "status": "planned", "description": "Preview materials through a live camera overlay."},
    ]
    return [Capability(**item) for item in items]
