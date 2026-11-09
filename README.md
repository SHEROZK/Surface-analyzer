# Surface Analyzer

Surface visualization SaaS for tiles and other architectural finishes. The local MVP supports a multi-category material catalog and previews a selected material inside a manually outlined region of a room photograph.

## MVP features
- Create and switch between visualization projects.
- Upload room photographs (JPG, PNG, WebP; 15 MB limit).
- Create a catalog for tiles, natural stone, wood/flooring, wallpaper, countertops, paint/coatings, panels, pavers and other surfaces.
- Store brand, collection, SKU, dimensions, finish, a primary seamless texture, multiple gallery images, and optional normal/roughness maps as separate product assets.
- Select a tile material and outline a wall or floor by clicking polygon points on the room photo.
- Preview the repeating material texture inside the selected polygon, with scale and opacity controls.
- Persistent PostgreSQL records and a Docker volume for uploaded files.

**Not in this MVP yet:** account registration, production tenant isolation, automatic AI surface detection, perspective-correct material projection, physically based lighting/shadows, live camera AR, billing, and production hardening. The current renderer is still a 2D repeated-texture preview and must not be presented as a photorealistic final render. The first polygon renderer is a manual 2D texture preview, not a physically accurate architectural renderer.

## Stack
- Next.js + TypeScript frontend
- FastAPI + SQLAlchemy + Alembic API
- PostgreSQL database
- Redis infrastructure (reserved for background jobs)
- MinIO infrastructure (object-storage integration is a follow-on; MVP uploads use a persistent local Docker volume)
- Docker Compose local environment

## Run locally
Requirements: Docker Desktop with Docker Compose.

1. Clone the repository.
2. Copy `.env.example` to `.env`. Change the development passwords before sharing the environment.
3. Start the services:

   ```bash
   docker compose up --build
   ```

   The API container applies Alembic migrations automatically before starting.
4. Open:
   - Studio: http://localhost:3000
   - API: http://localhost:8000
   - API docs: http://localhost:8000/docs
   - MinIO console: http://localhost:9001

The default Compose credentials are for local development only. Never expose this configuration directly to the public internet.

## First-use workflow
1. Create a project in the left panel.
2. Open the project and upload a room photograph.
3. Add a surface product, choose its category, and upload a seamless texture plus any gallery/maps available.
4. Select the material, then click at least three points around the target floor or wall surface.
5. Adjust tile scale and opacity. Clear or undo points to refine the outline.

## Repository layout
```
apps/
  api/
    app/                 FastAPI routes and SQLAlchemy models
    migrations/          Alembic schema migrations
    tests/               API tests
  web/
    app/                 Next.js studio and photo visualizer
docs/
  ARCHITECTURE.md
docker-compose.yml
.env.example
```

## Development roadmap
1. Add automated API and frontend build checks; verify the compose stack end-to-end.
2. Improve polygon editing and build a deterministic perspective-aware renderer with grout, tile layouts, rotation, and room-light preservation.
3. Add AI-assisted room segmentation, occlusion, and object-aware masks.
4. Add authentication and enforce tenant isolation before multi-customer deployment.
5. Integrate AI surface suggestions and object-aware masking.
6. Integrate live camera preview, then billing, embed SDK, and production operations.
