# Surface Analyzer — Initial Architecture

## Product direction
Independent, multi-tenant SaaS for tile visualization, supporting uploaded-photo visualization and live-camera material preview.

## Architecture
API-first modular monolith, with separately scalable rendering and inference workers as demand grows.

- Web: Next.js, TypeScript, React, Tailwind CSS.
- API: FastAPI, Pydantic, SQLAlchemy, Alembic.
- Database: PostgreSQL.
- Jobs/cache: Redis and Celery.
- Vision: OpenCV and PyTorch for surface detection and geometry assistance.
- Rendering: Three.js/WebGL for deterministic perspective-aware tile rendering, with AI-assisted surface understanding.
- Storage: S3-compatible object storage, initially self-hosted with MinIO.
- Deployment: Docker Compose with separate web, API, worker, database, Redis, and storage services.

## Core modules
1. Tenants, users, authentication, and role-based access control.
2. Tile catalog, product metadata, and material maps.
3. Projects, room photos, uploads, and image processing.
4. Surface detection, editable masks, polygons, and perspective geometry.
5. Photo renderer with tile scale, grout, rotation, and repeat controls.
6. Live camera preview with WebXR where supported and camera-overlay fallback.
7. Tenant branding, shareable projects, and embeddable visualization.
8. Usage metering, subscriptions, and licensing.
9. Audit logs, monitoring, backups, and administration.

## Rendering principles
Use deterministic geometry and texture mapping for predictable placement, scale, perspective, and repeatability. Use AI to assist segmentation and difficult image interpretation rather than making the entire renderer generative. Preserve the original scene outside selected surfaces wherever possible.

## Delivery sequence
- Foundation: monorepo, local development, CI, configuration, migrations, and tests.
- Platform core: tenancy, authentication, RBAC, catalog, projects, and uploads.
- Surface analysis: detection, editable masks, polygon tools, and perspective estimation.
- Photo renderer: material mapping, scale, grout, rotation, lighting controls, and export.
- Camera preview: permissions, live material overlay, tracking, and fallback.
- SaaS operations: tenant dashboard, sharing, embed integration, plans, metering, and administration.
- Hardening: security, performance, observability, backups, and production deployment.

## Engineering principles
- Enforce tenant isolation in API and database access.
- Run long-running image and inference work asynchronously.
- Separate original uploads from derived assets with explicit lifecycle rules.
- Version APIs and migrations; test migration safety and tenant boundaries.
- Keep rendering parameters reproducible so projects can be reopened consistently.
