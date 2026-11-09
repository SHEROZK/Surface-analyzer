"""Local monocular depth estimation using the Apache-2.0 Depth Anything V2 Small checkpoint."""
from __future__ import annotations
import os
from functools import lru_cache
import cv2
import numpy as np

MODEL_ID = os.getenv("DEPTH_MODEL_ID", "depth-anything/Depth-Anything-V2-Small-hf")

class DepthEstimationUnavailable(RuntimeError):
    pass

class DepthAnythingV2:
    name = "depth-anything-v2-small"

    def __init__(self):
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForDepthEstimation
        except ImportError as exc:
            raise DepthEstimationUnavailable("Install apps/api/requirements-ai.txt to enable local AI depth estimation.") from exc
        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = AutoImageProcessor.from_pretrained(MODEL_ID)
        self.model = AutoModelForDepthEstimation.from_pretrained(MODEL_ID).eval().to(self.device)
        if self.device == "cuda":
            self.model = self.model.half()

    def predict(self, bgr_image: np.ndarray) -> np.ndarray:
        from PIL import Image
        if bgr_image is None or bgr_image.ndim != 3 or bgr_image.shape[2] != 3:
            raise ValueError("Expected a decoded three-channel room image.")
        height, width = bgr_image.shape[:2]
        rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        inputs = self.processor(images=Image.fromarray(rgb), return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        if self.device == "cuda":
            inputs = {key: value.half() if value.is_floating_point() else value for key, value in inputs.items()}
        with self.torch.inference_mode():
            prediction = self.model(**inputs).predicted_depth
            prediction = self.torch.nn.functional.interpolate(
                prediction.unsqueeze(1), size=(height, width), mode="bicubic", align_corners=False
            ).squeeze()
        depth = prediction.float().cpu().numpy()
        if not np.isfinite(depth).all():
            raise DepthEstimationUnavailable("The depth model returned invalid values.")
        low, high = np.percentile(depth, (1, 99))
        if high - low < 1e-6:
            raise DepthEstimationUnavailable("The depth model returned a flat depth map.")
        return (np.clip((depth - low) / (high - low), 0, 1) * 255).astype(np.uint8)

@lru_cache(maxsize=1)
def get_depth_estimator():
    return DepthAnythingV2()
