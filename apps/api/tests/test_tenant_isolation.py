import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password
from app.db import Base, SessionLocal, engine
from app.main import UPLOAD_DIR, app, get_db
from app.models import ProductAsset, Project, ProjectAsset, Tenant, TileProduct, User


@pytest.fixture
def isolated_workspace_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "test-auth-secret-that-is-at-least-thirty-two-characters")
    monkeypatch.setattr("app.main.UPLOAD_DIR", tmp_path)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    tenant_a = Tenant(name="Workspace A", slug=f"workspace-a-{uuid.uuid4().hex[:8]}")
    tenant_b = Tenant(name="Workspace B", slug=f"workspace-b-{uuid.uuid4().hex[:8]}")
    db.add_all([tenant_a, tenant_b])
    db.flush()
    user_a = User(tenant_id=tenant_a.id, email=f"a-{uuid.uuid4().hex}@example.com", full_name="A", password_hash=hash_password("workspace-password-a"), role="owner")
    user_b = User(tenant_id=tenant_b.id, email=f"b-{uuid.uuid4().hex}@example.com", full_name="B", password_hash=hash_password("workspace-password-b"), role="owner")
    db.add_all([user_a, user_b])
    db.flush()
    product_a = TileProduct(tenant_id=tenant_a.id, name="A material")
    product_b = TileProduct(tenant_id=tenant_b.id, name="B material")
    project_a = Project(tenant_id=tenant_a.id, created_by_id=user_a.id, name="A room")
    project_b = Project(tenant_id=tenant_b.id, created_by_id=user_b.id, name="B room")
    db.add_all([product_a, product_b, project_a, project_b])
    db.flush()
    media_key = f"{uuid.uuid4().hex}.jpg"
    (tmp_path / media_key).write_bytes(b"workspace-private-image")
    db.add(ProductAsset(product_id=product_b.id, role="texture", storage_key=media_key, mime_type="image/jpeg"))
    db.add(ProjectAsset(project_id=project_b.id, asset_type="room", storage_key=media_key, mime_type="image/jpeg"))
    db.commit()
    token_a = create_access_token(str(user_a.id), str(tenant_a.id))
    foreign_project_id = str(project_b.id)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token_a}"})
    try:
        yield client, foreign_project_id, media_key
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_workspace_cannot_list_another_tenants_products(isolated_workspace_client):
    client, _, _ = isolated_workspace_client
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    assert all(product["name"] != "B material" for product in response.json())


def test_workspace_cannot_open_another_tenants_project(isolated_workspace_client):
    client, foreign_project_id, _ = isolated_workspace_client
    response = client.get(f"/api/v1/projects/{foreign_project_id}")
    assert response.status_code == 404


def test_workspace_cannot_download_another_tenants_media(isolated_workspace_client):
    client, _, media_key = isolated_workspace_client
    response = client.get(f"/api/v1/media/{media_key}")
    assert response.status_code == 404


def test_private_media_requires_authentication():
    client = TestClient(app)
    response = client.get("/api/v1/media/not-a-real-file.jpg")
    assert response.status_code == 401
