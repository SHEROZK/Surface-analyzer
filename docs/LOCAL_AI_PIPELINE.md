# Local AI vision pipeline

## Implemented AI stage

Surface Analyzer includes an optional, customer-hosted monocular depth inference stage using **Depth Anything V2 Small** (`depth-anything/Depth-Anything-V2-Small-hf`). Its model card labels the Small checkpoint Apache-2.0.

- Inference runs inside the customer's API process. Room photos are not sent to a vendor API.
- Weights are downloaded from Hugging Face on first inference and cached under `HF_HOME`.
- CUDA is selected automatically when the installed PyTorch build and runtime expose it; otherwise inference uses CPU.
- The model loads lazily and remains cached in process memory.
- Existing ONNX segmentation is a separate optional adapter requiring a compatible model supplied by the customer. OpenCV GrabCut remains a heuristic fallback.

## Enable

### Docker Compose installation

1. Set `INSTALL_AI=true` in the installation `.env` file.
2. Rebuild and restart the API: `docker compose -f docker-compose.production.yml build api` then `docker compose -f docker-compose.production.yml up -d api`.
3. Open Studio, select a project with a room photo, and choose **AI depth analysis**. The first run downloads the model into the persistent `api_models` volume and therefore requires internet access. Later runs use the local cache.

### Direct Python installation

1. In `apps/api`, install base requirements, then `pip install -r requirements-ai.txt`.
2. For NVIDIA acceleration, install a CUDA-enabled PyTorch build compatible with the host driver before installing the remaining AI requirements. Standard CPU PyTorch will run on CPU.
3. Set `HF_HOME` to a customer-controlled persistent directory.
4. Call authenticated `POST /api/v1/projects/{project_id}/analyze-depth`.

The Studio button displays the returned depth map. For Docker Desktop with NVIDIA GPU passthrough configured, use the optional override: `docker compose -f docker-compose.production.yml -f docker-compose.gpu.yml build api` and `docker compose -f docker-compose.production.yml -f docker-compose.gpu.yml up -d api`. The host must have a compatible NVIDIA driver and Docker GPU support; the PyTorch build inside the container must include CUDA support. Without all three, the model uses CPU. GPU passthrough on Windows Docker Desktop depends on the WSL2 and driver setup and has not yet been verified on every Windows configuration.

The response contains a normalized grayscale depth map as a PNG data URL, dimensions, device, and model identifier.

## Limits

- The model estimates relative depth, not reliable real-world distances.
- Mirrors, glass, reflections, occlusions, repetitive patterns and unusual camera angles can cause errors.
- Depth is not semantic floor/wall segmentation and does not replace manual boundary correction.
- The ONNX segmentation adapter still has no bundled trained weights. Do not label the current floor/wall detector as semantic AI.
- This is an AI foundation milestone, not Roomvo-level output. A commercial-use semantic/instance segmentation model validated on indoor surface imagery, object occlusion masks, perspective geometry, material-aware lighting and a real-photo benchmark are still required.

## Model reference

https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf
