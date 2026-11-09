import numpy as np
import pytest
from app.depth_estimation import DepthAnythingV2

def test_depth_estimator_normalizes_depth_to_uint8(monkeypatch):
    class Tensor:
        def __init__(self, data): self.data = data
        def unsqueeze(self, axis): return self
        def squeeze(self): return self
        def float(self): return self
        def cpu(self): return self
        def numpy(self): return self.data
    class Functional:
        @staticmethod
        def interpolate(*args, **kwargs): return Tensor(np.arange(100, dtype=np.float32).reshape(10, 10))
    class Torch:
        nn = type("NN", (), {"functional": Functional})
        class inference_mode:
            def __enter__(self): pass
            def __exit__(self, *args): pass
    estimator = object.__new__(DepthAnythingV2)
    estimator.torch = Torch
    estimator.device = "cpu"
    estimator.processor = lambda **kwargs: {"pixel_values": Tensor(None)}
    estimator.model = lambda **kwargs: type("Output", (), {"predicted_depth": Tensor(None)})()
    result = estimator.predict(np.zeros((10, 10, 3), dtype=np.uint8))
    assert result.shape == (10, 10)
    assert result.dtype == np.uint8
    assert result.min() == 0 and result.max() == 255

def test_missing_ai_dependencies_gives_install_hint(monkeypatch):
    import builtins
    original = builtins.__import__
    def blocked(name, *args, **kwargs):
        if name in {"torch", "transformers"}: raise ImportError("blocked")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", blocked)
    with pytest.raises(Exception, match="requirements-ai"):
        DepthAnythingV2()
