# Surface Analyzer

Independent SaaS platform for visualizing tile materials in real spaces.

**Current stage:** Foundation scaffold (0.1.0). This is an active development starter, not a production-ready application.

## Product direction
- Tile-first initial market, with independent SaaS branding.
- Hybrid rendering: deterministic geometry-based material mapping plus AI-assisted surface understanding.
- Both uploaded-photo visualization and live-camera preview in the V1 product scope.
- Self-hosted deployment, API-first modular monolith, and separately scalable workers as usage grows.

## Repository structure
```
apps/
  api/                 FastAPI service
    app/                API application
    tests/              API tests
  web/                 Next.js application
docs/                  Architecture and product decisions
docker-compose.yml     Local infrastructure and app services
.env.example           Local environment variable reference
```

## Quick start
Requirements: Docker Desktop with Compose.

1. Copy `.env.example` to `.env` and replace the development credentials.
2. Start the stack:

   ```bash
   docker compose up --build
   ```

3. Open:
   - Web workspace: http://localhost:3000
   - API: http://localhost:8000
   - API docs: http://localhost:8000/docs
   - MinIO console: http://localhost:9001

The initial compose file uses local development credentials. Do not expose this stack to the public internet or reuse these credentials in production.

## Local development without Docker
API:
```bash
cd apps/api
python -m venv .venv
# activate the virtual environment
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Web:
```bash
cd apps/web
npm install
npm run dev
```

## Current implementation
- Initial product landing/workspace shell.
- FastAPI service with health and capability endpoints.
- Docker Compose development stack for PostgreSQL, Redis, MinIO, API, and web.
- Initial architecture and implementation direction.

## Next milestones
1. Persistence foundation: SQLAlchemy models, Alembic migrations, tenant isolation.
2. Authentication and tenant-aware RBAC.
3. Tile catalog and material asset management.
4. Project creation, image uploads, and asset storage.
5. Surface annotation and perspective geometry.
6. Deterministic tile renderer, then camera preview.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the architecture baseline.
