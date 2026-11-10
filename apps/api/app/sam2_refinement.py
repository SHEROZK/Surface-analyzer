"""Optional local SAM 2 refinement for semantic object masks.

Semantic segmentation decides *what* an object is. SAM 2 refines the
corresponding box prompt into a more precise boundary. We keep this optional
because its checkpoint is large and must be stored on the customer's server.
"""
from __future__ import annotations

import os
from functools import lru_cache

import cv2
import numpy as np


class Sam2OcclusionRefiner:
    def __init__(self, config_path: str, checkpoint_path: str):
        if not config_path.strip():
            raise RuntimeError("Set SURFACE_SAM2_CONFIG to an installed SAM 2 Hydra config name.")
        if not os.path.isfile(checkpoint_path):
            raise RuntimeError(f"SAM 2 checkpoint not found: {checkpoint_path}")
        try:
            import torch
            from sam2.build_sam import build_sam2
            from sam2.sam2_image_predictor import SAM2ImagePredictor
        except ImportError as exc:
            raise RuntimeError(
                "SAM 2 refinement is configured but the optional sam2 package is not installed. "
                "Install apps/api/requirements-sam2.txt."
            ) from exc

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = build_sam2(config_path, checkpoint_path, device=self.device)
        self.predictor = SAM2ImagePredictor(self.model)

    def refine_points(self, image: np.ndarray, points: list[dict]) -> dict:
        """Create an editable surface mask from user positive/negative point prompts."""
        if image is None or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Expected a decoded three-channel image.")
        if not points:
            raise ValueError("Add at least one positive point to guide the mask.")
        height, width = image.shape[:2]
        coords = np.asarray([
            [float(point["x"]) * width, float(point["y"]) * height]
            for point in points
        ], dtype=np.float32)
        labels = np.asarray([int(point.get("label", 1)) for point in points], dtype=np.int32)
        if not np.isin(labels, [0, 1]).all() or not np.any(labels == 1):
            raise ValueError("Provide at least one positive point; labels must be 1 (include) or 0 (exclude).")
        self.predictor.set_image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        masks, scores, _ = self.predictor.predict(
            point_coords=coords, point_labels=labels, multimask_output=True
        )
        if masks is None or len(masks) == 0:
            raise RuntimeError("SAM 2 did not return a usable mask. Add clearer positive and negative points.")
        # Prefer the highest-scoring mask that contains every positive prompt and
        # excludes every negative prompt. Fall back to score only if none qualify.
        valid = []
        for index, mask in enumerate(masks):
            binary = np.asarray(mask, dtype=np.uint8)
            contains_positive = all(binary[min(height - 1, int(y)), min(width - 1, int(x))] > 0
                                    for x, y in coords[labels == 1])
            excludes_negative = all(binary[min(height - 1, int(y)), min(width - 1, int(x))] == 0
                                    for x, y in coords[labels == 0])
            if contains_positive and excludes_negative:
                valid.append(index)
        if not valid and np.any(labels == 0):
            raise ValueError(
                "SAM 2 could not satisfy all include/exclude points. Move conflicting points or add clearer prompts."
            )
        best_index = max(valid, key=lambda i: float(scores[i])) if valid else int(np.argmax(scores))
        binary = np.asarray(masks[best_index], dtype=np.uint8)
        count, components, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        if count <= 1:
            raise RuntimeError("SAM 2 returned an empty surface mask. Add more positive points.")
        positive_pixels = [(min(height - 1, int(y)), min(width - 1, int(x)))
                           for x, y in coords[labels == 1]]
        component_ids = {int(components[y, x]) for y, x in positive_pixels if components[y, x] > 0}
        if component_ids:
            component_id = max(component_ids, key=lambda i: int(stats[i, cv2.CC_STAT_AREA]))
        else:
            component_id = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        component = np.where(components == component_id, 255, 0).astype(np.uint8)
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            raise RuntimeError("Could not convert the SAM 2 mask into an editable boundary.")
        contour = max(contours, key=cv2.contourArea)
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, max(2.0, perimeter * 0.006), True).reshape(-1, 2)
        if len(polygon) < 3:
            raise RuntimeError("The selected mask is too small to form a surface boundary.")
        if len(polygon) > 48:
            polygon = cv2.approxPolyDP(contour, max(3.0, perimeter * 0.012), True).reshape(-1, 2)
        x, y, box_width, box_height = cv2.boundingRect(contour)
        return {
            "points": [{"x": round(float(px) / width, 5), "y": round(float(py) / height, 5)}
                       for px, py in polygon],
            "bbox": {"x": round(x / width, 5), "y": round(y / height, 5),
                     "width": round(box_width / width, 5), "height": round(box_height / height, 5)},
            "confidence": round(float(scores[best_index]), 3),
            "method": "sam2-point-prompt",
            "device": self.device,
            "warnings": ["AI mask generated from your point prompts. Review and correct the boundary before rendering."],
        }

    def refine(self, image: np.ndarray, proposals: list[dict]) -> list[dict]:
        if not proposals:
            return proposals
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        self.predictor.set_image(rgb)
        height, width = image.shape[:2]
        refined = []
        for proposal in proposals:
            bbox = proposal.get("bbox") or {}
            x1 = max(0, min(width - 1, int(round(float(bbox.get("x", 0)) * width))))
            y1 = max(0, min(height - 1, int(round(float(bbox.get("y", 0)) * height))))
            x2 = max(x1 + 1, min(width, int(round((float(bbox.get("x", 0)) + float(bbox.get("width", 0))) * width))))
            y2 = max(y1 + 1, min(height, int(round((float(bbox.get("y", 0)) + float(bbox.get("height", 0))) * height))))
            masks, scores, _ = self.predictor.predict(
                box=np.asarray([x1, y1, x2, y2], dtype=np.float32),
                multimask_output=True,
            )
            if masks is None or len(masks) == 0:
                refined.append(proposal)
                continue
            best_index = int(np.argmax(scores))
            binary = np.asarray(masks[best_index], dtype=np.uint8)
            count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
            if count <= 1:
                refined.append(proposal)
                continue
            component_id = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            component = np.where(labels == component_id, 255, 0).astype(np.uint8)
            contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                refined.append(proposal)
                continue
            contour = max(contours, key=cv2.contourArea)
            perimeter = cv2.arcLength(contour, True)
            points = cv2.approxPolyDP(contour, max(2.0, perimeter * 0.006), True).reshape(-1, 2)
            if len(points) < 3:
                refined.append(proposal)
                continue
            if len(points) > 32:
                points = cv2.approxPolyDP(contour, max(3.0, perimeter * 0.012), True).reshape(-1, 2)
            x, y, w, h = cv2.boundingRect(contour)
            updated = dict(proposal)
            updated["points"] = [
                {"x": round(float(px) / width, 5), "y": round(float(py) / height, 5)}
                for px, py in points
            ]
            updated["bbox"] = {
                "x": round(float(x) / width, 5), "y": round(float(y) / height, 5),
                "width": round(float(w) / width, 5), "height": round(float(h) / height, 5),
            }
            updated["confidence"] = round(float(scores[best_index]), 3)
            updated["refinement"] = "sam2-box-prompt"
            refined.append(updated)
        return refined


@lru_cache(maxsize=1)
def get_sam2_refiner() -> Sam2OcclusionRefiner | None:
    config_path = os.getenv("SURFACE_SAM2_CONFIG", "").strip()
    checkpoint_path = os.getenv("SURFACE_SAM2_CHECKPOINT", "").strip()
    if not config_path and not checkpoint_path:
        return None
    if not config_path or not checkpoint_path:
        raise RuntimeError("Set both SURFACE_SAM2_CONFIG and SURFACE_SAM2_CHECKPOINT to enable SAM 2 refinement.")
    return Sam2OcclusionRefiner(config_path, checkpoint_path)


def refine_occlusions(image: np.ndarray, proposals: list[dict]) -> tuple[list[dict], str | None]:
    if not proposals:
        return proposals, None
    refiner = get_sam2_refiner()
    if refiner is None:
        return proposals, None
    return refiner.refine(image, proposals), f"SAM 2 refined {len(proposals)} object masks locally ({refiner.device})."
