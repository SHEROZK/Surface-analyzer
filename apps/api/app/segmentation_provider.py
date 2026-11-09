"""Optional ONNX Runtime adapter for a Surface Analyzer segmentation model.

Model contract: float32 NCHW input [1, 4, H, W], RGB normalized to 0..1
plus a mode plane (0=floor, 1=wall); output [1, 1, H, W] probabilities
or logits. The adapter is optional; heuristic OpenCV remains the fallback.
"""
from __future__ import annotations

import os

import cv2
import numpy as np


class OnnxSurfaceSegmentationProvider:
    name = "onnx-room-segmentation"

    def __init__(self, model_path: str):
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError("Install the optional onnxruntime package to enable model segmentation.") from exc
        if not os.path.isfile(model_path):
            raise RuntimeError(f"Segmentation model file does not exist: {model_path}")
        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape

    def predict(self, image: np.ndarray, mode: str) -> np.ndarray:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        original_height, original_width = rgb.shape[:2]
        model_height = self.input_shape[2] if isinstance(self.input_shape[2], int) else original_height
        model_width = self.input_shape[3] if isinstance(self.input_shape[3], int) else original_width
        if (model_height, model_width) != (original_height, original_width):
            rgb = cv2.resize(rgb, (model_width, model_height), interpolation=cv2.INTER_AREA)
        mode_plane = np.full((*rgb.shape[:2], 1), 0.0 if mode == "floor" else 1.0, dtype=np.float32)
        tensor = np.concatenate([rgb, mode_plane], axis=2).transpose(2, 0, 1)[None, ...]
        output = np.asarray(self.session.run([self.output_name], {self.input_name: tensor})[0], dtype=np.float32)
        if output.ndim != 4 or output.shape[0] != 1 or output.shape[1] != 1:
            raise RuntimeError("ONNX model output must have shape [1, 1, H, W].")
        probabilities = output[0, 0]
        if probabilities.min() < 0.0 or probabilities.max() > 1.0:
            probabilities = 1.0 / (1.0 + np.exp(-np.clip(probabilities, -30, 30)))
        if probabilities.shape != (original_height, original_width):
            probabilities = cv2.resize(probabilities, (original_width, original_height), interpolation=cv2.INTER_LINEAR)
        return probabilities


def get_segmentation_provider():
    model_path = os.getenv("SURFACE_SEGMENTATION_MODEL", "").strip()
    if not model_path:
        return None
    return OnnxSurfaceSegmentationProvider(model_path)
