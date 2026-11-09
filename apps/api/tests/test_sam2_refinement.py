import numpy as np

from app import sam2_refinement


def test_sam2_refinement_is_optional_when_not_configured(monkeypatch):
    monkeypatch.delenv("SURFACE_SAM2_CONFIG", raising=False)
    monkeypatch.delenv("SURFACE_SAM2_CHECKPOINT", raising=False)
    sam2_refinement.get_sam2_refiner.cache_clear()
    proposals = [{"label": "sofa", "points": [{"x": 0.1, "y": 0.2}, {"x": 0.4, "y": 0.2}, {"x": 0.4, "y": 0.6}]}]

    refined, warning = sam2_refinement.refine_occlusions(
        np.zeros((80, 120, 3), dtype=np.uint8), proposals
    )

    assert refined == proposals
    assert warning is None
    sam2_refinement.get_sam2_refiner.cache_clear()


def test_sam2_requires_both_local_model_settings(monkeypatch):
    monkeypatch.setenv("SURFACE_SAM2_CONFIG", "configs/sam2.1/sam2.1_hiera_l.yaml")
    monkeypatch.delenv("SURFACE_SAM2_CHECKPOINT", raising=False)
    sam2_refinement.get_sam2_refiner.cache_clear()

    try:
        try:
            sam2_refinement.get_sam2_refiner()
        except RuntimeError as exc:
            assert "Set both SURFACE_SAM2_CONFIG and SURFACE_SAM2_CHECKPOINT" in str(exc)
        else:
            raise AssertionError("Expected incomplete SAM 2 configuration to fail")
    finally:
        sam2_refinement.get_sam2_refiner.cache_clear()
