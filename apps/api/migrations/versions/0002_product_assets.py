"""Add general material catalog fields and multiple product assets."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_product_assets"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tile_products", sa.Column("category", sa.String(80), nullable=False, server_default="tile"))
    op.add_column("tile_products", sa.Column("brand", sa.String(160), nullable=True))
    op.add_column("tile_products", sa.Column("collection", sa.String(160), nullable=True))
    op.create_table(
        "product_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tile_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(40), nullable=False, server_default="gallery"),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("original_name", sa.String(255)),
        sa.Column("mime_type", sa.String(120)),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_product_assets_product_id", "product_assets", ["product_id"])
    # Preserve the old single texture as the first-class texture asset.
    op.execute("""
        INSERT INTO product_assets (id, product_id, role, storage_key, original_name, sort_order, metadata, created_at, updated_at)
        SELECT gen_random_uuid(), id, 'texture', material_asset_key, 'legacy-material', 0, '{}'::json, now(), now()
        FROM tile_products WHERE material_asset_key IS NOT NULL
    """)


def downgrade():
    op.drop_index("ix_product_assets_product_id", table_name="product_assets")
    op.drop_table("product_assets")
    op.drop_column("tile_products", "collection")
    op.drop_column("tile_products", "brand")
    op.drop_column("tile_products", "category")
