import numpy as np
import pytest

from app.segmentation_provider import _label_id_for_mode, normalize_label
from app.surface_detection import detect_floor_boundary


def test_resolves_floor_and_wall_labels_without_hardcoded_class_ids():
    labels = {0: "wall", 1: "building", 3: "floor"}
    assert _label_id_for_mode(labels, "wall") == 0
    assert _label_id_for_mode(labels, "floor") == 3


def test_resolves_normalized_label_names():
    labels = {"4": "Flooring", "8": "walls"}
    assert _label_id_for_mode(labels, "floor") == 4
    assert _label_id_for_mode(labels, "wall") == 8
    assert normalize_label("chest_of_drawers") == "chest of drawers"


def test_rejects_checkpoint_without_requested_surface_class():
    with pytest.raises(RuntimeError, match="no 'floor' class"):
        _label_id_for_mode({0: "wall", 1: "ceiling"}, "floor")


def test_rejects_unknown_surface_mode():
    with pytest.raises(ValueError, match="floor or wall"):
        _label_id_for_mode({0: "floor"}, "ceiling")


def test_scene_segmentation_excludes_furniture_and_returns_occlusion_polygons(monkeypatch):
    class FakeSceneProvider:
        name = "fake-scene-model"

        def predict_scene(self, image):
            height, width = image.shape[:2]
            class_map = np.zeros((height, width), dtype=np.int32)
            class_map[:height // 2] = 1  # wall
            class_map[height // 2:, :] = 2  # floor
            class_map[height // 2 + 20:height // 2 + 100, width // 3:width // 3 + 100] = 3  # chair
            confidence = np.full((height, width), .92, dtype=np.float32)
            probabilities = np.zeros((4, height, width), dtype=np.float32)
            probabilities[0] = .02
            probabilities[1, :height // 2] = .95
            probabilities[2, height // 2:, :] = .95
            probabilities[2, height // 2 + 20:height // 2 + 100, width // 3:width // 3 + 100] = .01
            probabilities[3, height // 2 + 20:height // 2 + 100, width // 3:width // 3 + 100] = .96
            return {
                "class_map": class_map,
                "confidence_map": confidence,
                "id2label": {0: "background", 1: "wall", 2: "floor", 3: "chair"},
                "probabilities": probabilities,
            }

    image = np.zeros((300, 420, 3), dtype=np.uint8)
    result = detect_floor_boundary(image, FakeSceneProvider())

    assert result["method"] == "fake-scene-model-floor-v2"
    assert result["occlusions"]
    assert result["occlusions"][0]["label"] == "chair"
    assert len(result["occlusions"][0]["points"]) >= 3
    assert result["area_ratio"] < .5
    assert any("occluding object" in warning for warning in result["warnings"])
