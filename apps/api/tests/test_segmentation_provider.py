import pytest

from app.segmentation_provider import _label_id_for_mode


def test_resolves_floor_and_wall_labels_without_hardcoded_class_ids():
    labels = {0: "wall", 1: "building", 3: "floor"}
    assert _label_id_for_mode(labels, "wall") == 0
    assert _label_id_for_mode(labels, "floor") == 3


def test_resolves_normalized_label_names():
    labels = {"4": "Flooring", "8": "walls"}
    assert _label_id_for_mode(labels, "floor") == 4
    assert _label_id_for_mode(labels, "wall") == 8


def test_rejects_checkpoint_without_requested_surface_class():
    with pytest.raises(RuntimeError, match="no 'floor' class"):
        _label_id_for_mode({0: "wall", 1: "ceiling"}, "floor")
