import numpy as np
import pytest

from app.surface_detection import SurfaceDetectionError, detect_floor_boundary


def test_floor_detector_returns_normalized_polygon_for_simple_room():
    # Synthetic room: a plain wall above a differently colored floor.
    image = np.zeros((300, 420, 3), dtype=np.uint8)
    image[:] = (185, 190, 195)
    image[145:, :] = (75, 105, 135)
    # A small furniture-like obstruction should not prevent a floor proposal.
    image[190:265, 145:265] = (45, 55, 65)

    result = detect_floor_boundary(image)

    assert len(result["points"]) >= 3
    assert len(result["points"]) <= 32
    assert 0.0 < result["area_ratio"] < 1.0
    assert 0.15 <= result["confidence"] <= 0.82
    assert result["method"] == "opencv-grabcut-floor-prior-v1"
    for point in result["points"]:
        assert 0.0 <= point["x"] <= 1.0
        assert 0.0 <= point["y"] <= 1.0


def test_floor_detector_rejects_invalid_image():
    with pytest.raises(SurfaceDetectionError, match="three-channel"):
        detect_floor_boundary(None)


def test_floor_detector_rejects_too_small_image():
    image = np.zeros((80, 100, 3), dtype=np.uint8)
    with pytest.raises(SurfaceDetectionError, match="too small"):
        detect_floor_boundary(image)


def test_wall_detector_returns_normalized_polygon_for_simple_room():
    from app.surface_detection import detect_wall_boundary

    # Ceiling and lower furniture/floor are distinct from the central wall plane.
    image = np.zeros((360, 480, 3), dtype=np.uint8)
    image[:] = (35, 35, 35)
    image[:70, :] = (220, 220, 220)
    image[70:290, 35:445] = (185, 190, 195)
    image[290:, :] = (55, 65, 75)
    # Furniture-like foreground object inside the wall region.
    image[205:285, 160:310] = (35, 45, 55)

    result = detect_wall_boundary(image)

    assert len(result["points"]) >= 3
    assert len(result["points"]) <= 32
    assert 0.0 < result["area_ratio"] < 1.0
    assert result["method"] == "opencv-grabcut-wall-prior-v1"
    assert any("heuristic" in warning.lower() for warning in result["warnings"])
    for point in result["points"]:
        assert 0.0 <= point["x"] <= 1.0
        assert 0.0 <= point["y"] <= 1.0


class FakeSegmentationProvider:
    name = "test-model"

    def predict(self, image, mode):
        mask = np.zeros(image.shape[:2], dtype=np.float32)
        if mode == "floor":
            mask[int(image.shape[0] * .55):, :] = 0.95
        else:
            mask[int(image.shape[0] * .2):int(image.shape[0] * .75), int(image.shape[1] * .1):int(image.shape[1] * .9)] = 0.95
        return mask


def test_model_provider_generates_floor_boundary():
    image = np.zeros((300, 420, 3), dtype=np.uint8)
    result = detect_floor_boundary(image, FakeSegmentationProvider())
    assert result["method"] == "test-model-floor-v2"
    assert result["area_ratio"] > 0.3
    assert len(result["points"]) >= 3
    assert any("AI-generated" in warning for warning in result["warnings"])


def test_model_provider_generates_wall_boundary():
    from app.surface_detection import detect_wall_boundary

    image = np.zeros((360, 480, 3), dtype=np.uint8)
    result = detect_wall_boundary(image, FakeSegmentationProvider())
    assert result["method"] == "test-model-wall-v2"
    assert result["area_ratio"] > 0.3
    assert len(result["points"]) >= 3


def test_model_provider_rejects_invalid_probability_mask():
    class InvalidProvider:
        def predict(self, image, mode):
            return np.full((image.shape[0], image.shape[1]), np.nan, dtype=np.float32)

    image = np.zeros((300, 420, 3), dtype=np.uint8)
    with pytest.raises(SurfaceDetectionError, match="invalid probability"):
        detect_floor_boundary(image, InvalidProvider())
