# Local AI vision pipeline

## Implemented AI stage

Surface Analyzer includes an optional, customer-hosted monocular depth inference stage using **Depth Anything V2 Small** (`depth-anything/Depth-Anything-V2-Small-hf`). Its model card labels the Small checkpoint Apache-2.0.

- Inference runs inside the customer's API process. Room photos are not sent to a vendor API.
- Weights are downloaded from Hugging Face on first inference and cached under `HF_HOME`.
- CUDA is selected automatically when the installed PyTorch build and runtime expose it; otherwise inference uses CPU.
- The model loads lazily and remains cached in process memory.
- Existing ONNX segmentation is a separate optional adapter requiring a compatible model supplied by the customer. OpenCV GrabCut remains a heuristic fallback.

## Enable

1. In `apps/api`, install base requirements, then `pip install -r requirements-ai.txt`.
2. For NVIDIA acceleration, install a CUDA-enabled PyTorch build compatible with the host driver before installing the remaining AI requirements. Standard CPU PyTorch will run on CPU.
3. Set `HF_HOME` to a customer-controlled persistent directory (production Compose uses `/data/models`).
4. Restart API and call authenticated `POST /api/v1/projects/{project_id}/analyze-depth`.

The response contains a normalized grayscale depth map as a PNG data URL, dimensions, device, and model identifier.

## Limits

- The model estimates relative depth, not reliable real-world distances.
- Mirrors, glass, reflections, occlusions, repetitive patterns and unusual camera angles can cause errors.
- Depth is not semantic floor/wall segmentation and does not replace manual boundary correction.
- The ONNX segmentation adapter still has no bundled trained weights. Do not label the current floor/wall detector as semantic AI.
- This is an AI foundation milestone, not Roomvo-level output. A commercial-use semantic/instance segmentation model validated on indoor surface imagery, object occlusion masks, perspective geometry, material-aware lighting and a real-photo benchmark are still required.

## Model reference

https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf
