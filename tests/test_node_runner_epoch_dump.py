"""D-064: node_runner.py per-epoch telemetry is additive (see
scripts/h2_abrupt_golden_run.py for the tiny 1-node golden mission)."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from h2_abrupt_golden_run import GOLDEN, NEW_KEYS, golden_view, run_golden_mission

ONSET_S, DUR_S = 60.0, 60.0   # must match run_golden_mission's attack


@pytest.fixture(scope="module")
def n0():
    return run_golden_mission()


def test_epoch_keys_present_consistent_and_match_oracle(n0):
    """PERMANENT: new epoch_* keys exist, lengths match, epoch_t strictly
    increasing at 1 Hz epochs, epoch_active equals the attack schedule."""
    for k in NEW_KEYS:
        assert k in n0
    t, a, p = (np.asarray(n0[k]) for k in NEW_KEYS)
    assert len(t) == len(a) == len(p) > 0
    assert np.all(np.diff(t) > 0)
    assert len(t) < n0["n_ticks"]                      # 1 Hz epochs, not 100 Hz ticks
    assert np.allclose(np.diff(t), 1.0, atol=1e-6)     # gnss_rate_hz = 1
    assert np.array_equal(a, (t >= ONSET_S) & (t < ONSET_S + DUR_S))   # oracle label
    assert np.all((p >= 0) & (p <= 1))


@pytest.mark.skip(reason="one-shot D-064 bit-identity check, PASSED at 85e0e8e 2026-09-29 (golden captured at 906ae98); later core changes invalidate the golden")
def test_existing_keys_bit_identical_to_golden(n0):
    golden = json.loads(GOLDEN.read_text())
    got = json.loads(json.dumps(golden_view(n0), default=str))
    assert set(got) == set(golden)
    for k in golden:   # serialised compare so NaN == NaN
        assert json.dumps(got[k]) == json.dumps(golden[k]), f"existing key changed: {k}"
