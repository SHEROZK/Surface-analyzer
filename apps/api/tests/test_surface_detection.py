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
    assert result["method"] == "opencv-grabcut-floor-prior-v2"
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
