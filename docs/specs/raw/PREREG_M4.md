# M4 pre-registration (test-seed campaign)

_Master, 2026-10-03. Written BEFORE core-freeze-4 is tagged and BEFORE any test seed in [10000, 20000) has been run. Every item below is fixed. Any deviation must be recorded as a dated amendment with its reason, before the affected data is looked at._

## 1. Code and model
- **Code:** git tag `core-freeze-4`. A run is valid only if `git diff <launch> <end> -- fedqpnt` is empty and the `fedqpnt/` status is clean (D-062, D-077).
- **Detector:** `results/m1/detector_weights_sup_v3.npz` (D-072), passed explicitly. The `generate_tasks` default path is NOT used.
- **κ_R:** 60. **κ_Q:** 1 (D-079). Both come from `fedqpnt/core/defaults.py`.
- **Probe bounds (D-069/D-071):** MEMS 25.07, tactical 6.74 (position); χ²₂(0.99) = 9.21 (clock).

## 2. Seeds and grid
- **Test seeds:** 10000–10029 (n = 30).
- **IMU grades:** `industrial_mems` and `tactical` (D-063). Result ids are `<sid>@<grade>`.
- **Scenarios:** all 39 registry entries in `fedqpnt/eval/scenarios.py` at `core-freeze-4`, each with its registered method list. That is 5,340 single-node tasks, plus the fleet scenarios through the fleet adapter.
- **H2/H4:** come from the separate pre-registered fleet experiment (`docs/specs/raw/H2_PREREG.md`, Amendments 1–2), run on `core-freeze-4`.

## 3. Constants frozen from tuning data
- **σ_nom** (D-068, `results/sigma_nom.json`): MEMS 1.180 m; tactical 1.122 m.
- **S7 chattering bound** (D-075): at most 223 trust cycles per hour (integer comparison). The 133/h figure is reported as an annotation only.
- **Censoring:** event-level metrics are censored at 60 s; other latencies at t_off − t_on. Censoring is never data-dependent.

## 4. Confirmatory family
Exactly 8 tests, Holm-corrected with fixed m = 8 (D-068). An unevaluable test counts as not rejected.

| Hypothesis | Metrics | Setting | Comparison |
|---|---|---|---|
| H1 | RMSE_h(attack), latency_on | S2-med | FedQPNT vs Baseline A |
| H2 | P_D@10 s, onset latency | Fleet abrupt experiment | FL arm vs B-cont (D-064) |
| H3 | latency_eff | S6, one test per IMU grade | FedQPNT vs abl_minus_quantum (D-070) |
| H4 | P_D@10 s, latency | Cold-start node (D-064) | — |

- **Test:** paired Wilcoxon on per-seed values; α = 0.05 family-wise.
- **Effect sizes:** Hodges–Lehmann with 95% BCa CI.

## 5. Safety principle
Per scenario × grade:
- **Primary:** mean_defended ≤ mean_undefended + 3σ_nom.
- **Secondary:** paired HL difference (defended − undefended) with 95% CI.

Results are reported whatever they show.

## 6. Exploratory (not in the family)
- S6-coast (CAI coasting benefit).
- S2-DM (displaced meaconer).
- Per-family detection AUC.
- Timing RMSE.
- All other scenario criteria.

## 7. Known, stated envelope (from tuning data; not changed for M4)
- On MEMS, long exclusions coast about as far as slow-drift spoof drag, so the defence does not pay there. On tactical it does (D-079).
- Co-located meaconing costs position by design (cn0/xsat evidence routes to both laws), while timing is protected.
- Consistency-matched spoofs on MEMS can pass the shadow probe. The damage is bounded by the coast covariance.
- The detector fails for signature strength s < 0.5.
- The detector was trained on MEMS-grade data only.

## 8. Integrity
- The trust design was iterated on tuning seeds only (D-051…D-079).
- The test seeds are run once.
- No design, parameter or threshold changes after the gate opens.

---
## AMENDMENT R2 — Round 2 (2026-10-08), written BEFORE any round-2 data exists
Reason: round 1 (core-freeze-4, seeds 10000–10029) exposed a CAI-trust calibration bug (D-082). The user chose to fix the bug and run a fresh test round. Round 1 is reported as partial and superseded (`results/m4/ROUND1_STATUS.json`).

**Changes from the original pre-registration (everything else stands, including §4 confirmatory family, §5 safety rule, §8 integrity):**
- **Code:** tag `core-freeze-5` (D-082/D-083). Validity is judged by `git diff <launch> <end> -- fedqpnt` being empty and `fedqpnt/` equalling core-freeze-5 ("fedqpnt_verdict"). The frozen whole-repo HEAD verdict is also reported.
- **Test seeds:** **10030–10059** (n = 30). These are new and never used.
- **Single-node detector:** `results/m1/detector_weights_sup_v4.npz`, retrained with the unchanged D-052/D-053 protocol on the `schuler_tangent` world. Held-out AUC 0.958; displaced meaconer 0.9885; S1 FAR 0/h at both grades.
- **Fleet θ0:** `results/fleet/theta0_d054.npz`, re-pretrained on core-freeze-5 with the D-054 protocol on the fleet world (`flat`). Provenance is in `theta0_d054_freeze5_provenance.json`; the old file is backed up.
- **World:** single-node scenarios use `schuler_tangent`. Fleet scenarios use `flat` (the fleet runner default), which is disclosed.
- **σ_nom** (D-068 rule, re-measured on schuler_tangent): MEMS **1.139 m**, tactical **1.120 m** (`results/sigma_nom_freeze5.json`).
- **H2/H4:** the confirmatory fleet result stands from core-freeze-4 (D-081, null). Its primary (onset detection) does not involve CAI trust. Its inclusion in the Holm family is unchanged (it enters with its freeze-4 p-values), which is disclosed.
- **Execution:**
  - `scripts/m4_campaign.py --seeds 10030-10059 --weights <v4> --root results/m4r2`;
  - long specs use the spec-file launcher with a 7200 s timeout, and tasks are claimed via claim files;
  - test seeds are run ONCE;
  - a task that times out or crashes may be retried once, with the same spec, only if the cause is infrastructure (a machine stop or OOM). The retry is logged;
  - nothing else is re-run, and nothing is changed after launch.
