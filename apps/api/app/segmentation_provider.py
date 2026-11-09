"""Local semantic segmentation adapters for self-hosted room analysis.

No room image is sent to a hosted inference service. Checkpoint and training-data
licenses must be reviewed independently before commercial deployment.
"""
from __future__ import annotations

import os
import re

import cv2
import numpy as np


DEFAULT_OCCLUSION_LABELS = {
    "bed", "cabinet", "curtain", "chair", "sofa", "shelf", "armchair",
    "seat", "desk", "wardrobe", "lamp", "bathtub", "cushion", "box",
    "chest of drawers", "refrigerator", "pool table", "pillow", "screen door",
    "table", "plant", "person", "painting", "mirror", "windowpane", "door",
    "sink", "fireplace", "counter", "monitor", "vase", "shower", "radiator",
    "rug", "carpet",
}


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower().replace("_", " ").replace("-", " "))


def _label_id_for_mode(id2label: dict, mode: str) -> int:
    if mode not in {"floor", "wall"}:
        raise ValueError("Mode must be floor or wall.")
    wanted = {"floor": {"floor", "flooring"}, "wall": {"wall", "walls"}}[mode]
    for raw_id, raw_label in id2label.items():
        if normalize_label(raw_label) in wanted:
            return int(raw_id)
    raise RuntimeError(
        f"The selected segmentation checkpoint has no {mode!r} class in id2label. "
        "Choose a checkpoint trained with floor and wall semantic classes."
    )


class OnnxSurfaceSegmentationProvider:
    """Legacy binary ONNX adapter (NCHW RGB plus a floor/wall mode plane)."""

    name = "onnx-room-segmentation"

    def __init__(self, model_path: str):
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError("Install the optional onnxruntime package to enable ONNX segmentation.") from exc
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


class TransformersSemanticSegmentationProvider:
    """Local Hugging Face semantic model exposing floor/wall and object classes."""

    name = "transformers-semantic-segmentation"

    def __init__(self, model_id: str):
        if not model_id.strip():
            raise RuntimeError("Set SURFACE_SEGMENTATION_MODEL_ID to a compatible local semantic segmentation checkpoint.")
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
        except ImportError as exc:
            raise RuntimeError("Install apps/api/requirements-ai.txt to enable Transformers segmentation.") from exc

        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = AutoImageProcessor.from_pretrained(model_id)
        self.model = AutoModelForSemanticSegmentation.from_pretrained(model_id).eval().to(self.device)
        self.id2label = {int(k): v for k, v in self.model.config.id2label.items()}
        self.class_ids = {normalize_label(label): class_id for class_id, label in self.id2label.items()}
        if self.device == "cuda":
            self.model = self.model.half()

    def predict_scene(self, image: np.ndarray) -> dict:
        from PIL import Image

        if image is None or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Expected a decoded three-channel room image.")
        height, width = image.shape[:2]
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        inputs = self.processor(images=Image.fromarray(rgb), return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        if self.device == "cuda":
            inputs = {key: value.half() if value.is_floating_point() else value for key, value in inputs.items()}

        with self.torch.inference_mode():
            logits = self.model(**inputs).logits
            logits = self.torch.nn.functional.interpolate(
                logits.float(), size=(height, width), mode="bilinear", align_corners=False
            )
            probabilities = self.torch.softmax(logits, dim=1)[0]
            confidence, class_map = probabilities.max(dim=0)

        result = {
            "class_map": class_map.cpu().numpy().astype(np.int32),
            "confidence_map": confidence.cpu().numpy().astype(np.float32),
            "id2label": self.id2label,
            "probabilities": probabilities.cpu().numpy().astype(np.float32),
        }
        if result["class_map"].shape != (height, width) or not np.isfinite(result["confidence_map"]).all():
            raise RuntimeError("Semantic segmentation model returned an invalid scene map.")
        return result

    def predict(self, image: np.ndarray, mode: str) -> np.ndarray:
        scene = self.predict_scene(image)
        class_id = _label_id_for_mode(scene["id2label"], mode)
        return scene["probabilities"][class_id]


def get_segmentation_provider():
    backend = os.getenv("SURFACE_SEGMENTATION_BACKEND", "").strip().lower()
    if backend == "transformers":
        model_id = os.getenv("SURFACE_SEGMENTATION_MODEL_ID", "").strip()
        return TransformersSemanticSegmentationProvider(model_id)
    if backend == "onnx":
        model_path = os.getenv("SURFACE_SEGMENTATION_MODEL", "").strip()
        if not model_path:
            raise RuntimeError("Set SURFACE_SEGMENTATION_MODEL to the ONNX model file path.")
        return OnnxSurfaceSegmentationProvider(model_path)
    model_path = os.getenv("SURFACE_SEGMENTATION_MODEL", "").strip()
    return OnnxSurfaceSegmentationProvider(model_path) if model_path else None
