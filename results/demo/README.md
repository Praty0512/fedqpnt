# Live demo: FedQPNT under a displaced-meaconer attack

Runs registry scenario S2-DM (displaced meaconer: attack from t=60 s for 300 s, position walked away up to 500 m)
for three methods (FedQPNT local, undefended, Baseline A detect-and-exclude) on one TUNING seed
(default 531, industrial MEMS IMU, Schuler-tangent world, detector `results/m1/detector_weights_sup_v5.npz`).

    python scripts/demo_attack.py [--seed N] [--grade industrial_mems|tactical]

Runtime: about 1-1.5 min on a laptop (3 processes in parallel). Seeds >= 10000 are refused.
Outputs: `demo_attack_S2DM.png/.pdf` (3 panels: position error, FedQPNT trust state, clock error) and
`demo_attack_S2DM_summary.json`. Other seeds/grades get a suffixed filename.

Notes: the TRUST/DISTRUST/PROBE bands are read from the trust law's state machine (read-only). Traces are
re-collected with the same loop and metric functions as `fedqpnt.node.runner.run_single` (its metrics match
exactly); this is a single seed, so numbers differ from the 30-seed HEADLINE medians.

## Talk track
1. A fake GPS signal slowly drags the receiver away from the truth; the shaded band is the 5-minute attack.
2. An undefended receiver believes it: error grows to several km and timing is off by ~18 microseconds.
3. FedQPNT's detector flags the signal within 2 s, its trust weight drops to the floor, and it coasts on the inertial sensor and quantum accelerometer, so error stays far lower.
4. Every ~70 s it briefly re-tests GNSS (PROBE) and rejects it while it is still fake; once the attack ends, one probe passes and GNSS is re-admitted (t=411 s), snapping the error back to about a metre.
5. Honest caveat: the simple detect-and-exclude baseline is similar here (and better in clock on this seed); FedQPNT's gain is mainly vs the undefended receiver, with the timing and position error bounded during the attack.
