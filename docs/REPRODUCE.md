# Reproducibility Guide

This document specifies seeds policy, determinism guarantees, and how to regenerate each artefact in `results/`. **All results in this repository are reproducible from git tag `core-freeze-1` (commit a7c8bf0).**

## Seeds Policy

Simulations use deterministic seeding via `fedqpnt.core.seeding.stream` (SHA-256 RNG per seed). Seed namespaces are enforced at all layers by `fedqpnt.core.seed_gate.enforce_seed()` (D-067):

| Category | Seed Range | Status | Use Case |
|----------|---|---|---|
| **Tuning** | [0, 10000) | ✅ All runs complete | Detector training, threshold tuning, preliminary M1 results |
| **Pretraining** | 400–449 | ✅ All runs complete | Supervised detector pre-training (within tuning namespace) |
| **Test** | [10000, 20000) | ⛔ **GATED** | Full evaluation; requires `results/GATE_D047.json` cleared AND `final=True` flag |
| **Fleet-derived** | ≥ 100000 | ✅ Allowed (derived) | Fleet local-training seeds (100_000 + parent_seed*100 + ...); allowed because parent is gated |
| **Unregistered** | [20000, 100000) | ⛔ Refused | Reserved for future use; not a registered namespace |

### Test Seed Gate

Test-seed runs ([10000, 20000)) are blocked unless **both** conditions hold:
1. CLI flag `--final=True` (or `--final --gate-cleared`) passed to `run_campaign.py` or `run_fleet`
2. `results/GATE_D047.json` contains `{"cleared": true}`

**Current status:** `results/GATE_D047.json` = `{"cleared": false}` (gate not cleared; blocked by issue #1 — defended RMSE ≥ undefended on tuning seeds after core fixes in D-061). Test seeds cannot be used until this gate is explicitly cleared by the Master.

## Determinism

**Guarantee:** Bit-identical reruns on the same Python version (3.11+) and architecture (D-062).

- **RNG seed:** `fedqpnt.core.seeding.stream(seed_int)` produces deterministic NumPy RandomState
- **Floating-point:** No special handling; varies ≤1 ULP across runs on same machine
- **Serialization:** All saved states are JSON or NumPy .npz format; lossless reload
- **Git provenance:** Every campaign/fleet run records `git rev-parse HEAD` and `git status --porcelain` at launch and completion; a run is valid only if the fedqpnt/ tree is clean and unchanged throughout. Runs on a dirty tree are flagged INVALID.

**Test:** Run any script twice with the same seed on a clean tree; output checksums must match.

```bash
# Example: reproduce S1 FAR check
python scripts/run_m1_s1_far_check.py --seed 500
# ... run again ...
python scripts/run_m1_s1_far_check.py --seed 500
# Results should be identical
```

## Results Mapping

This table maps each results artefact to the script(s) that produce it (core-freeze-1 era).

### M1 Single-Node Results

| File | Script(s) | Scenario / Seeds | Output Location |
|------|-----------|---|---|
| `kappa_r_tuning.json` | `scripts/tune_kappa_r.py` | κ_R sweep on seed 500 | `results/m1/kappa_r_tuning.json` |
| `s1_far_check.json` | `scripts/run_m1_s1_far_check.py` | S1 FAR (false-alarm rate), seeds 500–509 | `results/m1/s1_far_check.json` |
| `s1_far_check_v2.json` | `scripts/run_m1_s1_far_check.py` (v2 trust law) | S1 FAR with trust law v2, seeds 500–509 | `results/m1/s1_far_check_v2.json` |
| `smoke_matrix.json` | `scripts/run_m1_smoke.py` | Attack smoke tests (drift, meaconing, jamming); seeds 500–549; IMU-grade dimension | `results/m1/smoke_matrix.json` |
| `smoke_matrix_v2.json` | `scripts/run_m1_smoke.py` (v2 trust law) | Smoke matrix with trust law v2 | `results/m1/smoke_matrix_v2.json` |
| `detector_train_sup_v1_report.json` | `scripts/train_supervised_v1.py` | Supervised detector training (v1), seeds 400–449 | `results/m1/detector_train_sup_v1_report.json` |
| `detector_train_sup_v2_report.json` | `scripts/train_supervised_v2.py` | Supervised detector training (v2), seeds 400–449 | `results/m1/detector_train_sup_v2_report.json` |
| `detector_train_sup_v3_report.json` | `scripts/train_supervised_v3.py` | Supervised detector training (v3, core-freeze-1), seeds 400–449, κ_R=60 | `results/m1/detector_train_sup_v3_report.json` |
| `detector_weights_sup_v1.npz` | `scripts/train_supervised_v1.py` | Trained detector weights (v1) | `results/m1/detector_weights_sup_v1.npz` |
| `detector_weights_sup_v2.npz` | `scripts/train_supervised_v2.py` | Trained detector weights (v2) | `results/m1/detector_weights_sup_v2.npz` |
| `detector_weights_sup_v3.npz` | `scripts/train_supervised_v3.py` | Trained detector weights (v3, core-freeze-1) | `results/m1/detector_weights_sup_v3.npz` |
| `defended_vs_undefended_v1.json` | `scripts/defended_vs_undefended_check.py` | Defended ≤ undefended check, v1, seeds 500–549 | `results/m1/defended_vs_undefended_v1.json` |
| `signature_summary.txt` | `scripts/gen_gnss_attack_results.py` | GNSS attack signature strength validation (includes meaconing_displaced) | `results/attacks/signature_summary.txt` |

### Core-Robustness Session Diagnostics

| File | Script(s) | Purpose | Output Location |
|------|-----------|---------|---|
| (logs) | `scripts/core_robust_attack_trace.py` | Per-epoch trace for meaconing/drift_spoof attacks | `results/core_robust/` |
| (logs) | `scripts/core_robust_ba_nees_artifact_check.py` | Diagnose b_a NEES metric artifact under CAI | `results/core_robust/` |
| (logs) | `scripts/core_robust_clock_meaconing_trace.py` | Trace ClockKF under meaconing; separate clock/position trusts | `results/core_robust/` |
| (logs) | `scripts/core_robust_coasting_envelope.py` | Measure pure GNSS-coasting error envelope (180 s outage) | `results/core_robust/` |
| (logs) | `scripts/core_robust_drift_probe_trace.py` | Generalized per-epoch trace for drift/meaconing with probing | `results/core_robust/` |
| (logs) | `scripts/core_robust_es_firing_fraction.py` | E_s firing fraction on drift and meaconing attacks | `results/core_robust/` |
| (logs) | `scripts/core_robust_jam_recovery_summary.py` | Post-jam recovery summary with shadow probe / reacquisition | `results/core_robust/` |
| (logs) | `scripts/core_robust_jam_recovery_trace.py` | Trace jam_cw non-recovery per epoch | `results/core_robust/` |
| (logs) | `scripts/core_robust_kappa60_block_nees.py` | Per-block NEES at κ_R=60 (post D-043/D-057/D-058) | `results/core_robust/` |
| (logs) | `scripts/core_robust_overconfidence_diag.py` | Diagnose ψ/b overconfidence at κ_R=40 | `results/core_robust/` |
| (logs) | `scripts/core_robust_safety_principle_sweep.py` | D-055 safety principle across signature-strength sweep | `results/core_robust/` |
| (logs) | `scripts/core_robust_shadow_nis_check.py` | Empirical check of gnss_shadow NIS as probe acceptance statistic | `results/core_robust/` |
| `sigma_nom.json` | `scripts/core_robust_sigma_nom.py` | D-068 pre-registration: σ_nom per IMU grade (when exists) | `results/sigma_nom.json` |

### H2-ABRUPT Evaluation Scripts

| File | Script(s) | Purpose | Output Location |
|------|-----------|---------|---|
| `theta0_noabrupt.npz` | `scripts/h2_abrupt_pretrain_theta0_v2.py` | Pretrain θ₀ excluding abrupt family (novel); core-freeze-1 | `results/fleet/` |
| (logs) | `scripts/h2_abrupt_h2h4_driver.py` | H2/H4/drift-control fleet runs with abrupt as novel family | `results/h2_abrupt/` |
| (logs) | `scripts/h2_abrupt_metrics.py` | H2-ABRUPT pre-registered metrics (D-064) | — (module) |
| (logs) | `scripts/h2_abrupt_diag_score_trace.py` | Diagnostic: explain live AUC inversion vs held-out check | `results/h2_abrupt/` |
| (logs) | `scripts/h2_abrupt_diag_weight_provenance.py` | Diagnostic: compare n0 weights between arms | `results/h2_abrupt/` |
| (logs) | `scripts/h2_abrupt_es_firing_check.py` | Verify E_s stays quiet on abrupt under current core | `results/h2_abrupt/` |
| (logs) | `scripts/h2_abrupt_theta0_auc_by_severity_v2.py` | θ₀_noabrupt held-out AUC on abrupt at explicit severities (0.1, 0.15, 0.2) | `results/h2_abrupt/` |

### Federation and Fleet Results

| File | Script(s) | Scenario / Seeds | Output Location |
|------|-----------|---|---|
| `fl_sanity_check_d054.json` | `scripts/fl_sanity_check_d054.py` | FL sanity: federated ≈ centralised, seeds 500–509 | `results/fleet/fl_sanity_check_d054.json` |
| `h2_h4_full_d054.json` | `scripts/h2_h4_full_d054.py` | H2/H4 federation on tuning seeds (D-054) | `results/fleet/h2_h4_full_d054.json` |
| `h2_h4_subrule_d056.json` | `scripts/h2_h4_subrule_d056.py` | H2/H4 sub-rule regime search (D-056) | `results/fleet/h2_h4_subrule_d056.json` |
| `theta0_d054.npz` | `scripts/pretrain_theta0_d054.py` | Pretrained detector θ₀ (D-054), seeds 400–449 | `results/fleet/theta0_d054.npz` |
| `fl_s5_s9_auc.json` | `scripts/run_fl_s5_s9_auc.py` | FL AUC on S5/S9, seeds 500–549 | `results/fl/fl_s5_s9_auc.json` |
| `fl_s12_full_sweep.json` | `scripts/run_fl_s12_full.py` | FL S12 (poison defence), N ∈ [2,4,6,8,10], seeds 500–549 | `results/fl/fl_s12_full_sweep.json` |
| `fl_s12_n10_sweep.json` | `scripts/run_fl_s12_n10.py` | FL S12 poisoning at N=10 (CI), seeds 500–549 | `results/fl/fl_s12_n10_sweep.json` |
| `fl_validation_report.json` | `scripts/run_fl_validate.py` | FL infrastructure validation (42 tests) | `results/fl/fl_validation_report.json` |

### Campaign and Dry-run

| File | Script(s) | Scenario / Seeds | Output Location |
|------|-----------|---|---|
| (variable) | `scripts/run_campaign.py` (dry-run) | Plumbing check; scenario registry, mission flow; test-seed gate enforced | `runs/dryrun/` |

## Running the Campaign (Dry-run)

To verify plumbing without long runs:

```bash
# Dry-run: 2 scenarios, 3 seeds, 120 s per mission, 2 workers
python scripts/run_campaign.py \
  --scenarios S1 S2-low \
  --methods fedqpnt_local baseline_a undefended \
  --seeds 500 501 502 \
  --duration 120 \
  --workers 2 \
  --run-root runs/dryrun
```

Expected output: JSON with task counts and statuses.

**Note:** Full campaign (M4, 15 scenarios, 30–120 min per mission, 100 seeds) requires clearing GATE_D047 and is **not run** in preliminary results (tuning seeds only).

## Validation

All test files are reproducible via pytest:

```bash
# Validate data reproduction
python -m pytest tests/test_data_jarlaud.py -v

# Validate simulation and attacks
python -m pytest tests/test_sim_*.py tests/test_gnss_*.py tests/test_attacks_*.py -v

# Validate fusion and trust
python -m pytest tests/test_fusion_*.py tests/test_trust_*.py -v

# Full suite (40 modules, ~300 tests)
python -m pytest tests/ -v
```

---

**Last updated:** 2026-09-29
