"""Semantic/heuristic room-surface proposals with explicit occlusion proposals."""
from __future__ import annotations

import os

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


def _contour_points(component: np.ndarray, max_points: int = 32) -> list[dict]:
    contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    contour = max(contours, key=cv2.contourArea)
    perimeter = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, max(2.0, perimeter * .006), True).reshape(-1, 2)
    if len(approx) > max_points:
        approx = cv2.approxPolyDP(contour, max(3.0, perimeter * .012), True).reshape(-1, 2)
    if len(approx) < 3:
        return []
    h, w = component.shape
    return [{"x": round(float(x) / w, 5), "y": round(float(y) / h, 5)} for x, y in approx]


def _occlusion_proposals(class_map: np.ndarray, confidence_map: np.ndarray, id2label: dict) -> list[dict]:
    from .segmentation_provider import DEFAULT_OCCLUSION_LABELS, normalize_label

    configured = os.getenv("SURFACE_OCCLUSION_LABELS", "").strip()
    occlusion_names = (
        {normalize_label(item) for item in configured.split(",") if item.strip()}
        if configured else DEFAULT_OCCLUSION_LABELS
    )
    h, w = class_map.shape
    proposals = []
    for class_id, raw_label in id2label.items():
        label_name = normalize_label(raw_label)
        if label_name not in occlusion_names:
            continue
        binary = (class_map == int(class_id)).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
        for component_id in range(1, count):
            x, y, cw, ch, area = stats[component_id]
            if area < max(24, int(h * w * .0015)):
                continue
            component = np.where(labels == component_id, 255, 0).astype(np.uint8)
            points = _contour_points(component, max_points=20)
            if len(points) < 3:
                continue
            confidence = float(np.mean(confidence_map[labels == component_id]))
            proposals.append({
                "label": label_name,
                "points": points,
                "confidence": round(confidence, 3),
                "area_ratio": round(float(area) / float(h * w), 4),
                "bbox": {
                    "x": round(float(x) / w, 5), "y": round(float(y) / h, 5),
                    "width": round(float(cw) / w, 5), "height": round(float(ch) / h, 5),
                },
            })
    proposals.sort(key=lambda item: item["area_ratio"], reverse=True)
    return proposals[:20]


def _grabcut_proposal(image: np.ndarray, mode: str) -> dict:
    image = _validate_and_resize(image)
    h, w = image.shape[:2]
    mask = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)
    if mode == "floor":
        mask[int(h * .43):, :] = cv2.GC_PR_FGD
        mask[int(h * .91):, :] = cv2.GC_FGD
        mask[:int(h * .34), :] = cv2.GC_BGD
        cv2.ellipse(mask, (w // 2, int(h * .78)), (max(8, int(w * .22)), max(8, int(h * .13))), 0, 0, 360, cv2.GC_PR_FGD, -1)
        hard_bg_end, min_area = int(h * .38), .035
    else:
        mask[int(h * .16):int(h * .86), int(w * .025):int(w * .975)] = cv2.GC_PR_FGD
        mask[int(h * .28):int(h * .70), int(w * .20):int(w * .80)] = cv2.GC_FGD
        mask[:int(h * .12), :] = cv2.GC_BGD
        mask[int(h * .92):, :] = cv2.GC_BGD
        hard_bg_end, min_area = int(h * .14), .06
    work = cv2.bilateralFilter(image, 7, 35, 35)
    bg_model, fg_model = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(work, mask, None, bg_model, fg_model, 6, cv2.GC_INIT_WITH_MASK)
    except cv2.error as exc:
        raise SurfaceDetectionError(f"The {mode} boundary was too ambiguous to segment.") from exc
    binary = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    binary[:hard_bg_end, :] = 0
    if mode == "wall":
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
            cx, cy = x + cw / 2, y + ch / 2
            valid = int(w * .12) < cx < int(w * .88) and int(h * .20) < cy < int(h * .82)
        if valid:
            candidates.append((int(area), label))
    if not candidates:
        guidance = "wider room photo or outline it manually" if mode == "floor" else "clearer view of the wall or outline it manually"
        raise SurfaceDetectionError(f"A clear {mode} boundary was not found. Try a {guidance}.")
    area, label = max(candidates)
    component = np.where(labels == label, 255, 0).astype(np.uint8)
    points = _contour_points(component)
    if len(points) < 3:
        raise SurfaceDetectionError(f"The {mode} boundary was too ambiguous to outline.")
    area_ratio = float(area) / float(h * w)
    edge_band = component[int(h * .94):, :] if mode == "floor" else component[int(h * .20):int(h * .80), int(w * .20):int(w * .80)]
    coverage = float(np.count_nonzero(edge_band)) / float(max(1, edge_band.size))
    confidence = max(.15, min(.82, .22 + min(area_ratio, .70) * .58 + coverage * .18))
    warnings = []
    if area_ratio > .78:
        warnings.append(f"The proposed {mode} covers most of the image; check for overlap.")
    if len(points) > 20:
        warnings.append("The boundary is irregular; refine it before rendering.")
    warnings.append(f"{mode.title()} detection is a heuristic proposal; review and refine the boundary.")
    return {"points": points, "confidence": round(confidence, 2), "area_ratio": round(area_ratio, 3),
            "method": f"opencv-grabcut-{mode}-prior-v1", "occlusions": [], "warnings": warnings}


def _model_proposal(image: np.ndarray, mode: str, provider) -> dict:
    image = _validate_and_resize(image)
    scene = provider.predict_scene(image) if hasattr(provider, "predict_scene") else None
    probabilities = (
        provider.predict(image, mode) if scene is None else
        scene["probabilities"][_target_class_id(scene["id2label"], mode)]
    )
    if not isinstance(probabilities, np.ndarray) or probabilities.ndim != 2:
        raise SurfaceDetectionError("Segmentation provider must return a two-dimensional probability mask.")
    if probabilities.shape != image.shape[:2]:
        probabilities = cv2.resize(probabilities.astype(np.float32), (image.shape[1], image.shape[0]), interpolation=cv2.INTER_LINEAR)
    if not np.isfinite(probabilities).all():
        raise SurfaceDetectionError("Segmentation provider returned invalid probability values.")

    occlusions = []
    if scene is not None:
        class_map = scene["class_map"]
        confidence_map = scene["confidence_map"]
        if class_map.shape != image.shape[:2] or confidence_map.shape != image.shape[:2]:
            raise SurfaceDetectionError("Segmentation provider returned inconsistent scene-map dimensions.")
        occlusions = _occlusion_proposals(class_map, confidence_map, scene["id2label"])
        from .segmentation_provider import DEFAULT_OCCLUSION_LABELS, normalize_label
        configured = os.getenv("SURFACE_OCCLUSION_LABELS", "").strip()
        occlusion_names = (
            {normalize_label(item) for item in configured.split(",") if item.strip()}
            if configured else DEFAULT_OCCLUSION_LABELS
        )
        occluder_ids = [int(class_id) for class_id, name in scene["id2label"].items()
                        if normalize_label(name) in occlusion_names]
        if occluder_ids:
            probabilities = probabilities.copy()
            # Exclude every pixel of an occluder class, even when a small object
            # is too small to be emitted as a separate polygon proposal.
            probabilities[np.isin(class_map, occluder_ids)] = 0.0

    binary = (probabilities >= 0.5).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    candidates = []
    h, w = binary.shape
    for label in range(1, count):
        x, y, cw, ch, area = stats[label]
        if area < h * w * (0.025 if mode == "floor" else 0.04):
            continue
        if mode == "floor" and y + ch < int(h * 0.85):
            continue
        if mode == "wall":
            cx, cy = x + cw / 2, y + ch / 2
            if not (w * .08 < cx < w * .92 and h * .12 < cy < h * .88):
                continue
        candidates.append((int(area), label))
    if not candidates:
        raise SurfaceDetectionError(f"The segmentation model did not find a usable {mode} region. Refine the outline manually.")
    area, label = max(candidates)
    component = np.where(labels == label, 255, 0).astype(np.uint8)
    points = _contour_points(component)
    if len(points) < 3:
        raise SurfaceDetectionError("The segmentation model produced an unusable boundary.")
    warnings = [
        "AI-generated boundary: review furniture edges, rugs, fixtures and reflections before applying material.",
    ]
    if scene is None:
        warnings.append("This checkpoint returns a binary surface mask; separate occlusion masks are unavailable.")
    elif occlusions:
        warnings.append(f"Detected {len(occlusions)} potential occluding object regions. Review their masks before rendering.")
    return {
        "points": points, "confidence": round(float(np.mean(probabilities[component > 0])), 2),
        "area_ratio": round(float(area) / float(h * w), 3),
        "method": f"{provider.name}-{mode}-v2",
        "occlusions": occlusions,
        "warnings": warnings,
    }


def _target_class_id(id2label: dict, mode: str) -> int:
    from .segmentation_provider import _label_id_for_mode
    return _label_id_for_mode(id2label, mode)


def detect_floor_boundary(image: np.ndarray, provider=None) -> dict:
    return _model_proposal(image, "floor", provider) if provider is not None else _grabcut_proposal(image, "floor")


def detect_wall_boundary(image: np.ndarray, provider=None) -> dict:
    return _model_proposal(image, "wall", provider) if provider is not None else _grabcut_proposal(image, "wall")
