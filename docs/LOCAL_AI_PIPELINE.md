# Local AI vision pipeline

## Implemented AI stages

Surface Analyzer has two optional local AI stages:

- **Depth estimation:** Depth Anything V2 Small estimates relative scene depth. It is not metric geometry.
- **Semantic segmentation:** a customer-selected Hugging Face semantic checkpoint can return per-pixel floor/wall probabilities and scene classes. Detected furniture and other configured object classes are returned as separate normalized occlusion polygons and removed from the target surface proposal.

Both stages run inside the customer's API process. Room photos are not sent to a vendor inference API. Model weights are cached in the customer-controlled Hugging Face cache. CUDA is selected when the installed PyTorch build and runtime expose it; otherwise inference runs on CPU.

The existing binary ONNX adapter remains supported. OpenCV GrabCut remains the fallback when no segmentation provider is configured.

## Commercial model and dataset licensing gate

**Do not use ADE20K-derived pretrained weights in a commercial Surface Analyzer deployment unless the relevant rights holders grant commercial permission.** MIT CSAIL's ADE20K image terms restrict the images to non-commercial research and educational use. The fact that a third-party model card says BSD-3-Clause does not automatically grant commercial rights to the training images or learned weights. In particular, the common NVIDIA SegFormer ADE20K checkpoint and Pictograph SceneParse150 checkpoint are not approved defaults for this commercial product until their training-data and weight rights are independently cleared.

The intended production path is a model trained or fine-tuned on a properly licensed indoor-room/tile dataset, with written rights for commercial training and deployment. Keep the model checkpoint external to the repository and set the model ID/path only after legal and technical review. Model architecture/code licensing, checkpoint licensing, and training-data licensing are separate checks.

## Enable semantic segmentation

1. Set INSTALL_AI=true in the installation .env file and rebuild the API image.
2. Set SURFACE_SEGMENTATION_BACKEND=transformers.
3. Set SURFACE_SEGMENTATION_MODEL_ID to an approved semantic checkpoint exposing floor and wall classes in id2label.
4. Ensure that the checkpoint also labels furniture/object classes if separate occlusion polygons are required.
5. Set HF_HOME to a persistent customer-controlled directory (production Compose mounts api_models).
6. Restart the API and call authenticated POST /api/v1/projects/{project_id}/detect-surface?mode=floor or mode=wall.

The provider resolves class IDs from model metadata; it does not hardcode ADE20K class indexes. The endpoint returns the main target polygon plus an occlusions array. Each occlusion includes a class label, normalized polygon, normalized bounding box, confidence and area ratio. The target proposal excludes pixels assigned to configured occlusion classes.

The default occlusion labels include common furniture, rugs, fixtures, doors and windows. Override them with a comma-separated SURFACE_OCCLUSION_LABELS value when a model uses different class names. Use exact normalized names from the model's id2label metadata.

For checkpoints with different output conventions, export a compatible semantic segmentation model or implement a dedicated provider adapter. The legacy ONNX adapter is a binary 4-channel model contract and does not provide separate occlusion classes.

## Enable depth estimation

### Docker Compose installation

1. Set INSTALL_AI=true in the installation .env file.
2. Rebuild and restart the API image using the production Compose file.
3. Open Studio, select a project with a room photo, and choose AI depth analysis. First use downloads model weights into the persistent api_models volume and requires internet access. Later runs use the local cache.

### Direct Python installation

1. In apps/api, install base requirements, then apps/api/requirements-ai.txt.
2. For NVIDIA acceleration, install a CUDA-enabled PyTorch build compatible with the host driver before installing the remaining AI requirements. Standard CPU PyTorch runs on CPU.
3. Set HF_HOME to a customer-controlled persistent directory.

For Docker Desktop with NVIDIA GPU passthrough, the host needs a compatible NVIDIA driver and Docker GPU support, and the container PyTorch build must include CUDA support. Without all three, the model uses CPU. GPU passthrough on Windows Docker Desktop depends on WSL2 and driver setup and has not yet been verified on every Windows configuration.

## Limits and next validation gates

- Relative depth is not a real-world measurement.
- Generic indoor semantic models can confuse rugs, reflective surfaces, unusual camera angles, furniture, and partially occluded boundaries.
- Object-class segmentation is not a guarantee that every object is detected or that its boundary is pixel-perfect.
- The API returns editable proposals; manual correction remains required.
- The ONNX adapter still requires a compatible customer-supplied model file.
- This is an AI pipeline foundation, not Roomvo-level output. Before production, validate on a held-out set of real phone photos from tile showrooms and lived-in rooms, measure floor/wall IoU and occlusion recall, and test perspective mapping, lighting, shadows, reflections and grout.

## References

- ADE20K terms: https://sceneparsing.csail.mit.edu/terms/
- Transformers semantic segmentation: https://huggingface.co/docs/transformers/tasks/semantic_segmentation
- NVIDIA SegFormer license notice: https://github.com/NVlabs/SegFormer
