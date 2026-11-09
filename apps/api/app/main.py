import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Base, SessionLocal, engine
from .models import Project, ProjectAsset, Tenant, TileProduct

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024

app = FastAPI(
    title="Surface Analyzer API",
    version="0.2.0",
    description="Tile catalog, room projects, uploads, and visualization workspace API.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_default_tenant(db: Session) -> Tenant:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == "default-workspace"))
    if tenant is None:
        tenant = Tenant(name="My Workspace", slug="default-workspace")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    return tenant


async def save_image(upload: UploadFile) -> tuple[str, int]:
    if upload.content_type not in ALLOWED_IMAGES:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WebP image.")
    content = await upload.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 15 MB or smaller.")
    extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[upload.content_type]
    key = f"{uuid.uuid4().hex}{extension}"
    (UPLOAD_DIR / key).write_bytes(content)
    return key, len(content)


@app.get("/", tags=["system"])
async def root():
    return {"name": "Surface Analyzer API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "surface-analyzer-api", "timestamp": datetime.now(timezone.utc)}


@app.get("/api/v1/capabilities", tags=["platform"])
async def capabilities():
    return [
        {"id": "catalog", "name": "Tile catalog", "status": "available", "description": "Create and manage tile products and material images."},
        {"id": "projects", "name": "Visualization projects", "status": "available", "description": "Create projects and upload room photographs."},
        {"id": "surface-analysis", "name": "Surface selection", "status": "mvp", "description": "Manually outline the target surface in the visualizer."},
        {"id": "photo-renderer", "name": "Photo renderer", "status": "mvp", "description": "Preview a repeating tile texture inside a selected polygon."},
        {"id": "camera-preview", "name": "Live camera preview", "status": "planned", "description": "Live camera material preview is planned after the photo workflow."},
    ]


@app.get("/api/v1/products", tags=["catalog"])
def list_products(db: Session = Depends(get_db)):
    tenant = get_default_tenant(db)
    products = db.scalars(select(TileProduct).where(TileProduct.tenant_id == tenant.id).order_by(TileProduct.created_at.desc())).all()
    return [{
        "id": str(p.id), "name": p.name, "sku": p.sku, "description": p.description,
        "width_mm": p.width_mm, "height_mm": p.height_mm, "finish": p.finish,
        "material_url": f"/uploads/{p.material_asset_key}" if p.material_asset_key else None,
    } for p in products]


@app.post("/api/v1/products", tags=["catalog"])
async def create_product(
    name: str = Form(...),
    sku: str | None = Form(None),
    description: str | None = Form(None),
    width_mm: int | None = Form(None),
    height_mm: int | None = Form(None),
    finish: str | None = Form(None),
    material: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Product name is required.")
    if width_mm is not None and width_mm <= 0 or height_mm is not None and height_mm <= 0:
        raise HTTPException(status_code=422, detail="Tile dimensions must be positive.")
    tenant = get_default_tenant(db)
    material_key = None
    if material is not None:
        material_key, _ = await save_image(material)
    product = TileProduct(
        tenant_id=tenant.id, name=name, sku=sku or None, description=description or None,
        width_mm=width_mm, height_mm=height_mm, finish=finish or None,
        material_asset_key=material_key,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return {"id": str(product.id), "name": product.name, "sku": product.sku, "width_mm": product.width_mm,
            "height_mm": product.height_mm, "finish": product.finish,
            "material_url": f"/uploads/{material_key}" if material_key else None}


@app.delete("/api/v1/products/{product_id}", tags=["catalog"])
def delete_product(product_id: uuid.UUID, db: Session = Depends(get_db)):
    tenant = get_default_tenant(db)
    product = db.scalar(select(TileProduct).where(TileProduct.id == product_id, TileProduct.tenant_id == tenant.id))
    if product is None:
        raise HTTPException(status_code=404, detail="Tile product not found.")
    db.delete(product)
    db.commit()
    return {"deleted": True}


@app.get("/api/v1/projects", tags=["projects"])
def list_projects(db: Session = Depends(get_db)):
    tenant = get_default_tenant(db)
    projects = db.scalars(select(Project).where(Project.tenant_id == tenant.id).order_by(Project.created_at.desc())).all()
    return [{
        "id": str(p.id), "name": p.name, "status": p.status,
        "room_image_url": next((f"/uploads/{a.storage_key}" for a in p.assets if a.asset_type == "room"), None),
        "created_at": p.created_at,
    } for p in projects]


@app.post("/api/v1/projects", tags=["projects"])
def create_project(name: str = Form(...), db: Session = Depends(get_db)):
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Project name is required.")
    tenant = get_default_tenant(db)
    project = Project(tenant_id=tenant.id, name=name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": str(project.id), "name": project.name, "status": project.status}


@app.post("/api/v1/projects/{project_id}/room-image", tags=["projects"])
async def upload_room_image(project_id: uuid.UUID, image: UploadFile = File(...), db: Session = Depends(get_db)):
    tenant = get_default_tenant(db)
    project = db.scalar(select(Project).where(Project.id == project_id, Project.tenant_id == tenant.id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    key, size = await save_image(image)
    asset = ProjectAsset(project_id=project.id, asset_type="room", storage_key=key, mime_type=image.content_type,
                         metadata_json={"original_name": image.filename, "size_bytes": size})
    db.add(asset)
    db.commit()
    return {"asset_id": str(asset.id), "room_image_url": f"/uploads/{key}", "size_bytes": size}


@app.get("/api/v1/projects/{project_id}", tags=["projects"])
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db)):
    tenant = get_default_tenant(db)
    project = db.scalar(select(Project).where(Project.id == project_id, Project.tenant_id == tenant.id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {
        "id": str(project.id), "name": project.name, "status": project.status,
        "assets": [{"id": str(a.id), "type": a.asset_type, "url": f"/uploads/{a.storage_key}"} for a in project.assets],
    }
