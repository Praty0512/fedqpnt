# Trust/Detection design v2 (Master, D-051), amends ARCHITECTURE.md §3.1, §3.3, §4.3

Developed on TUNING seeds (500–599) only, **before any test-seed run**. To be declared in the paper as a design iteration (pre-registration integrity, D-002). It applies to FedQPNT and B-cont alike (B-cont = the same law without FL, so the H2 isolation is preserved). Baselines A, B-bin and B′ are unchanged.

## Why (M1-CLOSE evidence, EXECUTION_LOG #80, #83)
1. **Labeller:** the joint χ²₁₁ negative rule is dominated by near-degenerate features (nsat_delta σ = 0.024 on clean converged runs). Pseudo-label precision was 0.60 (v1) and 0.29 (v2). Family AUCs trade places (v1: jam/abrupt inverted; v2: drift inverted).
2. **Trust law:** the §3.3 anti-lockout timer only runs when D = 0. **There is no bound on time spent with D = 1**, so a chronically mis-firing detector pins w_gnss at the floor indefinitely, giving unbounded free-inertial drift (nominal runs diverged to 10⁵–10⁶ m).
3. **Jamming:** distrusting still-consistent, partially jammed GNSS is worse than using it (defended 13–27 km vs undefended 237 m).

## A. Labeller v2 (§4.3)
- Standardise each feature with σ_eff,k = max(σ_ref,k, σ_floor,k). σ_floor is the physical resolution or noise scale:
  - integer counts (nsat, nsat_delta): 0.5;
  - C/N0 features: 0.3 dB-Hz;
  - AGC: 0.5 dB;
  - NIS/RAIM-type χ² features: 0.5·dof;
  - clock bias/drift jumps: the receiver's reported 1σ;
  - correlation-type features (x14): 0.05;
  - slope (x15): 0.02 dB/deg.
- Negative rule: joint χ² on the floored, standardised (diagonal) vector, threshold χ²_k(0.95), with the 90% window clean fraction (D-022 PD2).
- Positive rules: the existing physical rules (clock jump, xsat/cn0 D-024, AGC, NIS spike, divergence CUSUM vs the CAI-aided INS), unchanged.
- **Acceptance before any retrain:** clean-run positive-label rate ≤ 1% on held-out clean tuning runs AND precision ≥ 0.8 vs oracle on tuning missions. If it's not met, stop and report; no iteration without the Master.

## B. Detector output (§3.2)
- Per-head Platt calibration fitted at the natural class ratio (tuning seeds) and **applied at runtime** to p before the trust law.
- Class-weight cap 10× in `train_local` (D-050).

## C. Trust law v2: evidence-bounded exclusion (§3.3)
States: TRUST (D=0), DISTRUST (D=1), PROBE.
1. Entering DISTRUST: as in §3.3 (hysteresis on the calibrated p̄).
2. **Exclusion bound:** after T_ex = 60 s continuously in DISTRUST, go to PROBE.
3. **PROBE** (T_probe = 10 s): w_gnss = w_probe = 0.3 regardless of p. Collect the GNSS innovation NIS under partial trust and the *physical spoof evidence* E_s = {clock/clock-drift jump beyond 5σ, xsat C/N0 correlation above the floored nominal band, meaconing C/N0 bump ≥ 3 dB, abrupt position innovation beyond the gate}.
4. Exit PROBE:
   - if the mean NIS over the probe is within the χ²_dof 95% bound AND E_s is empty → TRUST, via the normal recovery ramp; the learned detector is **suppressed** for T_sup = 120 s (p ignored unless E_s fires) to prevent re-lock by a mis-firing detector;
   - otherwise → DISTRUST for another T_ex.
5. **Jamming evidence** (AGC drop, C/N0 loss, lock loss) does **not** block recovery. Jamming degrades rather than deceives, and the honest receiver covariance already down-weights degraded fixes. Invalid fixes are simply absent.
6. The floor w_min, the reacquisition cap and the asymmetric rates are unchanged.
7. **Chattering bound:** a cycle is ≥ T_ex + T_probe = 70 s > the 26.1 s §3.3 bound, so the bound still holds. Re-verify S7.
- **Stated threat-model assumption (paper §III):** recovery against an NIS-blind (consistent) spoofer relies on at least one physical signature in E_s. A fully signature-free spoofer (e.g. multi-antenna, per-satellite-power-matched) is outside the threat model. Under it, v2 would re-trust the spoofer every T_ex + T_probe, and this is reported as a limitation.

## D. Acceptance (M1 sign-off, tuning seeds)
- S1: FAR ≤ 1/h/node for FedQPNT and B-cont; RMSE_h ratio ≤ 1.05 vs fixed trust; ANEES_pos ∈ [0.5, 2]; no nominal divergence.
- S7: chattering bound holds.
- Smoke: no defended method worse than undefended on nominal or CW jamming by more than 3σ_nom (from D-048, measured).
- Detector: all four family AUCs > 0.5, with CIs reported.
- Everything stays labelled κ_R PROVISIONAL (D-046/D-047).
