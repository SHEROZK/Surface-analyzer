import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    products: Mapped[list["TileProduct"]] = relationship(back_populates="tenant")
    projects: Mapped[list["Project"]] = relationship(back_populates="tenant")

class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(160))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), default="member", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tenant: Mapped["Tenant"] = relationship(back_populates="users")

class TileProduct(TimestampMixin, Base):
    __tablename__ = "tile_products"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    width_mm: Mapped[int | None] = mapped_column(Integer)
    height_mm: Mapped[int | None] = mapped_column(Integer)
    finish: Mapped[str | None] = mapped_column(String(80))
    material_asset_key: Mapped[str | None] = mapped_column(String(500))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    tenant: Mapped["Tenant"] = relationship(back_populates="products")

class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tenant: Mapped["Tenant"] = relationship(back_populates="projects")
    assets: Mapped[list["ProjectAsset"]] = relationship(back_populates="project", cascade="all, delete-orphan")

class ProjectAsset(TimestampMixin, Base):
    __tablename__ = "project_assets"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    asset_type: Mapped[str] = mapped_column(String(40), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    width_px: Mapped[int | None] = mapped_column(Integer)
    height_px: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    project: Mapped["Project"] = relationship(back_populates="assets")
