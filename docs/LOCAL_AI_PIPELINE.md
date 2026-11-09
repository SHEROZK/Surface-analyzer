# Local AI vision pipeline

## Implemented AI stages

Surface Analyzer now has two separate optional local AI stages:

- **Depth estimation:** Depth Anything V2 Small (depth-anything/Depth-Anything-V2-Small-hf) estimates relative depth. Its model card identifies Apache-2.0 licensing.
- **Semantic surface segmentation:** a local Hugging Face Transformers provider can run a customer-selected semantic segmentation checkpoint. The checkpoint must expose class labels named floor and wall (or flooring / walls) in its id2label metadata. The provider returns per-pixel class probabilities to the existing editable-boundary pipeline.

Both stages run inside the customer's API process. Room photos are not sent to a vendor inference API. Model weights are downloaded on first use and cached under the customer-controlled Hugging Face cache. CUDA is selected when the installed PyTorch build and runtime expose it; otherwise inference runs on CPU.

The existing ONNX adapter remains supported for custom trained models. OpenCV GrabCut remains the fallback when no segmentation provider is configured.

## Enable semantic segmentation

1. Set INSTALL_AI=true in the installation .env file and rebuild the API image.
2. Set SURFACE_SEGMENTATION_BACKEND=transformers.
3. Set SURFACE_SEGMENTATION_MODEL_ID to a checkpoint whose model config includes floor and wall semantic classes.
4. Set HF_HOME to a persistent customer-controlled directory (the production Compose setup mounts the api_models volume).
5. Restart the API and call authenticated POST /api/v1/projects/{project_id}/detect-surface?mode=floor or mode=wall.

The provider validates that both requested labels exist in the model metadata. It does not silently guess class indexes. For checkpoints with different class names or output conventions, train/export a compatible model or use the ONNX adapter.

**Model licensing is the deployer's responsibility.** Verify the exact checkpoint's weight, dataset, and commercial-use terms before enabling it in a commercial installation. Do not assume that every model hosted on Hugging Face is commercially licensed.

## Enable depth estimation

### Docker Compose installation

1. Set INSTALL_AI=true in the installation .env file.
2. Rebuild and restart the API image using the production Compose file.
3. Open Studio, select a project with a room photo, and choose AI depth analysis. The first run downloads the model into the persistent api_models volume and therefore requires internet access. Later runs use the local cache.

### Direct Python installation

1. In apps/api, install base requirements, then apps/api/requirements-ai.txt.
2. For NVIDIA acceleration, install a CUDA-enabled PyTorch build compatible with the host driver before installing the remaining AI requirements. Standard CPU PyTorch will run on CPU.
3. Set HF_HOME to a customer-controlled persistent directory.

For Docker Desktop with NVIDIA GPU passthrough, the host needs a compatible NVIDIA driver and Docker GPU support, and the container PyTorch build must include CUDA support. Without all three, the model uses CPU. GPU passthrough on Windows Docker Desktop depends on WSL2 and driver setup and has not yet been verified on every Windows configuration.

## Limits

- Relative depth is not a real-world measurement.
- Generic indoor semantic checkpoints can confuse rugs, reflective surfaces, unusual camera angles, furniture, and partially occluded boundaries.
- A semantic floor/wall class is not a tile-specific segmentation model and does not guarantee a Roomvo-quality mask.
- The provider returns editable proposals; manual correction remains required.
- The ONNX adapter still requires a compatible customer-supplied model file.
- This is an AI foundation milestone, not Roomvo-level output. A commercial-use checkpoint validated on indoor tile imagery, object/occlusion masks, perspective geometry, material-aware lighting, and a real-photo benchmark are still required.

## Model references

- Depth Anything V2 Small: https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf
- Transformers semantic segmentation API: https://huggingface.co/docs/transformers/tasks/semantic_segmentation
