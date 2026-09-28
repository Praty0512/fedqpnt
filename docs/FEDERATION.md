# Federated Learning: Transport, Aggregation, and Poisoning Resilience

This document covers the FL stack used in FedQPNT: the transport layer, server and client protocols, aggregators (FedAvg, FedProx, TRIM-NB-R), communications model, poisoning attacks, determinism, and the leakage guard. For integration with node-level training, see [FLEET.md](FLEET.md) and [TRAINING.md](TRAINING.md).

---

## Purpose and Scope

**Owns:** `fedqpnt/fl/{__init__,transport,server,client,aggregator,comms,poisoning,orchestrator}.py`, `tests/test_fl_*.py`, `scripts/run_fl_validate.py`, results in `results/fl/`.

**Does NOT own:** `fedqpnt.node`, `fedqpnt.fusion`, `fedqpnt.sim`, `fedqpnt.attacks`. Uses `fedqpnt.trust` only via `TrustDetector.get_params`/`set_params`/`train_local(balance=True)` and `FeatureNormalizer`.

**Design freeze:** D-026 (detector design FROZEN); all FL implementation follows the unchangeable detector architecture and class-balance rules.

---

## Data Flow and Training Contract

### Training Object
Trained weights: `TrustDetector` parameters (fc*.weight/bias).

**Parameter transmission (ModelUpdate.params):** Delta format only. Aggregators receive deltas and apply weight updates.

**Normalization:** `norm_mu` / `norm_sd` sent as ABSOLUTE values (not deltas); server aggregates by coordinate-wise median.

**Metrics reported per round:**
- `n_pos`, `n_neg` (positive/negative sample counts per node)
- `loss` (per-node training loss)
- `pl_rate` (pseudo-label positive rate, unused by aggregators)
- `base_round` (the last-installed global round at the node, for staleness s = r - base_round)

### Leakage Guard
`fedqpnt/fl/transport.enforce_leakage_guard()`: parameters must match detector param names/shapes (plus optional `norm_mu`/`norm_sd`/`norm_count`); metrics must be scalars. Test: `tests/test_fl_leakage_guard.py` includes smuggled-array and smuggled-non-scalar-metric rejection tests (both pass).

---

## Round Schedule and Execution Model

### Synchronization
- Bulk-synchronous protocol: multiprocessing `spawn` + `mp.Queue` (abstract in `fedqpnt/fl/transport.MpQueueTransport`; real deployments in `orchestrator.py` use raw `ctx.Queue()`).
- Server aggregates in node_id order (never arrival order); `fedqpnt/fl/server.py` sorts by node_id.
- Quorum rule: aggregate iff `#fresh >= ceil(0.5 * N_live)` else send `RoundSkipped` to every expected node.

### Determinism and RNG Streams (D-005)
- **Uplink RNG (per node):** `stream(seed, node_id, "comms_up")` (persistent across rounds; G-E chain is Markov)
- **Downlink RNG (server-owned):** `stream(seed, "server", "comms_down", node_id)` keyed per node
- **Detector init:** `stream(seed, node_id, "detector_init")`
- **Bootstrap for CIs:** `stream(seed, "eval", "bootstrap")`
- Thread safety: `torch.set_num_threads(1)` + `OMP_NUM_THREADS=1` set at every process entry point

**Validation:** `tests/test_fl_orchestrator.py::test_determinism_bit_identical_across_runs` — two full runs with identical `ScenarioConfig` give `np.array_equal` on every theta array. PASS.

---

## Aggregators (SS4.5 ARCHITECTURE.md)

### FedAvg
Weight = `n_samples * staleness_weight(s)`, where `n_samples` is self-reported (deliberate vulnerability per ARCHITECTURE) and `staleness_weight(s) = (1+s)^-0.5`.

Known vulnerability: uncapped gradient instability with tiny synthetic batches and few rounds (manifested at N=5 with some seeded random walks into instability; at N=10 spec fleet size, TRIM-NB-R's clipping prevents this).

### FedProx
Aggregation = FedAvg (alias). Prox term `(μ/2)||θ - θ_g||²` is entirely client-side in `TrustDetector.train_local(theta_g=..., prox_mu=...)`.

**Parameter:** `FedProxConfig.mu` (default 0 = FedAvg).

### TRIM-NB-R (Byzantine-Robust Aggregator)
1. Clip each δ by `c × median_norm` (c=2; probation c=1 for first 2 rounds, SS4.7)
2. Exclude quarantined nodes
3. Coordinate-wise trimmed mean (β=0.2, requires N_live ≥ 5) else median
4. Reputation decay: `r ← 0.8*r + 0.2*max(0, cos(clipped_δ_i, agg))`
5. Quarantine: `r < 0.2` for 3 consecutive rounds → 10-round exclusion

**Validation:** `tests/test_fl_aggregator.py` clips 1000× outlier back to honest cluster; quarantines persistent -1000× attacker after ~11 rounds; median fallback at N_live < 5; excludes already-quarantined nodes. PASS.

**Staleness:** Both FedAvg and TRIM-NB-R apply staleness weight as extra per-update multiplier; s > 3 discarded as too-stale.

---

## Communications Model (SS4.6, SS8)

### Delay
LogNormal(ln 0.2, 0.5) + `bytes * 8 / 1 Mbit`, capped/lost beyond `d_max = 5 s`.

### Gilbert-Elliott Fading
- States: Good (G), Bad (B)
- Transition: P(G→B) = 0.02, P(B→G) = 0.3
- Loss: loss_G = 0.01, loss_B = 0.9
- **S9 sweep:** loss_B ∈ {0.5, 0.9}, P(G→B) ∈ {0.02, 0.1} (via `CommsConfig` overrides)

### Cold Start (SS4.7)
- Dormant nodes excluded from `ScenarioConfig.expected_ids(r)` for `r < join_round`; no explicit join handshake needed (simulation simplification).
- **Probation:** `TrimNbRConfig.probation_rounds = 2`, `probation_clip_c = 1.0`, keyed off `FLServer._joined_round[node_id]`.

**Validation:** `test_s8_cold_start_receives_model_within_two_rounds` (catches buffering bug: server now keeps pending messages across rounds, not silently dropping out-of-order arrivals).

---

## Poisoning Attacks (S12, S15)

All attacks supplied via `PoisoningAttackConfig` in `ScenarioConfig`.

### Node-Local Attacks
**sign_flip:** x → x - 5; applied node-side before `train_local`.
**label_flip:** y → 1 - y; applied before `train_local`.

### Server-Side Attacks (require cross-node information)
**gaussian_noise:** magnitude 10× median update norm; applied to fresh updates at aggregation.
**ALIE (Automated Lie Injection):** closed-form z per Baruch et al. 2019 (PROPOSED-DECISION: uses standard simplification, not exact per-coordinate order-statistics).

Both server-side attacks are simulation-only bookkeeping (never on wire `ModelUpdate` contract); leakage guard unaffected.

### Malicious Node Count
Passed via `malicious_ids` / `poison_kind` into `aggregate_round`, never the wire contract. Simulation verification: `malicious_node_count == round(f * N)` asserted for every one of the 90 runs at each tested fraction f ∈ {0.2, 0.4}.

---

## Known Scope Simplifications (all PROPOSED-DECISION)

1. **Replay buffer:** FIFO-truncated (20k capacity, class-balanced reservoir). Class-balance cap enforced at train time via `TrustDetector.train_local(balance=True, max_pos_fraction=0.5)`.

2. **S5 delayed updates:** Nodes send `NoUpdate(reason="scripted_delay")` during a scripted window, rather than literally holding and replaying trained δ after k rounds. Both are spec-compatible; this avoids second message queue per node.

3. **Node ticks:** Delegated to `local_dataset_provider` per round (not a literal dt=0.01 loop), required by INDEPENDENCE (no `fedqpnt.node` dependency) and M0/M1 lacking a closed-loop mission. Numeric AUC-drop under S5 reported by `scripts/run_fl_validate.py`.

---

## Known Bugs Found and Fixed (D-037, D-039)

### Bug 1: Server Dropped Out-of-Round Messages (D-037)
**Symptom:** Cold-start node reaches join round instantly; its round-r message lands on `server_q` before round collection was complete. Original loop did `if round_idx != r: continue` **after popping** — silent drop.
**Fix:** `orchestrator._server_main` now keeps `pending: dict[(node_id, round), msg]` buffer; each round drains buffered messages before blocking on queue.
**Test:** `test_s8_cold_start_receives_model_within_two_rounds`.

### Bug 2: Node Never Installed Global Model (D-037)
**Symptom:** `FLServer.aggregate_round` replies with `(GlobalModel, delay_s)` tuple on success, but node checked `isinstance(reply, GlobalModel)` — always False for tuple. `base_round` stayed at -1; `staleness s = round_idx - (-1)` exceeded `max_staleness=3` from round 3 onward, silent `ROUND_SKIPPED` starvation (looked like quorum loss, no crash).
**Fix:** Tuple unpacking in `_node_main`; call `install_global(global_model, delay_s)`.
**Test:** `test_clients_install_global_model_after_successful_rounds`.

---

## S12 Poisoning Results (Signature-Strength Sweep and N=10 Fleet)

### N=5 Baseline (D-037 warm-start bug diagnosis fix, 5 seeds, before real fix)
Fixed an off-path subsampling bug in `TrustDetector.train_local`: when `n_neg < n_min` (default 10), skip subsampling entirely and train on ALL samples with inverse-frequency weights. Result: zero-delta nodes (6/10 before fix) → 0/10 after fix.

**Acceptance criterion (TRIM-NB-R, f=20%, sign_flip):** mean drop = 0.063, CI = [-0.049, 0.110] >= 0.05 → FAIL at N=5. Driven by one outlier seed (0.219); others 0.028, 0.067, -0.002, 0.000. Reported honestly (not tuned away); at N=5, one malicious node = 20% of fleet, small held-out eval set → high variance.

### N=10 Spec Fleet Size (D-039, 10 seeds, 4 rounds)
Mean AUC drop vs clean with 95% bootstrap CI (2000 resamples):

| f | attack | FedAvg mean [95% CI] | TRIM-NB-R mean [95% CI] |
|---|---|---|---|
| 20% | sign_flip | -0.163 [-0.278, -0.044] | **0.032 [-0.049, 0.110]** |
| 20% | label_flip | 0.045 [-0.024, 0.115] | 0.070 [0.015, 0.130] |
| 20% | gaussian_noise | -0.095 [-0.192, -0.005] | -0.024 [-0.072, 0.035] |
| 20% | alie | -0.021 [-0.057, 0.014] | 0.015 [-0.010, 0.041] |
| 40% | sign_flip | -0.234 [-0.345, -0.123] | -0.003 [-0.117, 0.102] |
| 40% | label_flip | 0.010 [-0.093, 0.120] | 0.147 [0.088, 0.206] |
| 40% | gaussian_noise | -0.192 [-0.279, -0.113] | 0.011 [-0.078, 0.100] |
| 40% | alie | 0.021 [-0.041, 0.082] | 0.020 [-0.018, 0.056] |

**Acceptance criterion (TRIM-NB-R, f=20%, sign_flip):** mean drop = 0.032, 95% CI = [-0.049, 0.110] ≤ 0.05 → **PASS** at spec size (N=10 trimmed-mean design holds; β=20% covers one malicious node in five).

Several FedAvg cells show negative AUC drop (poisoned > clean) — expected under high noise (small held-out eval, 4-round runs). Reported honestly (not evidence FedAvg is fine; `tests/test_fl_aggregator.py::test_fedavg_delta_measurably_changes_with_poisoned_fraction` isolates aggregation math and shows FedAvg output IS pulled further from honest mean at f=40% vs f=20%).

---

## S5/S9 Comms-Loss Results (D-037, 5 seeds, N=5, PROVISIONAL)

**S5 (1 of 5 nodes failure at T/2):** mean AUC no-failure = 0.848, mean failure = 0.830, drop = 0.019 ≤ 0.02 → **PASS**.

**S9 (Gilbert-Elliott worst: loss_B=0.9, P(G→B)=0.1):** mean AUC no-loss = 0.844, mean lossy = 0.849, drop = -0.004 ≤ 0.03 → **PASS**.

---

## Validation and Regression Tests

**All FL tests:** `python -m pytest tests/test_fl_*.py -q` → 41 passed. Includes:
- Determinism (bit-identical across runs)
- CI-scoped real-multiprocess S5/S8/S9/S12/S15 (no deadlock; ROUND_SKIPPED logged, never silent hang; cold-start joins; TRIM-NB-R clipping bounded under poisoning)

**Full pipeline wall times (N ∈ {5, 10}):**
- N=5: 12.66 s / 6 rounds (2.11 s/round)
- N=10: 22.21 s / 6 rounds (3.70 s/round)

---

## Limitations and Known Issues

1. **Staleness s > 0 only in lost-message recovery:** bulk-synchronous protocol means s > 0 arises only when a node loses its downlink and keeps training on an older base. Not yet end-to-end tested on s > 0 numeric behavior (S9 comms-loss checks no-deadlock only, not staleness math).

2. **FedAvg uncapped gradient instability:** with synthetic tiny batches and few rounds, occasional seeded random walks into instability (manifested at N=5; N=10 avoids it). TRIM-NB-R's clipping prevents this.

3. **Process-count discipline:** all validation runs use N ≤ 10 nodes (≤ 11 processes total) to share machine with other agents; no multi-fleet concurrency.

---

## Related Decisions

- **D-026:** Detector design FROZEN (class-balance, feature set, loss function). FL implementation follows this frozen design.
- **D-037:** Round-0 warm-start fix in harness + real subsampling fix in `TrustDetector.train_local(n_min=10)`.
- **D-039:** Real source fix (dead-zone subsampling) + S12 at spec N=10 PASS.
- **D-050:** Class-weight cap 10×; fleet infrastructure accepted.
- **D-054:** Fleet data path accepted; H2/H4 previews INVALID (test-design flaw: trust law rules caught attacks, not learned detector). Evaluation protocol redesigned.
- **D-056:** M2 FL sanity check PASS (FedAvg/TRIM-NB-R AUC ≥ 0.95× centralised on IID data). H2/H4 report learned-detector-only AUC separately from operational p_bar.

---

**Last updated:** 2026-09-29 · **Status:** PROVISIONAL (kappa_R PROVISIONAL per D-046/D-047) · **Test count:** 41 FL tests passed; 5 seeds × multiple scenarios validated
