import numpy as np
import pytest

from app.sam2_refinement import Sam2OcclusionRefiner


class FakePredictor:
    def set_image(self, image):
        self.image = image

    def predict(self, point_coords, point_labels, multimask_output):
        mask = np.zeros((1, 120, 160), dtype=np.uint8)
        mask[0, 25:100, 30:140] = 1
        return mask, np.asarray([0.91], dtype=np.float32), None


def test_sam2_point_refinement_returns_normalized_editable_polygon():
    refiner = object.__new__(Sam2OcclusionRefiner)
    refiner.predictor = FakePredictor()
    refiner.device = "cpu"
    image = np.zeros((120, 160, 3), dtype=np.uint8)

    result = refiner.refine_points(image, [
        {"x": 0.5, "y": 0.5, "label": 1},
        {"x": 0.05, "y": 0.05, "label": 0},
    ])

    assert result["method"] == "sam2-point-prompt"
    assert result["confidence"] == pytest.approx(0.91)
    assert len(result["points"]) >= 3
    assert result["bbox"] == {
        "x": 0.1875, "y": 0.20833, "width": 0.6875, "height": 0.625
    }
    assert all(0 <= point["x"] <= 1 and 0 <= point["y"] <= 1 for point in result["points"])


def test_sam2_point_refinement_requires_positive_prompt():
    refiner = object.__new__(Sam2OcclusionRefiner)
    refiner.predictor = FakePredictor()
    refiner.device = "cpu"
    image = np.zeros((120, 160, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match="at least one positive"):
        refiner.refine_points(image, [{"x": 0.1, "y": 0.1, "label": 0}])



def test_sam2_point_refinement_rejects_masks_that_ignore_negative_prompts():
    refiner = object.__new__(Sam2OcclusionRefiner)
    refiner.predictor = FakePredictor()
    refiner.device = "cpu"
    image = np.zeros((120, 160, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match="could not satisfy all include/exclude"):
        refiner.refine_points(image, [
            {"x": 0.5, "y": 0.5, "label": 1},
            {"x": 0.5, "y": 0.5, "label": 0},
        ])
