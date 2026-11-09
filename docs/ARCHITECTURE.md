# Surface Analyzer — Architecture

## Product direction

Surface Analyzer is an independently branded, self-hosted software product for businesses that sell, specify, or install architectural surface materials. Each customer installs and operates a separate instance on infrastructure they control: an on-premises server, workstation/server network, or private cloud account.

This is not a SaaS platform. There is no shared vendor-hosted multi-tenant runtime, mandatory cloud account, subscription billing dependency, or requirement to send customer catalogs, room photographs, or project data to vendor servers. Core visualization must work locally within the customer's deployment.

## Deployment model

- One independent installation per business or organization.
- Customer-controlled database, file storage, credentials, backups, and network access.
- Docker Compose as the standard installation path; support a documented production deployment profile.
- Optional reverse proxy and customer-owned domain for browser access and website embedding.
- Local operation for core catalog, project, image processing, and rendering workflows. Internet access is optional for updates, external integrations, or explicitly enabled AI services.
- Updates are versioned and customer-initiated, with migration checks, backup guidance, and rollback procedures.
- Organization/user authentication protects the installation. Organization scoping is a local access-control boundary, not a shared SaaS tenancy model.
- No billing, usage-metering, or vendor-hosted subscription services in the core product.

## Architecture

A modular application with separately deployable processing workers where useful.

- Web: Next.js, TypeScript, React, Tailwind CSS.
- API: FastAPI, Pydantic, SQLAlchemy, Alembic.
- Database: PostgreSQL.
- Jobs/cache: Redis and Celery for local background processing.
- Vision: OpenCV and PyTorch for surface detection and geometry assistance.
- Rendering: Three.js/WebGL for deterministic perspective-aware surface rendering, with AI-assisted surface understanding.
- Storage: customer-controlled local disk or self-hosted S3-compatible storage such as MinIO.
- Deployment: Docker Compose with web, API, worker, database, Redis, and optional object-storage services.

## Core modules

1. Local installation configuration, organization users, authentication, and role-based access control.
2. Multi-category material catalog, product metadata, variants, and material maps.
3. Projects, room photos, uploads, and image processing.
4. Surface detection, editable masks, polygons, and perspective geometry.
5. Photo renderer with tile scale, grout, rotation, layout, and repeat controls.
6. Live camera preview with WebXR where supported and camera-overlay fallback.
7. Customer branding, shareable project links, and embeddable visualization.
8. Lead, sample, quote, and showroom workflows managed by the customer's installation.
9. Audit logs, monitoring, backups, restore, and installation administration.

## Rendering principles

Use deterministic geometry and texture mapping for predictable placement, scale, perspective, and repeatability. Use AI to assist segmentation and difficult image interpretation rather than making the entire renderer generative. Preserve the original scene outside selected surfaces wherever possible. AI inference should run locally when supported; any external AI provider must be explicitly configured by the installing customer and clearly disclosed.

## Data and privacy principles

- Customer catalogs, room photographs, project files, leads, and generated renders remain in customer-controlled storage by default.
- No telemetry or image upload to vendor infrastructure by default.
- Optional diagnostics must be opt-in and avoid collecting customer images or personal data.
- Provide documented backup, restore, retention, and deletion workflows.
- Enforce user permissions and organization-level access boundaries within each installation.
- Keep API keys, signing secrets, and database credentials configurable per installation.

## Delivery sequence

- Foundation: monorepo, local development, Docker installation, CI, configuration, migrations, and tests.
- Local application core: organization setup, authentication, roles, catalog, projects, and uploads.
- Surface analysis: detection, editable masks, polygon tools, and perspective estimation.
- Photo renderer: material mapping, scale, grout, rotation, lighting controls, and export.
- Camera preview: permissions, live material overlay, tracking, and fallback.
- Business workflows: customer branding, share links, embed integration, leads, sample/quote requests, and local analytics.
- Installation hardening: installer, upgrade/migration process, security, performance, observability, backups, restore, and production deployment.

## Engineering principles

- Keep each installation self-contained and customer-controlled.
- Do not introduce dependencies on a shared vendor-hosted platform for core operation.
- Run long-running image and inference work asynchronously where appropriate.
- Separate original uploads from derived assets with explicit lifecycle rules.
- Version APIs and migrations; test migration safety and access boundaries.
- Keep rendering parameters reproducible so projects can be reopened consistently.
- Make external integrations optional, configurable, and disabled unless the customer enables them.
