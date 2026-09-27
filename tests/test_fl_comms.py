"""SS4.6 comms model: Gilbert-Elliott loss rate + delay bound + determinism
of the ``stream(seed, node, "comms_up"/"comms_down")`` RNG keys."""
from __future__ import annotations

import numpy as np

from fedqpnt.fl.comms import CommsConfig, uplink_channel, downlink_channel


def test_uplink_channel_deterministic_for_same_seed_node():
    a = uplink_channel(42, "node0")
    b = uplink_channel(42, "node0")
    outcomes_a = [a.send() for _ in range(20)]
    outcomes_b = [b.send() for _ in range(20)]
    for oa, ob in zip(outcomes_a, outcomes_b):
        assert oa.lost == ob.lost
        assert oa.delay_s == ob.delay_s


def test_uplink_and_downlink_streams_are_independent():
    up = uplink_channel(42, "node0")
    down = downlink_channel(42, "node0")
    o_up = [up.send().delay_s for _ in range(10)]
    o_down = [down.send().delay_s for _ in range(10)]
    assert o_up != o_down


def test_delay_never_exceeds_d_max():
    ch = uplink_channel(1, "n", CommsConfig(d_max_s=5.0))
    for _ in range(500):
        out = ch.send()
        assert out.delay_s <= 5.0 + 1e-9
        if out.delay_s >= 5.0:
            assert out.lost


def test_bad_state_loss_rate_much_higher_than_good_state():
    cfg = CommsConfig(p_gb=0.0, p_bg=0.0, loss_g=0.01, loss_b=0.9)  # frozen chain: isolate per-state loss rates
    good = uplink_channel(1, "good", cfg)
    bad_cfg = CommsConfig(p_gb=1.0, p_bg=0.0, loss_g=0.01, loss_b=0.9)
    bad = uplink_channel(1, "bad", bad_cfg)
    bad.send()  # first send flips G->B with p_gb=1.0
    n = 2000
    good_losses = sum(good.send().lost for _ in range(n))
    bad_losses = sum(bad.send().lost for _ in range(n))
    assert bad_losses > good_losses


def test_loss_b_sweep_changes_loss_rate_s9():
    """S9 sweeps loss_B in {0.5, 0.9}; higher loss_B must give a higher
    bad-state loss rate."""
    rates = {}
    for loss_b in (0.5, 0.9):
        cfg = CommsConfig(p_gb=1.0, p_bg=0.0, loss_b=loss_b)
        ch = uplink_channel(7, f"n{loss_b}", cfg)
        ch.send()
        n = 3000
        losses = sum(ch.send().lost for _ in range(n))
        rates[loss_b] = losses / n
    assert rates[0.9] > rates[0.5]
