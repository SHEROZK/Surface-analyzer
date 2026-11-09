"""Heuristic room-floor segmentation.

This module deliberately returns a proposal, not a semantic guarantee. A learned
segmentation model can replace this implementation behind the same function.
"""
from __future__ import annotations

import cv2
import numpy as np


class SurfaceDetectionError(ValueError):
    """Raised when an image does not contain a sufficiently clear floor proposal."""


def detect_floor_boundary(image: np.ndarray) -> dict:
    if image is None or not isinstance(image, np.ndarray) or image.ndim != 3 or image.shape[2] != 3:
        raise SurfaceDetectionError("Image must be a decoded three-channel color image.")

    original_h, original_w = image.shape[:2]
    if min(original_w, original_h) < 120:
        raise SurfaceDetectionError("Room photo is too small for surface detection.")

    scale = min(1.0, 1100.0 / max(original_w, original_h))
    if scale < 1:
        image = cv2.resize(
            image,
            (max(1, round(original_w * scale)), max(1, round(original_h * scale))),
            interpolation=cv2.INTER_AREA,
        )

    h, w = image.shape[:2]
    # The bottom band is a weak prior, not a hard polygon: GrabCut can still
    # classify furniture and rugs as background using color/edge evidence.
    mask = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)
    mask[int(h * 0.43):, :] = cv2.GC_PR_FGD
    mask[int(h * 0.91):, :] = cv2.GC_FGD
    mask[:int(h * 0.34), :] = cv2.GC_BGD

    # Preserve likely floor near the lower center in photos where the bottom
    # edge is partly occluded by furniture.
    cv2.ellipse(
        mask,
        (w // 2, int(h * 0.78)),
        (max(8, int(w * 0.22)), max(8, int(h * 0.13))),
        0, 0, 360, cv2.GC_PR_FGD, -1,
    )

    # Reduce high-frequency texture before segmentation while retaining
    # boundaries between wall, furniture and floor.
    work = cv2.bilateralFilter(image, 7, 35, 35)
    bg_model = np.zeros((1, 65), np.float64)
    fg_model = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(work, mask, None, bg_model, fg_model, 5, cv2.GC_INIT_WITH_MASK)
    except cv2.error as exc:
        raise SurfaceDetectionError("The room image was too ambiguous to segment.") from exc

    binary = np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0
    ).astype(np.uint8)
    binary[:int(h * 0.38), :] = 0
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    candidates = []
    for label in range(1, count):
        x, y, cw, ch, area = stats[label]
        bottom_touch = y + ch >= int(h * 0.94)
        if bottom_touch and area >= h * w * 0.035:
            candidates.append((int(area), label))
    if not candidates:
        raise SurfaceDetectionError(
            "A clear floor boundary was not found. Try a wider room photo or outline it manually."
        )

    area, label = max(candidates)
    component = np.where(labels == label, 255, 0).astype(np.uint8)
    contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise SurfaceDetectionError("The floor boundary was too ambiguous to outline.")
    contour = max(contours, key=cv2.contourArea)
    perimeter = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, max(2.0, perimeter * 0.006), True).reshape(-1, 2)

    # Keep the polygon manageable for the browser editor without destroying
    # corners needed for perspective alignment.
    if len(approx) > 32:
        approx = cv2.approxPolyDP(contour, max(3.0, perimeter * 0.012), True).reshape(-1, 2)
    if len(approx) < 3:
        raise SurfaceDetectionError("The floor boundary was too ambiguous to outline.")

    points = [
        {"x": round(float(x) / w, 5), "y": round(float(y) / h, 5)}
        for x, y in approx
    ]
    area_ratio = float(area) / float(h * w)
    bottom_band = component[int(h * 0.94):, :]
    bottom_coverage = float(np.count_nonzero(bottom_band)) / float(max(1, bottom_band.size))
    # This is a ranking heuristic, not a calibrated probability.
    confidence = max(
        0.15,
        min(0.82, 0.22 + min(area_ratio, 0.70) * 0.58 + bottom_coverage * 0.18),
    )
    warnings = []
    if area_ratio > 0.78:
        warnings.append("The proposed floor covers most of the image; check for furniture or wall overlap.")
    if len(points) > 20:
        warnings.append("The boundary is irregular; refine the outline before rendering.")

    return {
        "points": points,
        "confidence": round(confidence, 2),
        "area_ratio": round(area_ratio, 3),
        "method": "opencv-grabcut-floor-prior-v2",
        "warnings": warnings,
    }
