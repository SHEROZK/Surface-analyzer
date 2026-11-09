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
