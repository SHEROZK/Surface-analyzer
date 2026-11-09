# Surface Analyzer

Self-hosted surface visualization software for tiles and other architectural finishes. Each business runs its own installation and controls its data, users, catalog, and infrastructure. The local MVP supports a multi-category material catalog and previews a selected material inside a manually outlined region of a room photograph.

## MVP features
- Create and switch between visualization projects.
- Upload room photographs (JPG, PNG, WebP; 15 MB limit).
- Create a catalog for tiles, natural stone, wood/flooring, wallpaper, countertops, paint/coatings, panels, pavers and other surfaces.
- Store brand, collection, SKU, dimensions, finish, a primary seamless texture, multiple gallery images, and optional normal/roughness maps as separate product assets.
- Propose floor and wall boundaries using OpenCV, then refine the editable polygons manually.
- Optional local AI depth analysis using Depth Anything V2 Small (Apache-2.0), with a Studio preview of relative scene depth.
- Optionally connect a trained ONNX semantic-segmentation model through a documented provider contract.
- Drag materials onto detected floor or wall regions, with a live drop-target highlight.
- Preview the repeating material texture inside the selected polygon, with scale and opacity controls.
- Persistent PostgreSQL records and a Docker volume for uploaded files.

**Important limitations:** The default floor/wall detector is a heuristic OpenCV GrabCut proposal, not semantic AI segmentation; furniture and rugs may be included in its mask. The AI depth model estimates relative depth only and does not identify floors, walls, furniture, or real-world dimensions. The ONNX segmentation adapter is only an integration interface: no trained semantic model weights are bundled. To enable it, install `onnxruntime` in the API image and set `SURFACE_SEGMENTATION_MODEL` to a compatible model file. The model must accept float32 NCHW `[1,4,H,W]` input (RGB 0–1 plus a mode plane: 0=floor, 1=wall) and return `[1,1,H,W]` probabilities or logits. Without that file, the API uses the OpenCV fallback. Perspective-correct material projection, physically based lighting/shadows, live camera AR, billing, and production hardening remain outstanding. The current renderer is still a 2D repeated-texture preview and must not be presented as a photorealistic final render. The first polygon renderer is a manual 2D texture preview, not a physically accurate architectural renderer.

## Stack
- Next.js + TypeScript frontend
- FastAPI + SQLAlchemy + Alembic API
- PostgreSQL database
- Redis infrastructure (reserved for background jobs)
- MinIO infrastructure (object-storage integration is a follow-on; MVP uploads use a persistent local Docker volume)
- Docker Compose local environment

## Install for a business

For a customer-managed installation, use the production Compose stack and Windows installer. See [Self-hosted installation](docs/SELF_HOSTED_INSTALLATION.md). The installer generates secrets and does not overwrite an existing `.env` file.

## Run locally (development)
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
4. Complete organization-level authentication, roles, and access controls for each independent installation.
5. Integrate AI surface suggestions and object-aware masking.
6. Integrate live camera preview, then embed SDK and production operations.
