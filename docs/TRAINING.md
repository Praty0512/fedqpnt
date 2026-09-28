# Detector Training and Validation: From Labels to Deployment

This document covers supervised detector training (the primary path per D-052), trust-law v2 implementation (D-051), label-free pseudo-labelling (ablation), Platt calibration, class-weight capping, and the rebalanced 6-family training mix with signature-strength validation. For node-level trust engine deployment, see [FEDERATION.md](FEDERATION.md) and [FLEET.md](FLEET.md).

---

## Purpose and Scope

**Training Pipeline Owns:** `fedqpnt/training/build_supervised_dataset.py`, `scripts/train_supervised_v1.py`, `scripts/train_supervised_v2.py`, `scripts/retrain_detector_real.py`, `scripts/sweep_signature_strength.py`, `scripts/gate_a_labeller_v2.py`, `tests/test_training_leakage_guard.py`.

**Trust Engine Owns:** `fedqpnt/trust/pseudolabel.py`, `fedqpnt/trust/detector.py`, `fedqpnt/trust/trust_law.py`.

**Design Freeze (D-026):** Detector architecture (MLP), loss function (cross-entropy + class weights), and feature set are FROZEN. All training changes are data/calibration-only.

---

## Training Data Path and Label Sourcing (D-052)

### Supervised Primary Path
**Decision (D-052 amends ARCHITECTURE §4.3):** Detector for ALL learning methods (FedQPNT, baseline A, B-cont) is trained on **ground-truth-labelled TRAINING missions** (tuning seed range 500–599 plus pretrain seeds 400–449).

**Rationale:** Matches literature baselines (Khan 2025, Chai 2025 both train supervised). At deployment/test time, **no labels reach any node**; test seeds (≥ 10000) never used for training or tuning (D-002, D-005).

**Label sourcing:** `fedqpnt/training/build_supervised_dataset.py` is the **ONLY place** `AttackLabel` joins with features. Statically enforced by `tests/test_training_leakage_guard.py` (3 tests, PASS).

**Leakage guard at runtime:** `fedqpnt/trust/pseudolabel.py` and `fedqpnt/trust/detector.py` never see `AttackLabel` during node operation; training labels consumed only offline or during FL-round training on training-seed missions.

### Label-Free Ablation (Pseudo-Labelling)
Original §4.3 hindsight pseudo-labelling (D-049 gate A, D-052 rejection) becomes an ablation path. Precision 0.214 (target ≥ 0.80), recall 0.587 — failed gate. Reported honestly with measured precision; **not part of H1–H4 main results.**

---

## Supervised Training Phases (D-049, D-051, D-052, D-053)

### Phase Sequencing

| Phase | Seed Range | Purpose | Status |
|---|---|---|---|
| Pretrain (θ0) | 400–449 | Detector pretrained on restricted families (e.g., jamming+abrupt; drift/meaconing excluded for H2 novel-family test, D-054) | D-056 PASS (FL sanity check on IID data from full mix) |
| Training | 500–549 | Supervised training on oracle-labelled missions | D-055 PASS (6-family ≥ 500 pos/family) |
| Platt-fit | 550–574 | Per-head Platt calibration at natural class ratio (oracle labels, training-phase data) | D-052 ACCEPTED |
| Heldout eval | 575–599 | AUC, Brier, per-family breakdowns (oracle labels, unseen data) | D-055 PASS (overall 0.953) |

### Real Closed-Loop Feature Capture (D-029, D-049)
**Data generation method:** `fixed_trust` mode (w_gnss ≡ 1, no trust law distrust, no detector in loop). This ensures consistent GNSS fusing during training-label collection, unlike operational mode where trust-law exclusion happens.

**Features:** Real ESKF innovations x1 (nis_pos, before correction) / x2 (nis_vel). No surrogates.

**Reference stats:** Recalibrated on clean 30-min runs (seeds 500–519) once per training cycle, capturing true feature distributions at κ_R = 40 PROVISIONAL.

---

## Design Details: Labeller, Class Balance, Calibration

### Labeller v2 Sigma Floors (D-051 Section A, D-052)
Implemented `fedqpnt/trust/pseudolabel.py::SIGMA_FLOOR_15`, applied to both positive and negative rules.

| Feature | Floor | Feature | Floor |
|---|---|---|---|
| x1 (nis_pos) | 0.5 (dof-normalised) | x7 (nsat_delta) | 0.1 |
| x2 (nis_vel) | 0.5 (dof-normalised) | x8 (cn0_rate) | 0.3 |
| x3 (raim) | 0.5 (dof-normalised) | x10 (resid_rms) | unfloored (unclear in source) |
| x4 (clk_jump) | 3.0 | x12 (div_cusum) | unfloored |
| x5 (cn0_std) | 0.1 | x13 (outage) | unfloored |
| x6 (cn0_mean) | 0.3 | | |

**Rationale:** Features near zero on clean data trigger false positives; floors stabilize the nominal reference without changing attack-detection thresholds (D-026 freeze).

### Class-Weight Cap (D-050)
**Parameter:** `max_weight = 10×` inverse-frequency weight per class.

**Problem:** Inverse-frequency weights become unbounded when `n_neg` is tiny (e.g., 1 negative = huge `w_pos`), causing exploding SGD steps.

**Solution:** Cap `w_pos` / `w_neg` at 10× in `TrustDetector.train_local(balance=True)`. Not a design change (still uses class weights for imbalance), just numerical stability.

**Unit test:** `test_class_weight_cap_bounds_update_norm_with_single_negative` (PASS).

### Platt Scaling (Runtime Calibration, D-051 Section B, D-052)
Per-head (spoof/jam) logistic calibration: `p_calibrated = σ(a*p_raw + b)` where (a, b) are fit on heldout data (seeds 550–574, natural class ratio).

**Wiring:** `TrustDetector.score()` returns calibrated `p_bar` if Platt params are installed; identity by default.

**Effectiveness:** Helps reliability curve but not always AUC (Brier improved v1→v2 in some cases, not others; see D-049 breakdown).

---

## Signature-Strength Sweep and Failure Boundary (D-053b, D-055)

### Signature Strength Parameter
`fedqpnt/attacks/spoofing.py::DriftInSpoof.cn0_sig_scale` (default 1.0).

Scales BOTH:
- Shared Gauss-Markov fluctuation sigma: `common_cn0_fluct_sigma_db * cn0_sig_scale`
- Post-capture convergence: `cn0_sig_scale * conv_frac_full`

At s=0, no cross-PRN C/N0 correlation induced; each PRN keeps individually-boosted level. At s=1, reproduces D-018 exactly (regression-tested: existing spoofing tests all PASS unchanged).

### Sweep Results (D-055, v2 Detector Trained at s=1)
Fresh held-out missions per signature strength:

| s | Drift AUC | Meaconing AUC (control) | Detector Behavior |
|---|---|---|---|
| 1.0 | 0.999 | 0.999 | Trained distribution |
| 0.75 | 0.999 | 0.999 | Strong signal persists |
| 0.5 | 0.995 | 0.999 | Borderline detectability |
| 0.25 | 0.524 | 0.999 | **Chance-level performance** |
| 0.0 | **0.129** | 0.999 | **Inverted (anti-correlated)** |

**Meaconing flat at 0.999** across all s — control confirming effect isolation (meaconing's C/N0 bump doesn't use cn0_sig_scale).

**Conclusion:** Drift detection carried almost entirely by D-018 single-antenna signature between s=0.25 and s=0.5. Below s~0.5, method **actively harms RMSE** (not neutral degradation).

### Safety Principle (D-055 adopted)
**"A defended method must never be substantially worse than undefended across the stated threat envelope."**

**Paper requirement:** State minimum signature strength (s ≳ 0.5) as explicit operating assumption; report s < 0.5 failure boundary; include harm analysis.

---

## Attack Family Rebalancing (D-053a, D-053b)

### Problem (D-053a root-cause diagnosis)
Old training used jam_cw at severity=0.5 with default jammer geometry (500 m FSPL ~90 dB). Even severity=0.15 drives effective C/N0 to ~-10 dB-Hz, far below 25 dB-Hz lock threshold. **Every satellite loses lock simultaneously for the whole [0,1] severity range.** Agent.step maps invalid fix to `fix=None`; zero (feature, label) pairs captured — only 8 jamming positive epochs across entire old pool.

**Fix:** Vary `jammer_eirp_dbw` per severity level via direct calibration:

| Severity | jammer_eirp_dbw | Fix-Valid Fraction |
|---|---|---|
| 0.15 | -55 | 181/181 (clean-ish) |
| 0.25 | -45 | 181/181 (mild) |
| 0.35 | -38 | 181/181 (partial) |
| 0.45 | -33 | 150/181 (partial, some drop) |
| 0.55 | -30 | 99/181 (transition) |
| 0.80 | +5 | ~0-2/181 (full denial) |
| 1.00 | +20 | ~0-2/181 (full denial, matches old regime) |

### 6-Family Training Mix (D-053a)
`FAMILY_NAMES = [drift, meaconing, abrupt, jam_cw, jam_wideband, jam_then_spoof]`.

Clean assigned at `seed % 10 == 0` (~10%); round-robin 6 families on rest (`seed % 6`). Same convention across disjoint TRAIN/PLATT/HELDOUT blocks.

`jam_then_spoof` built as two chained AttackSpec dicts (jam_wideband 60–120 s, drift 100–280 s, overlapping), not via unused `JamThenSpoof` class.

### Training-Pool Positive Epochs (D-055, seeds 500–549)
All families ≥ 500 target achieved on second attempt (first attempt: jam_wideband=397, increased attack duration 180→240 s):

| Family | Positive Epochs |
|---|---|
| drift | 1092 |
| meaconing | 1448 |
| abrupt | 1246 |
| jam_cw | 836 |
| jam_wideband | 577 |
| jam_then_spoof | 1368 (spoof) + 177 (jam) |

Oracle jam positives across TRAIN: 1590 (vs old pipeline's 8).

---

## Detector v2 Validation Results (D-055)

### Heldout AUC per Family (Calibrated, v2 vs v1)
v2 represents 6-family mix with rebalanced jam levels; v1 used old 4-family mix (jam_cw only, 8 pos epochs).

| Family | v1 AUC | v2 AUC | Change |
|---|---|---|---|
| drift | 0.999 | 0.998 | slight ↓ (noise) |
| meaconing | 0.999 | 0.999 | flat |
| abrupt | 0.754 | **0.691** | **↓ (regressed)** |
| jam_cw | 0.649 (single "jamming") | 0.996 | ↑↑ (new family split) |
| jam_wideband | — | 0.988 | new |
| jam_then_spoof | — | 0.997 | new |
| **Overall** | 0.923 | **0.953** | ↑ |

**Brier (calibrated):** v1 = 0.053, v2 = 0.068 (slightly worse; more heterogeneous jam data broadens calibration).

**Per-head breakdown:** spoof AUC=0.929, jam AUC=0.988 overall (v1 jam head not separately reportable).

**Honest negative finding:** Rebalancing jam improved jam family detection sharply but **abrupt AUC regressed from 0.754 to 0.691**, not recovered by more jam/jam_then_spoof training. Flagged for Master; no further iteration attempted (D-026 freeze + D-055 token economy).

---

## S1 v2 False-Alarm and Filter Performance (D-055)

**5 seeds × 30 min nominal (no attack):**

| Criterion | v2 Result | Threshold | Status |
|---|---|---|---|
| FAR (fedqpnt/B-cont) | 0.0/h | ≤ 1/h | **PASS** |
| RMSE_h ratio (fedqpnt/fixed-trust) | 0.9904 median | ≤ 1.05 | **PASS** |
| ANEES_pos | 1.306 | ∈ [0.5, 2] | **PASS** |

Residual: seed 504 shows FAR=1.6/h on baseline_a/fixed_trust/undefended (pre-existing, hits methods v2 doesn't change, not v2-specific regression).

---

## Core-Robustness and E_s Redesign (D-058, in progress)

### E_s Position Term Self-Contamination (H2-SUBRULE Finding, D-058)
**Problem:** E_s was designed to be independent physical evidence but is coupled to trust law's exclusion dynamics. E_s fires one epoch after w_gnss collapses (as detector's p drives distrust), when filter's own state has free-inertially diverged — large innovations result not from attack but from the law's own exclusion.

**At attack onset:**
- w_gnss collapses to ~0.06
- Filter free-inertial-coasts
- Next epoch's Δp innovation is huge (divergence, not attack signature)
- E_s position term fires (0.87–0.88 of total evidence)

**Decision (D-058):** Redefine E_s as **short-baseline jump test independent of filter state:** Δp_GNSS(t_k − t_{k−1}) − Δp_INS(t_k − t_{k−1}) (IMU-propagated over 1 s), χ²₃ at 99.9% using fix covariances + short-term INS covariance. Abrupt spoof trips it; slow drift and self-divergence do not.

### Core-Robustness Session (D-058 Planned, Post-H2-SUBRULE)
One work package, shared core (all methods):
- (a) Soft covariance-scaling gating (D-057)
- (b) E_s short-baseline jump test
- (c) `_hygiene` eigenvalue clip (D-043)
- (d) ψ/b overconfidence investigation (D-046/D-047)
- (e) Re-verify M1 criteria (S1, smoke matrix) and κ_R re-tune
- Then re-attempt H2 sub-rule verification

---

## Trust Law v2 Implementation (D-051 Section C)

### State Machine (T_ex = 60 s, T_probe = 10 s, w_probe = 0.3, T_sup = 120 s)
`_LawCoreV2` wraps existing `_LawCore` for p_bar/hysteresis/tau_star/G.

**States:**
- **TRUST:** normal operation (w_gnss high)
- **DISTRUST:** detector p > θ_on for T_ex seconds → reduce w_gnss
- **PROBE:** after T_ex, try w_probe = 0.3 for T_probe = 10 s
- **RECOVER:** if NIS consistent + no persistent E_s during probe → back to TRUST
- **SUPPRESS:** detector suppressed 120 s after recovery (avoid chatter)

### Evidence Sources
- **Detector p_bar:** EWMA of learned detector output + Platt calibration
- **E_s (physical spoof evidence):** Reuses detector's running normalizer as clean reference (sigma-floored same as labeller)

**Jamming evidence does not block recovery** (key difference from v1): A partially jammed-but-consistent GNSS fix can be probed; recovery happens if NIS passes even under persistent jamming.

### Validation
`tests/test_trust_law_dynamics.py` (25/25 PASS):
- Chronic false-positive detector: exclusion never > 70 s continuous; recovers to w > 0.9
- Persistent E_s evidence: stays ≤ w_probe, attack_detected ≤ True
- Partial jamming (elevated p, clean NIS, no E_s): recovers within 70 s
- S7 chattering: 52 cycles/hour bound holds (v1: 138, unaffected)

**Selected via `TrustLawConfig`/`TrustEngineConfig.trust_law_version` ("v1" default, "v2" for fedqpnt/B-cont; baselines A/B-bin/B' stay v1).**

---

## Limitations and Known Issues

### D-055 Safety Principle Boundary
Below s < 0.5, defender is **actively harmful** on drift (2.3 km mean RMSE vs 108 m undefended). Honest negative result; no workaround. Paper must state s ≳ 0.5 operating assumption.

### D-051 Anti-Lockout Failure (D-049 Diagnosis, Unfixed)
The anti-lockout timer only accumulates while `D==0` (detector already cleared). **There is no timer that forces D back to 0 purely as elapsed-time function.** If detector stays chronically elevated on clean data (misclassified, off-distribution), D can remain 1 indefinitely, anti-lockout's precondition never met. Solution is shared-core (gating + overconfidence fix), assigned to core-robustness session (D-058).

### Abrupt Spoof AUC Regression
v2 rebalancing improved jam detection sharply (0.649→0.996) but **regressed abrupt from 0.754→0.691**. More jam training did not help abrupt. Root cause unclear; no design-change iteration performed (D-026 freeze, D-055 token economy).

---

## Related Decisions

- **D-026:** Detector design FROZEN (MLP arch, loss, class-balance rule, feature set). All changes are data/calibration only.
- **D-029:** Retrain on real closed-loop features (captured live via monkeypatch, not edited).
- **D-049:** Recalibrate reference stats on real features; discovered v1 mis-calibration (nsat_delta sd 1.0→0.024); trade-off found (abrupt recovered but drift inverted).
- **D-051:** Trust law v2 (state machine, evidence-bounded exclusion 60 s); sigma floors; Platt calibration; class-weight cap.
- **D-052:** Supervised primary path (D-049 gate A failed, pseudo-labelling rejected). AttackLabel join ONLY in build_supervised_dataset.py.
- **D-053:** 6-family rebalance + jammer EIRP calibration (old: jam severity [0,1] gave zero epochs; new: all families ≥ 500 pos epochs).
- **D-055:** Signature-strength sweep (s < 0.5 failure boundary s < 0.25 inverted; s < 0.5 actively harmful); safety principle adopted; honest abrupt regression reported.
- **D-058:** E_s position term redefined as short-baseline jump (independence from filter-divergence artifacts); core-robustness session planned (post-H2-SUBRULE).

---

**Last updated:** 2026-09-29 · **Status:** D-055 PASS (S1 v2, detector 0.953 AUC); core-robustness pending (D-058) · **Test count:** 122 training + trust + eval tests PASS; 66 attack tests PASS
