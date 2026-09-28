# Fleet Runner and Evaluation Protocol

This document covers the federated fleet runner (`fedqpnt/fleet/`), the θ0 pretraining protocol, the FL sanity check for H2/H4 evaluation, and fleet-level validation results. For the FL transport and aggregators, see [FEDERATION.md](FEDERATION.md). For node-level training, see [TRAINING.md](TRAINING.md).

---

## Purpose and Scope

**Owns:** `fedqpnt/fleet/` infrastructure; fleet integration with `fedqpnt/fl/` (transport, server, aggregators) and `fedqpnt/node` (local training and deployment). N-node federated runs with Environment + Agent at each node.

**Design:** Real-time Environment-driven federated loops over actual detector training rounds, not simplified per-round harness (contrast with `tests/_fl_harness.py` test stand-in).

---

## Fleet Runner Architecture

### Data Path
Each node's local dataset is built offline in the parent process via the shared real-feature builder, and nodes receive plain arrays. No surrogates; no feature leakage. Test: `tests/test_fl_leakage_guard.py` includes transitive import-graph tests (PASS).

**Leakage guard:** `fedqpnt/fleet/__init__` is import-free, preventing label-join leakage into spawned node processes.

### Live Detector Update
The detector object is updated from the next tick once each round completes. All nodes train on a fresh detector instance downloaded from the aggregator.

---

## θ0 Pretraining Protocol (D-054)

### Design
**FL experiments must start from θ0 pretrained on a disjoint seed range (400–449)** with a **RESTRICTED family set** that excludes the H2/H4 "novel" family. Example:
- θ0 trained on: jamming + abrupt only
- H2 evaluation: jamming + abrupt are "known"; drift and meaconing are "novel"
- Evaluation nodes see novel attacks absent from θ0 and their own local data but present in peers' data

**B-cont baseline:** starts from the same θ0, ensuring fair comparison.

### Rationale (D-054)
Earlier previews (H2/H4 at reduced scale) ran θ0 = M1 detector (trained on ALL families including the "novel" one), making the "detector never saw X" test meaningless. Early H2/H4 results showed FedQPNT = B-cont to 5 decimals (agreement to 5 decimals implies no effective training or same model evaluated). Fleet meaconing AUC was 0.708 vs 0.999 centrally; nominal FAR ≈ 12/h vs 0/h single-node — both signs of degradation, not learning.

---

## FL Sanity Check (D-054, D-056 PASS)

**Standard prerequisite:** Before any H2/H4 run, verify that federated learning on IID data with all families reaches ≥ 0.95× the centralised supervised detector AUC.

### Protocol
- N=5 or N=10 IID nodes, all see all attack families (clean + drift + meaconing + jamming)
- FedAvg and TRIM-NB-R aggregators
- Tune only FL hyper-parameters on tuning seeds (500–599, identically for all FL methods)
- Chosen parameters: `local_epochs=2`, `lr=0.05`, `μ=0` (FedProx), `R=10` (rounds)
- Centralised baseline: supervised M1 detector trained on union of node data

### D-056 Results (N=5, reduced scale 30 seeds × 60 s)
- **FedAvg AUC:** 0.996 [target ≥ 0.95 × centralised 0.997]
- **TRIM-NB-R AUC:** 0.998
- **FAR proxy:** 0/h
- **Grid coverage:** 8/8 cells PASS

**Acceptance:** PASS. Chosen hyper-parameters hold across all 8 grid cells; IID federation works.

---

## H2/H4 Evaluation Protocol Redesign (D-056 Master Diagnosis)

### Problem (D-056)
Preview results showed FedQPNT ≈ B-cont at meaconing AUC = 0.959 ± 0.002. Master found the root cause: **the scored quantity was p_bar (trust law's fused detector + rules)**, which includes the rule-based physical evidence E_s (D-051). E_s has a meaconing rule: "C/N0 bump ≥ 3 dB." A detector that never trained on meaconing still scores 0.96 because the **fixed rules catch it**. The preview measured the Master's safety rules, not FL knowledge transfer — a test-design flaw.

### Solution (D-056 Amended ARCHITECTURE §6.2)

Report three separate quantities:

1. **Learned-detector-only AUC** (calibrated p, E_s excluded)
2. **Operational p_bar AUC** (fused p + rules)
3. **Detection latency** (onset time to decision)

### Evaluation Regime: Sub-Rule Scenario
**The novel family is evaluated in a sub-rule regime where E_s does NOT fire:**
- Drift: signature strength s ∈ {0.5, 0.75} (below s < 0.5 failure boundary per D-055)
- Meaconing: C/N0 bump < 3 dB (below the E_s rule's ≥ 3 dB threshold); clock-jump < 5σ
- ≥ 5 seeds with CIs

### Claim Framing
**FL's contribution is learned detection of attacks *below* fixed physical-evidence thresholds, plus faster detection.** The rules provide a safety floor. No FL method should harm the safety floor's effectiveness.

---

## Fleet Validation Results

### D-050 Fleet Infrastructure Acceptance
**All tests PASS:**
- Real N-node pipelines (Environment + Agent) federated through unchanged FL server
- Live detector object updated from next tick
- S5/S8/S9/S12/S15 configurable
- Result files match campaign schema
- Leakage-guard AST test extended (PASS)
- Deterministic

**Wall time:** 52–55 s per fleet-hour at N=5.

### FedAvg Anomaly (D-048 Diagnosis)
Earlier results showed FedAvg with negative AUC drops at f=20% and f=40% (poisoned > clean, impossible). Root cause: **FedAvg uncapped gradient instability** with small per-round batches. Per-node logging showed one honest node produced delta_norm=6.88 vs 0.1–0.3 for others at round 3, destabilizing the aggregate. This is FedAvg's designed vulnerability (ARCHITECTURE §4.1: "weight by self-reported n_samples"). TRIM-NB-R's clipping (c=2×median) prevents this. No fix applied (per Master instruction: "no fix warranted since no bug found"). Reported honestly, not evidence FedAvg is fine.

---

## Limitations and Known Issues

### Missing Metrics (D-048)
S5, S8, S9, S12, S15 are marked `NOT_RUNNABLE` in the spec until:
1. Fleet runner proves stable (DONE, D-050)
2. FL sanity check confirms IID learning (DONE, D-056)
3. H2/H4 protocol redesigned to isolate learned contribution (DONE, D-056)

### θ0 Protocol Incompleteness (D-054)
Earlier previews omitted the θ0 protocol in their run description, leading to ambiguity about whether the "never saw meaconing" test was fair. θ0 documentation and provenance logging (parameter hash per arm, per round) now required before any H2/H4 claim.

### FedAvg Noise at Small N
At N=5 (forced by process-count discipline), FedAvg with 4-round runs and small held-out eval sets shows high variance; several poisoning cells show negative AUC drop. Reported as dataset artifact (small sample size, high variance), not evidence of FedAvg's robustness. Canonical poisoning math (unit test `test_fedavg_delta_measurably_changes_with_poisoned_fraction`) confirms FedAvg IS pulled further from honest at higher f.

---

## Related Decisions

- **D-050:** Fleet runner infrastructure ACCEPTED; class-weight cap 10×; surrogate-feature PD REJECTED (use real features).
- **D-054:** θ0 protocol REQUIRED for novel-family evaluation; fleet leakage guard PASS; H2/H4 previews INVALID (test-design flaw); evaluation protocol redesigned.
- **D-056:** M2 FL sanity check PASS (N=5 IID, FedAvg/TRIM-NB-R ≥ 0.95× centralised). H2/H4 report learned-detector-only AUC separately from operational p_bar. Novel family in sub-rule regime. θ0 pretrained on restricted families (e.g., jamming + abrupt; drift/meaconing novel).

---

**Last updated:** 2026-09-29 · **Status:** PROVISIONAL · **Sanity check result:** PASS (N=5 IID, FedAvg 0.996, TRIM-NB-R 0.998 vs centralised 0.997) · **Validation:** 8/8 grid cells PASS; leakage guard PASS
