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
from .models import ProductAsset, Project, ProjectAsset, Tenant, TileProduct

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
        {"id": "catalog", "name": "Multi-category surface catalog", "status": "available", "description": "Manage tiles, stone, wood, wallpaper, countertops, paint, panels and pavers with multiple product assets."},
        {"id": "projects", "name": "Visualization projects", "status": "available", "description": "Create projects and upload room photographs."},
        {"id": "surface-analysis", "name": "Automatic surface detection", "status": "mvp", "description": "OpenCV proposes a floor boundary from the room photo; users can refine the outline."},
        {"id": "photo-renderer", "name": "Photo renderer", "status": "mvp", "description": "Preview material textures inside an automatically detected or manually refined surface polygon; perspective-aware rendering is in development."},
        {"id": "camera-preview", "name": "Live camera preview", "status": "planned", "description": "Live camera material preview is planned after the photo workflow."},
    ]


@app.get("/api/v1/products", tags=["catalog"])
def list_products(db: Session = Depends(get_db)):
    tenant = get_default_tenant(db)
    products = db.scalars(select(TileProduct).where(TileProduct.tenant_id == tenant.id).order_by(TileProduct.created_at.desc())).all()
    return [serialize_product(p) for p in products]


def serialize_product(product: TileProduct):
    assets = [{
        "id": str(asset.id), "role": asset.role, "url": "/uploads/" + asset.storage_key,
        "name": asset.original_name, "mime_type": asset.mime_type, "sort_order": asset.sort_order,
    } for asset in product.assets]
    texture = next((a["url"] for a in assets if a["role"] == "texture"), None)
    legacy_texture = "/uploads/" + product.material_asset_key if product.material_asset_key else None
    return {
        "id": str(product.id), "name": product.name, "sku": product.sku, "description": product.description,
        "category": product.category, "brand": product.brand, "collection": product.collection,
        "width_mm": product.width_mm, "height_mm": product.height_mm, "finish": product.finish,
        "material_url": texture or legacy_texture, "assets": assets,
    }


@app.post("/api/v1/products", tags=["catalog"])
async def create_product(
    name: str = Form(...),
    sku: str | None = Form(None),
    description: str | None = Form(None),
    width_mm: int | None = Form(None),
    height_mm: int | None = Form(None),
    finish: str | None = Form(None),
    category: str = Form("tile"),
    brand: str | None = Form(None),
    collection: str | None = Form(None),
    material: UploadFile | None = File(None),
    texture: UploadFile | None = File(None),
    gallery: list[UploadFile] | None = File(None),
    texture_faces: list[UploadFile] | None = File(None),
    normal_map: UploadFile | None = File(None),
    roughness_map: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Product name is required.")
    if width_mm is not None and width_mm <= 0 or height_mm is not None and height_mm <= 0:
        raise HTTPException(status_code=422, detail="Tile dimensions must be positive.")
    tenant = get_default_tenant(db)
    allowed_categories = {"tile", "natural-stone", "wood-flooring", "wallpaper", "countertop", "paint", "panel", "paver", "other"}
    category = category.strip().lower()
    if category not in allowed_categories:
        raise HTTPException(status_code=422, detail="Unsupported material category.")
    product = TileProduct(
        tenant_id=tenant.id, name=name, sku=sku or None, description=description or None,
        category=category, brand=brand or None, collection=collection or None,
        width_mm=width_mm, height_mm=height_mm, finish=finish or None,
    )
    db.add(product)
    db.flush()
    uploads = []
    if texture is not None:
        uploads.append(("texture", texture))
    elif material is not None:
        uploads.append(("texture", material))
    if gallery:
        uploads.extend(("gallery", image) for image in gallery)
    if texture_faces:
        uploads.extend(("texture_face", image) for image in texture_faces)
    if normal_map is not None:
        uploads.append(("normal", normal_map))
    if roughness_map is not None:
        uploads.append(("roughness", roughness_map))
    for order, (role, upload) in enumerate(uploads):
        key, size = await save_image(upload)
        db.add(ProductAsset(
            product_id=product.id, role=role, storage_key=key,
            original_name=(upload.filename or "")[:255], mime_type=upload.content_type,
            sort_order=order, metadata_json={"size_bytes": size},
        ))
        if role == "texture":
            product.material_asset_key = key
    db.commit()
    db.refresh(product)
    return serialize_product(product)


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


@app.post("/api/v1/projects/{project_id}/detect-surface", tags=["surface-analysis"])
def detect_surface(project_id: uuid.UUID, mode: str = "floor", db: Session = Depends(get_db)):
    """Return an automatic floor-boundary proposal in normalized image coordinates."""
    if mode != "floor":
        raise HTTPException(status_code=422, detail="Only floor detection is currently supported.")
    tenant = get_default_tenant(db)
    project = db.scalar(select(Project).where(Project.id == project_id, Project.tenant_id == tenant.id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    room_asset = db.scalar(select(ProjectAsset).where(
        ProjectAsset.project_id == project.id, ProjectAsset.asset_type == "room"
    ).order_by(ProjectAsset.created_at.desc()))
    if room_asset is None:
        raise HTTPException(status_code=404, detail="Upload a room photo first.")
    try:
        import cv2
        import numpy as np
        image = cv2.imread(str(UPLOAD_DIR / room_asset.storage_key))
        if image is None:
            raise ValueError("Image could not be decoded.")
        original_h, original_w = image.shape[:2]
        if min(original_w, original_h) < 120:
            raise HTTPException(status_code=422, detail="Room photo is too small for surface detection.")
        factor = min(1.0, 960.0 / max(original_w, original_h))
        if factor < 1:
            image = cv2.resize(image, (int(original_w * factor), int(original_h * factor)), interpolation=cv2.INTER_AREA)
        h, w = image.shape[:2]
        mask = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)
        mask[int(h * .48):, :] = cv2.GC_PR_FGD
        mask[int(h * .90):, :] = cv2.GC_FGD
        mask[:int(h * .40), :] = cv2.GC_BGD
        cv2.ellipse(mask, (w // 2, int(h * .78)), (max(8, int(w * .16)), max(8, int(h * .12))),
                    0, 0, 360, cv2.GC_FGD, -1)
        bg_model = np.zeros((1, 65), np.float64)
        fg_model = np.zeros((1, 65), np.float64)
        cv2.grabCut(image, mask, None, bg_model, fg_model, 4, cv2.GC_INIT_WITH_MASK)
        binary = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")
        binary[:int(h * .42), :] = 0
        count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
        candidates = []
        for label in range(1, count):
            x, y, cw, ch, area = stats[label]
            if y + ch >= int(h * .94) and area > h * w * .025:
                candidates.append((area, label))
        if not candidates:
            raise HTTPException(status_code=422, detail="A clear floor boundary was not found. Try a wider room photo or outline it manually.")
        area, label = max(candidates)
        component = np.where(labels == label, 255, 0).astype("uint8")
        component = cv2.morphologyEx(component, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour = max(contours, key=cv2.contourArea)
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, max(2.0, perimeter * .008), True).reshape(-1, 2)
        if len(approx) < 3:
            raise HTTPException(status_code=422, detail="The floor boundary was too ambiguous to outline.")
        points = [{"x": round(float(x) / w, 5), "y": round(float(y) / h, 5)} for x, y in approx]
        area_ratio = float(area) / float(h * w)
        bottom_ratio = float(np.count_nonzero(component[int(h * .94):, :])) / float(max(1, int(h * .06) * w))
        confidence = max(.15, min(.82, .25 + min(area_ratio, .65) * .55 + bottom_ratio * .18))
        return {"mode": mode, "points": points, "confidence": round(confidence, 2),
                "area_ratio": round(area_ratio, 3), "method": "opencv-grabcut-floor-prior"}
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=503, detail="Automatic detection is unavailable because the vision dependency is not installed.")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Automatic detection failed: {str(exc)[:160]}")


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
