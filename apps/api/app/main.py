import os
import uuid
import mimetypes
import base64
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from .db import Base, SessionLocal, engine
from .models import ProductAsset, Project, ProjectAsset, Tenant, TileProduct, User
from .auth import create_access_token, decode_access_token, hash_password, verify_password

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
auth_scheme = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    workspace_name: str = Field(min_length=2, max_length=160)
    full_name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=1, max_length=128)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Security(auth_scheme), db: Session = Depends(get_db)) -> User:
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise HTTPException(status_code=401, detail='Sign in to access this workspace.', headers={'WWW-Authenticate': 'Bearer'})
    try:
        claims = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(claims['sub'])
        tenant_id = uuid.UUID(claims['tid'])
    except (ValueError, KeyError):
        raise HTTPException(status_code=401, detail='Invalid or expired access token.', headers={'WWW-Authenticate': 'Bearer'})
    user = db.scalar(select(User).where(User.id == user_id, User.tenant_id == tenant_id, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(status_code=401, detail='Account is inactive or no longer available.')
    return user


@lru_cache(maxsize=1)
def get_surface_segmentation_provider():
    from .segmentation_provider import get_segmentation_provider
    return get_segmentation_provider()

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


@app.post("/api/v1/auth/register", tags=["authentication"])
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    slug_base = "".join(ch.lower() if ch.isalnum() else "-" for ch in payload.workspace_name.strip()).strip("-")[:60] or "workspace"
    tenant = Tenant(name=payload.workspace_name.strip(), slug=f"{slug_base}-{uuid.uuid4().hex[:8]}")
    db.add(tenant)
    db.flush()
    user = User(tenant_id=tenant.id, email=email, full_name=payload.full_name.strip(), password_hash=hash_password(payload.password), role="owner")
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_access_token(str(user.id), str(tenant.id)), "token_type": "bearer", "expires_in": 3600,
            "user": {"id": str(user.id), "email": user.email, "full_name": user.full_name, "role": user.role},
            "workspace": {"id": str(tenant.id), "name": tenant.name, "slug": tenant.slug}}


@app.post("/api/v1/auth/login", tags=["authentication"])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None or not tenant.is_active:
        raise HTTPException(status_code=403, detail="Workspace is inactive.")
    return {"access_token": create_access_token(str(user.id), str(tenant.id)), "token_type": "bearer", "expires_in": 3600,
            "user": {"id": str(user.id), "email": user.email, "full_name": user.full_name, "role": user.role},
            "workspace": {"id": str(tenant.id), "name": tenant.name, "slug": tenant.slug}}


@app.get("/api/v1/auth/me", tags=["authentication"])
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tenant = db.get(Tenant, current_user.tenant_id)
    return {"user": {"id": str(current_user.id), "email": current_user.email, "full_name": current_user.full_name, "role": current_user.role},
            "workspace": {"id": str(tenant.id), "name": tenant.name, "slug": tenant.slug}}


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
        {"id": "surface-analysis", "name": "Surface segmentation", "status": "requires-local-model", "description": "Local semantic floor/wall segmentation requires an explicitly configured compatible checkpoint. Automatic heuristic fallback is disabled to prevent false surface proposals; manual outlining remains available."},
        {"id": "ai-depth", "name": "Local AI depth estimation", "status": "optional-local-model", "description": "Depth Anything V2 Small estimates relative scene depth locally when optional AI dependencies are installed; it is not semantic segmentation or metric geometry."},
        {"id": "photo-renderer", "name": "Photo renderer", "status": "projective-preview", "description": "Browser preview uses a subdivided projective homography for planar quadrilateral mapping. Photometric lighting reconstruction, physically based material response, and validated foreground compositing remain unfinished."},
        {"id": "camera-preview", "name": "Live camera preview", "status": "planned", "description": "Live camera material preview is planned after the photo workflow."},
    ]


@app.get("/api/v1/media/{storage_key}", tags=["media"])
def get_private_media(storage_key: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Never trust a client-supplied path: only serve a basename that belongs to
    # a product or project owned by the authenticated workspace.
    if not storage_key or Path(storage_key).name != storage_key or storage_key in {".", ".."}:
        raise HTTPException(status_code=404, detail="Media not found.")
    product_asset = db.scalar(
        select(ProductAsset.id).join(TileProduct, ProductAsset.product_id == TileProduct.id).where(
            ProductAsset.storage_key == storage_key, TileProduct.tenant_id == current_user.tenant_id
        )
    )
    legacy_product = db.scalar(select(TileProduct.id).where(
        TileProduct.material_asset_key == storage_key, TileProduct.tenant_id == current_user.tenant_id
    ))
    project_asset = db.scalar(
        select(ProjectAsset.id).join(Project, ProjectAsset.project_id == Project.id).where(
            ProjectAsset.storage_key == storage_key, Project.tenant_id == current_user.tenant_id
        )
    )
    if not (product_asset or legacy_product or project_asset):
        raise HTTPException(status_code=404, detail="Media not found.")
    path = UPLOAD_DIR / storage_key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Media not found.")
    return FileResponse(path, media_type=mimetypes.guess_type(storage_key)[0] or "application/octet-stream")


@app.get("/api/v1/products", tags=["catalog"])
def list_products(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tenant_id = current_user.tenant_id
    products = db.scalars(select(TileProduct).where(TileProduct.tenant_id == tenant_id).order_by(TileProduct.created_at.desc())).all()
    return [serialize_product(p) for p in products]


def serialize_product(product: TileProduct):
    assets = [{
        "id": str(asset.id), "role": asset.role, "url": "/api/v1/media/" + asset.storage_key,
        "name": asset.original_name, "mime_type": asset.mime_type, "sort_order": asset.sort_order,
    } for asset in product.assets]
    texture = next((a["url"] for a in assets if a["role"] == "texture"), None)
    legacy_texture = "/api/v1/media/" + product.material_asset_key if product.material_asset_key else None
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Product name is required.")
    if width_mm is not None and width_mm <= 0 or height_mm is not None and height_mm <= 0:
        raise HTTPException(status_code=422, detail="Tile dimensions must be positive.")
    tenant_id = current_user.tenant_id
    allowed_categories = {"tile", "natural-stone", "wood-flooring", "wallpaper", "countertop", "paint", "panel", "paver", "other"}
    category = category.strip().lower()
    if category not in allowed_categories:
        raise HTTPException(status_code=422, detail="Unsupported material category.")
    product = TileProduct(
        tenant_id=tenant_id, name=name, sku=sku or None, description=description or None,
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
def delete_product(product_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    product = db.scalar(select(TileProduct).where(TileProduct.id == product_id, TileProduct.tenant_id == current_user.tenant_id))
    if product is None:
        raise HTTPException(status_code=404, detail="Tile product not found.")
    db.delete(product)
    db.commit()
    return {"deleted": True}


@app.get("/api/v1/projects", tags=["projects"])
def list_projects(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = db.scalars(select(Project).where(Project.tenant_id == current_user.tenant_id).order_by(Project.created_at.desc())).all()
    return [{
        "id": str(p.id), "name": p.name, "status": p.status,
        "room_image_url": next((f"/api/v1/media/{a.storage_key}" for a in p.assets if a.asset_type == "room"), None),
        "created_at": p.created_at,
    } for p in projects]


@app.post("/api/v1/projects", tags=["projects"])
def create_project(name: str = Form(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)): 
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Project name is required.")
    project = Project(tenant_id=current_user.tenant_id, created_by_id=current_user.id, name=name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": str(project.id), "name": project.name, "status": project.status}


@app.post("/api/v1/projects/{project_id}/room-image", tags=["projects"])
async def upload_room_image(project_id: uuid.UUID, image: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.scalar(select(Project).where(Project.id == project_id, Project.tenant_id == current_user.tenant_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    key, size = await save_image(image)
    asset = ProjectAsset(project_id=project.id, asset_type="room", storage_key=key, mime_type=image.content_type,
                         metadata_json={"original_name": image.filename, "size_bytes": size})
    db.add(asset)
    db.commit()
    return {"asset_id": str(asset.id), "room_image_url": f"/api/v1/media/{key}", "size_bytes": size}


@app.post("/api/v1/projects/{project_id}/detect-surface", tags=["surface-analysis"])
def detect_surface(project_id: uuid.UUID, mode: str = "floor", current_user: User = Depends(get_current_user), db: Session = Depends(get_db)): 
    """Return an editable floor or wall boundary proposal in normalized image coordinates."""
    if mode not in {"floor", "wall"}:
        raise HTTPException(status_code=422, detail="Mode must be floor or wall.")
    project = db.scalar(select(Project).where(Project.id == project_id, Project.tenant_id == current_user.tenant_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    room_asset = db.scalar(select(ProjectAsset).where(
        ProjectAsset.project_id == project.id, ProjectAsset.asset_type == "room"
    ).order_by(ProjectAsset.created_at.desc()))
    if room_asset is None:
        raise HTTPException(status_code=404, detail="Upload a room photo first.")
    try:
        import cv2
        from .surface_detection import SurfaceDetectionError, detect_floor_boundary, detect_wall_boundary
        provider = get_surface_segmentation_provider()
        if provider is None:
            raise HTTPException(
                status_code=503,
                detail="AI surface detection is not configured. Use the manual outline for now, or install a compatible local floor/wall segmentation checkpoint. Heuristic auto-detection is disabled because it can select cabinets, shelves, or furniture as a surface.",
            )
        image = cv2.imread(str(UPLOAD_DIR / room_asset.storage_key))
        if image is None:
            raise HTTPException(status_code=422, detail="Room image could not be decoded.")
        result = detect_floor_boundary(image, provider) if mode == "floor" else detect_wall_boundary(image, provider)
        return {"mode": mode, **result}
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=503, detail="Automatic detection is unavailable because the vision dependency is not installed.")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f"Segmentation model is not available: {str(exc)[:160]}")
    except SurfaceDetectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Automatic detection failed: {str(exc)[:160]}")


@app.post("/api/v1/projects/{project_id}/analyze-depth", tags=["surface-analysis"])
def analyze_room_depth(project_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Run customer-hosted monocular depth inference on the latest room photo."""
    project = db.scalar(select(Project).where(Project.id == project_id, Project.tenant_id == current_user.tenant_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    room_asset = db.scalar(select(ProjectAsset).where(
        ProjectAsset.project_id == project.id, ProjectAsset.asset_type == "room"
    ).order_by(ProjectAsset.created_at.desc()))
    if room_asset is None:
        raise HTTPException(status_code=404, detail="Upload a room photo first.")
    try:
        import cv2
        from .depth_estimation import DepthEstimationUnavailable, get_depth_estimator
        image = cv2.imread(str(UPLOAD_DIR / room_asset.storage_key))
        if image is None:
            raise HTTPException(status_code=422, detail="Room image could not be decoded.")
        depth = get_depth_estimator().predict(image)
        ok, encoded = cv2.imencode(".png", depth)
        if not ok:
            raise HTTPException(status_code=500, detail="Could not encode the depth map.")
        return {
            "model": "depth-anything-v2-small",
            "device": get_depth_estimator().device,
            "width": int(depth.shape[1]),
            "height": int(depth.shape[0]),
            "depth_map": "data:image/png;base64," + base64.b64encode(encoded.tobytes()).decode("ascii"),
            "depth_type": "relative",
            "warnings": ["Relative depth is not a real-world measurement.", "Depth estimation is not a floor/wall semantic mask. Review surface boundaries manually."],
        }
    except HTTPException:
        raise
    except DepthEstimationUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Local depth inference failed: {str(exc)[:180]}")


@app.get("/api/v1/projects/{project_id}", tags=["projects"])
def get_project(project_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)): 
    project = db.scalar(select(Project).where(Project.id == project_id, Project.tenant_id == current_user.tenant_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {
        "id": str(project.id), "name": project.name, "status": project.status,
        "assets": [{"id": str(a.id), "type": a.asset_type, "url": f"/api/v1/media/{a.storage_key}"} for a in project.assets],
    }
