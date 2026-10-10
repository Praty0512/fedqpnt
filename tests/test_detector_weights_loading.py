"""FIX7 B1: a missing/unreadable detector-weights file must raise, never silently yield an untrained detector."""
import numpy as np
import pytest

from fedqpnt.node.methods import load_detector_weights, make_agent_config, save_detector_weights


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_detector_weights(tmp_path / "nope.npz")


def test_make_agent_config_missing_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        make_agent_config("fedqpnt_local", detector_weights_path=tmp_path / "nope.npz")


def test_explicit_none_is_untrained_ok():
    cfg = make_agent_config("fedqpnt_local", detector_weights_path=None)
    assert cfg.detector_weights is None


def test_corrupt_file_raises(tmp_path):
    p = tmp_path / "bad.npz"
    p.write_bytes(b"not an npz")
    with pytest.raises(ValueError):
        load_detector_weights(p)


def test_roundtrip(tmp_path):
    p = tmp_path / "w.npz"
    save_detector_weights(p, {"a": np.ones(3)})
    assert np.array_equal(load_detector_weights(p)["a"], np.ones(3))
