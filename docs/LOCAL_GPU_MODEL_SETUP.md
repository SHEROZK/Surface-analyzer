# Local GPU AI setup (Windows + RTX 5070 Ti)

## What must be downloaded

The application does not contain trained model weights. The current code can load a Transformers semantic-segmentation checkpoint and optionally SAM 2, but it cannot do useful learned floor/wall segmentation until compatible weights are installed.

Recommended development setup for this machine:
- NVIDIA RTX 5070 Ti Laptop GPU (12 GB VRAM): suitable for inference with compact/medium segmentation models and SAM 2 Tiny/Small at sensible image resolutions.
- 32 GB system RAM: workable for local inference; avoid loading several large vision models simultaneously.
- Keep at least 20–30 GB free on the AI/model drive for Python environments, model caches, and checkpoints. Actual size depends on the chosen models.

## Important model-selection rule

Do not download a random ADE20K SegFormer/OneFormer checkpoint and assume it is commercially usable. Some popular indoor-scene checkpoints are tied to research-only datasets or non-commercial weight terms. Check the exact model card, checkpoint license, training-data terms, and redistribution rights before enabling it in a customer-facing SaaS.

SAM 2.1 checkpoints are Apache-2.0 according to Meta's official repository. SAM 2 is a promptable mask refiner, not a semantic floor/wall classifier. It needs a point/box prompt or a separate model to propose the object/surface.

## Model candidates reviewed (10 Nov 2026)

- **Pictograph PG-SceneParse150-2XL:** technically relevant because its published class list includes floor, wall, cabinet, shelf, rug, furniture, doors, and fixtures, and its model page lists BSD-3-Clause for the model. However, its model card says it was trained on ADE-20K; the associated dataset page states that the images are limited to non-commercial research/education unless separate permission is obtained. The model is therefore **not approved for this commercial SaaS** without written rights clearance for the training data and resulting weights. Do not download or deploy it as the production checkpoint.
- **SAM 2.1:** approved for the interactive prompt-refinement role under Apache-2.0 according to Meta's repository, but it does not semantically distinguish floor from wall. It remains a separate component, not the missing scene parser.

The current decision is to keep semantic auto-detection disabled until we have either (a) a model trained on commercially cleared data with documented rights, or (b) a written commercial license covering the checkpoint and its training data. A practical route is to assemble a rights-cleared, consented tile-room photo dataset and train/validate a compact floor/wall/object segmentation model against it.

## Recommended architecture

1. **Surface proposal model:** choose or train a commercially cleared indoor-scene model with explicit floor, wall, cabinet, shelving, rug, furniture, door, window, and fixture classes. It must expose a compatible `id2label` containing `floor` and `wall` for the current Transformers adapter.
2. **Promptable mask refinement:** use SAM 2.1 Tiny or Small for user clicks/boxes and boundary refinement. Do not use it to decide whether a region is a floor or wall.
3. **Depth:** keep Depth Anything V2 Small optional. Relative depth can assist ordering/occlusion but is not metric geometry and is not a semantic surface mask.
4. **Renderer:** use the projective preview for planar mapping; photometric reconstruction and realistic material response still require separate implementation and evaluation.

## Where to put weights

Mount a persistent host folder into the API container, for example:

```yaml
services:
  api:
    volumes:
      - api_uploads:/data/uploads
      - ./models:/models:ro
```

Keep model files out of Git. Add `models/` to `.gitignore`. Configure the API with paths inside the container, not Windows paths.

For a Transformers checkpoint stored in `./models/indoor-surfaces`:

```env
SURFACE_SEGMENTATION_BACKEND=transformers
SURFACE_SEGMENTATION_MODEL_ID=/models/indoor-surfaces
```

The checkpoint must have floor and wall labels. The current adapter will reject a checkpoint that does not.

For SAM 2.1 Tiny/Small, the existing optional SAM2 refiner needs both the matching config file and checkpoint file. The config and weights must be from the same SAM 2.1 release. Example environment variables (adjust paths to the actual mounted files):

```env
SURFACE_SAM2_CONFIG=/app/sam2/configs/sam2.1/sam2.1_hiera_s.yaml
SURFACE_SAM2_CHECKPOINT=/models/sam2.1_hiera_small.pt
```

The Studio now exposes positive/negative point prompts for SAM 2 surface selection. The API returns an editable normalized polygon; the user must review and correct it before rendering. Semantic class recognition (floor vs wall) is still a separate, unresolved model-selection problem.

## GPU installation options

### Option A — Docker Desktop + WSL2 (preferred for this Docker Compose project)

1. Install/update the NVIDIA Windows driver with WSL2 CUDA support.
2. Ensure Docker Desktop uses the WSL2 backend.
3. Verify GPU visibility inside WSL2 with `nvidia-smi`.
4. Verify Docker can pass the GPU through using NVIDIA's current Container Toolkit / Docker Desktop guidance.
5. Add GPU access to the API service in a local Compose override (do not commit machine-specific settings blindly):

```yaml
services:
  api:
    gpus: all
    build:
      args:
        INSTALL_AI: "true"
    volumes:
      - ./models:/models:ro
```

6. Build and start with the override:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml build api
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d api
docker compose -f docker-compose.yml -f docker-compose.gpu.yml logs --tail=100 api
```

The API image must contain a CUDA-enabled PyTorch wheel compatible with the installed NVIDIA driver. Installing the optional AI requirements alone is not proof that CUDA is available in the container. Verify `torch.cuda.is_available()` inside the running API container before downloading large weights.

### Option B — Native Windows AI worker

If Docker GPU passthrough is inconvenient, run a separate Python AI worker natively on Windows with CUDA-enabled PyTorch and expose it only on localhost/private Docker network. The current API is not yet wired to an external worker protocol, so this requires a small integration step; do not simply set the Transformers model ID in the container and expect it to use the host GPU.

## Verify PyTorch CUDA

Run this inside the same environment that will execute inference:

```powershell
python -c "import torch; print('torch', torch.__version__); print('cuda build', torch.version.cuda); print('cuda available', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')"
```

Expected result includes `cuda available True` and your RTX 5070 Ti device name. If it says False, model inference will fall back to CPU (or fail if GPU is required).

Use the official PyTorch selector for the current Windows/WSL/Linux platform and CUDA build: https://pytorch.org/get-started/locally/

## Do not download yet

Do not download ADE20K-derived checkpoints or large SAM 2 Large weights as a first step. First establish the GPU runtime and select a floor/wall checkpoint with cleared commercial rights. For SAM refinement, start with SAM 2.1 Tiny or Small, not Large, on 12 GB VRAM.

## Current implementation status

- [x] Local Transformers provider interface (requires compatible checkpoint).
- [x] Optional SAM 2 box-refinement adapter (requires matching config/checkpoint).
- [x] Authenticated SAM 2 point-prompt surface refinement API and Studio controls.
- [x] Automatic heuristic detection disabled when no semantic provider is configured, to avoid misleading masks.
- [x] Projective homography mesh mapping in the browser preview.
- [ ] Commercially cleared floor/wall model selected, downloaded, and benchmarked.
- [ ] Brush-based mask editing and persistent per-project mask revisions.
- [ ] Full perspective-aware scale calibration and tile layout validation.
- [ ] Photometric lighting/shadow reconstruction and realistic foreground compositing.
- [ ] Held-out image evaluation and visual quality acceptance gate.

This is a development setup guide, not a claim that the full photorealistic renderer is finished.
