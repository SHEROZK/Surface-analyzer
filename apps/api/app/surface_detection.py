"""Heuristic room-surface proposals for floor and wall planes.

These algorithms produce editable proposals, not semantic guarantees. Replaceable
behind the same API when a trained segmentation model is introduced.
"""
from __future__ import annotations

import cv2
import numpy as np


class SurfaceDetectionError(ValueError):
    """Raised when an image does not contain a sufficiently clear surface proposal."""


def _validate_and_resize(image: np.ndarray) -> np.ndarray:
    if image is None or not isinstance(image, np.ndarray) or image.ndim != 3 or image.shape[2] != 3:
        raise SurfaceDetectionError("Image must be a decoded three-channel color image.")
    h, w = image.shape[:2]
    if min(w, h) < 120:
        raise SurfaceDetectionError("Room photo is too small for surface detection.")
    scale = min(1.0, 1100.0 / max(w, h))
    if scale < 1:
        image = cv2.resize(image, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)
    return image


def _grabcut_proposal(image: np.ndarray, mode: str) -> dict:
    image = _validate_and_resize(image)
    h, w = image.shape[:2]
    mask = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)
    if mode == "floor":
        mask[int(h * .43):, :] = cv2.GC_PR_FGD
        mask[int(h * .91):, :] = cv2.GC_FGD
        mask[:int(h * .34), :] = cv2.GC_BGD
        cv2.ellipse(mask, (w // 2, int(h * .78)), (max(8, int(w * .22)), max(8, int(h * .13))), 0, 0, 360, cv2.GC_PR_FGD, -1)
        hard_bg_end, min_area, touch = int(h * .38), .035, "bottom"
    else:
        # Wall plane generally occupies the middle of a room photograph.
        # Leave ceiling, floor, bed/furniture bands as probable background.
        mask[int(h * .16):int(h * .86), int(w * .025):int(w * .975)] = cv2.GC_PR_FGD
        mask[int(h * .28):int(h * .70), int(w * .20):int(w * .80)] = cv2.GC_FGD
        mask[:int(h * .12), :] = cv2.GC_BGD
        mask[int(h * .92):, :] = cv2.GC_BGD
        hard_bg_end, min_area, touch = int(h * .14), .06, "middle"
    work = cv2.bilateralFilter(image, 7, 35, 35)
    bg_model, fg_model = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(work, mask, None, bg_model, fg_model, 6, cv2.GC_INIT_WITH_MASK)
    except cv2.error as exc:
        raise SurfaceDetectionError(f"The {mode} boundary was too ambiguous to segment.") from exc
    binary = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    if mode == "floor":
        binary[:hard_bg_end, :] = 0
    else:
        binary[:hard_bg_end, :] = 0
        binary[int(h * .92):, :] = 0
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    candidates = []
    for label in range(1, count):
        x, y, cw, ch, area = stats[label]
        if area < h * w * min_area:
            continue
        if mode == "floor":
            valid = y + ch >= int(h * .94)
        else:
            # A wall proposal should span a meaningful central region, not a
            # small object; score central occupancy and area.
            cx, cy = x + cw / 2, y + ch / 2
            valid = int(w * .12) < cx < int(w * .88) and int(h * .20) < cy < int(h * .82)
        if valid:
            candidates.append((int(area), label))
    if not candidates:
        guidance = "wider room photo or outline it manually" if mode == "floor" else "clearer view of the wall or outline it manually"
        raise SurfaceDetectionError(f"A clear {mode} boundary was not found. Try a {guidance}.")
    area, label = max(candidates)
    component = np.where(labels == label, 255, 0).astype(np.uint8)
    contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise SurfaceDetectionError(f"The {mode} boundary was too ambiguous to outline.")
    contour = max(contours, key=cv2.contourArea)
    perimeter = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, max(2.0, perimeter * .006), True).reshape(-1, 2)
    if len(approx) > 32:
        approx = cv2.approxPolyDP(contour, max(3.0, perimeter * .012), True).reshape(-1, 2)
    if len(approx) < 3:
        raise SurfaceDetectionError(f"The {mode} boundary was too ambiguous to outline.")
    points = [{"x": round(float(x) / w, 5), "y": round(float(y) / h, 5)} for x, y in approx]
    area_ratio = float(area) / float(h * w)
    edge_band = component[int(h * .94):, :] if mode == "floor" else component[int(h * .20):int(h * .80), int(w * .20):int(w * .80)]
    coverage = float(np.count_nonzero(edge_band)) / float(max(1, edge_band.size))
    confidence = max(.15, min(.82, .22 + min(area_ratio, .70) * .58 + coverage * .18))
    warnings = []
    if area_ratio > .78:
        warnings.append(f"The proposed {mode} covers most of the image; check for overlap.")
    if len(points) > 20:
        warnings.append("The boundary is irregular; refine it before rendering.")
    if mode == "wall":
        warnings.append("Wall detection is a heuristic proposal; check around furniture, curtains, fixtures and ceiling edges.")
    return {"points": points, "confidence": round(confidence, 2), "area_ratio": round(area_ratio, 3),
            "method": f"opencv-grabcut-{mode}-prior-v1", "warnings": warnings}


def detect_floor_boundary(image: np.ndarray) -> dict:
    return _grabcut_proposal(image, "floor")


def detect_wall_boundary(image: np.ndarray) -> dict:
    return _grabcut_proposal(image, "wall")
