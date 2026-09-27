# GNSS Signal Model and Attack Scenarios

**Purpose.** This document specifies the simulated GNSS receiver signal model, spoofing and jamming attacks, and associated validation and cross-checks against literature.

## Orbit and constellation geometry

### GPS constellation

| Parameter | Value | Source | Status |
|-----------|-------|--------|--------|
| Semi-major axis | 26,560 km | Kaplan & Hegarty 2017, Ch. 2 | [LIT] |
| Inclination | 55 deg | Kaplan & Hegarty 2017, Ch. 2 | [LIT] |
| Orbital planes | 6 | Kaplan & Hegarty 2017, Ch. 2 | [LIT] |
| Orbit propagation | Unperturbed 2-body Kepler (no J2/SRP) | — | [ASSUMPTION] |
| Almanac | Synthetic Walker-like pattern | — | [ASSUMPTION] (A1 ratified) |
| Elevation mask | 10 deg | Standard receiver practice | [LIT] |
| Earth model | WGS-84 | — | [LIT] |

**Rationale for synthetic almanac:** Geometry is realistic (8–9 satellites visible at 10° elevation from the reference origin `ORIGIN_LLH`, consistent with GPS-only open-sky). Visible PRN set changes over a 6-hour span (orbital period ~11h58m). Slant ranges 18–27 Mm match nominal GPS geometry. No real dated YUMA/SEM almanac is tied to simulation date, so absolute ephemeris error and sky-plot time variation are qualitative, not quantitative — sufficient for DOP and geometry-driven attack signatures over multi-hour sim windows (which is the relevant domain). Not adequate for cm-level ephemeris accuracy or seasonal sky-plot variation studies.

**Validation:** 30 min static observation, synthetic Walker almanac, 10° elevation mask: DOP distribution mean 2.02, std 0.11, min 1.83, max 2.11, p95 2.11 — sane, bounded, not degenerate. (Result: `results/attacks/dop_distribution.txt`.)

---

## Clean signal model

The receiver measures, per satellite PRN, a pseudorange ρ (code phase) and Doppler shift (carrier phase rate), both corrupted by thermal noise and atmospheric delays. A 2-state receiver clock (bias and drift) is estimated jointly with position and velocity.

### Signal-to-noise observables and receiver thermal noise

| Quantity | Equation / Value | Source | Status |
|----------|------------------|--------|--------|
| L1 frequency | 1575.42 MHz | ICD-GPS-200 | [LIT] |
| C/A chip rate | 1.023 Mchip/s | ICD-GPS-200 | [LIT] |
| Receiver clock | 2-state random walk (bias, drift) | Vig 1992 / Kaplan & Hegarty 2017 Ch.5 | [LIT model], [ASSUMPTION] tuning |
| Code thermal noise σ_code(el, C/N0) | Kaplan & Hegarty 2017 Eq. 8.24 class | Narrow-correlation DLL, d=0.1 chip, BW=1 Hz, T=20 ms | [LIT formula], [ASSUMPTION] loop params |
| Doppler thermal noise σ_doppler(C/N0) | Standard PLL thermal jitter, scaled by wavelength/T | Kaplan & Hegarty 2017 Ch.8 | [LIT formula], [ASSUMPTION] loop BW=15 Hz |
| C/N0 vs elevation | 38 dB-Hz @10° → 48 dB-Hz @zenith (linear) | Kaplan & Hegarty 2017 Ch.5 | [ASSUMPTION] exact curve shape |

**Unified UERE budget functions** (`fedqpnt/gnss/signal.py`): All per-satellite error sources (thermal, ionospheric, tropospheric, multipath) now compute into a single `uere_variance_m2(elevation, cn0)` and individual component functions (`code_thermal_sigma_m`, `doppler_thermal_sigma_mps`, etc.). These are used by both the signal generator and the receiver's own weight matrix, ensuring the signal model and the receiver's noise budget are in sync. This is the single source of truth; no independent heuristic weighting is used.

### Atmospheric error models

| Component | Model | τ (time constant) | σ (spatial/1-σ magnitude) | Source | Status |
|-----------|-------|---|---|--------|--------|
| Ionospheric residual | Gauss-Markov, post Klobuchar correction | 600 s | 1.5 m / sin(el) | Klobuchar 1987 (magnitude order) | [LIT model], [ASSUMPTION] τ/σ tuning |
| Tropospheric delay | Saastamoinen zenith ≈ 2.3 m, 1/sin(el) mapping | (no time variation model) | 0.23 m @30° el | Saastamoinen 1972 (model), simplified 1/sin(el) not full Niell/GMF | [LIT model], [ASSUMPTION] mapping |
| Multipath | Elevation-dependent Gauss-Markov | 20 s | 0.3–2.3 m (el-dependent) | Kaplan & Hegarty 2017 Ch.7 (qualitative shape) | [LIT qualitative], [ASSUMPTION] exact coefficients |

**Initialization fix:** Each per-satellite Gauss-Markov channel (iono/tropo/multipath) is initialized from its own stationary distribution on first acquisition of a PRN, not from zero. Prior to this fix, a 30-minute warm-up bias was observed (mean-raim/mean(n-4) ≈ 0.60, outside ±30% band), which has been corrected.

**Example error budget at 30° elevation:**
- Thermal: 0.185 m @51 dB-Hz (clean C/N0 typical)
- Ionospheric: 3.00 m
- Tropospheric: 0.23 m
- Multipath: 0.75 m
- **Total UERE σ ≈ 3.15 m** (iono dominates; thermal is a small fraction)

### Receiver architecture (WLS + RAIM)

| Component | Formula / Method | Source | Status |
|-----------|---|--------|--------|
| Position/velocity solution | Weighted Least Squares (WLS), w_i = 1/σ_i² | Misra & Enge 2006, Ch.6 | [LIT] |
| PVT weight | w_i = 1/uere_variance_m2(el_i, cn0_i) | Unified UERE budget (Section above) | v2: weight now uses exact signal UERE, not independent heuristic |
| Velocity weight | w_i = 1/doppler_thermal_sigma_mps(cn0_i)² | Dedicated Doppler-consistent weight | v2: was position-weight reused; now separate |
| PDOP | sqrt(trace((H^T H)^-1)[0:3,0:3]) | Kaplan & Hegarty 2017 Ch.5 (geometry-only, unweighted) | [LIT] |
| RAIM statistic | Weighted sum-of-squares post-fit residual (χ²) | Parkinson & Axelrad 1988 (snapshot RAIM) | [LIT] |
| Lock threshold | C/N0 < 25 dB-Hz → lost lock | Kaplan & Hegarty 2017 Ch.5/6 (order of magnitude) | [ASSUMPTION] |
| Reacquisition delay | 1.0 s | Typical warm reacquisition 0.5–2 s | [ASSUMPTION] |
| Valid fix threshold | ≥4 locked satellites + nominal χ² | Standard GNSS requirement | [LIT] |

### RAIM calibration and blindness under attack

**Calibration (Section 4a of raw notes):** A single 30-minute run does NOT provide stable χ² estimates due to long-lived Gauss-Markov error processes (tropo τ = 1800 s, iono τ = 600 s). Per-run ratios range 0.67–1.51 across 10 independent seeds. Acceptance test pools 6 independent ≥30-minute runs instead, all meeting the nominal ±30% / 5e-3 false-alarm-rate bounds.

**RAIM under drift-in spoofing (paired-receiver test):** Drift-in spoofing's power advantage and slow code/Doppler drag are geometrically self-consistent (delta-on-clean construction). Unlike naive per-epoch RAIM, cross-satellite detectors can exploit the single-antenna C/N0 correlation signature (D-018). Measured: paired-clean RAIM mean 3.95 vs. attacked 4.04 (KS p=0.99, n=40 independent realisations). **RAIM is nominally blind to drift-in spoofing**, by design — this matches real-world behavior and motivates the need for trust-based multi-satellite detectors.

**RAIM under meaconing:** Common-mode delay, small C/N0 rise. Statistically indistinguishable from clean in snapshot RAIM.

**RAIM under abrupt (non-aligned) spoofing:** Lock-loss and reacquisition window shows elevated χ². Once past reacquisition, indistinguishable from clean (KS p=0.9999, n=40).

**RAIM under jamming:** Raw χ² stays low during jamming (fewer locked satellites means fewer DoF mechanically lower the statistic, even though per-satellite residuals are larger). **By definition**, χ² goes NaN when <4 satellites remain (no valid fix).

---

## Attack scenarios

Attacks modify `GnssEpoch` observables (pseudorange, pseudorange rate, C/N0, lock state, AGC/noise floor) per PRN. An attack never reads `epoch.meta` (truth clock bias, receiver state); this is enforced by contract v0.2. Spoofed observables are constructed as **deltas on clean observables** to maintain geometric self-consistency.

### Spoofing (drift-in carry-off)

**Construction:** Spoofed pseudorange = clean pseudorange + `fake_position - true_position` (geometric delta) + spoofer-atmosphere-mismatch Gauss-Markov term (σ ≈ 0.5 m, τ ≈ 300 s, [ASSUMPTION]).

**Signature evolution:**

| Phase | C/N0 behavior | AGC | Code/Doppler | Effect on receiver |
|-------|---|---|---|---|
| Power alignment (capture) | +3–10 dB bump during ramp (power advantage, D-018 item 1) | Unaffected | Smooth drag toward spoofer fake state | Correlator locks to spoofed signal within a few seconds (typical 5–30 s) |
| Post-capture drag | Decays from peak to maintenance level (15% of peak) over 5 s | — | Code and Doppler converge to spoofer-computed values | Receiver is now tracking fake trajectory |
| Steady-state | Converges to spoofer's transmitted C/N0 (45 dB-Hz [ASSUMPTION]) + shared Gauss-Markov fluctuation (σ=1 dB, τ=20s [ASSUMPTION]) | — | Statically consistent with fake position | RAIM sees no anomaly; continuous trust detector needed |

**Single-antenna C/N0 correlation (D-018 item 2):** All spoofed PRNs share a common-mode C/N0 fluctuation (single jammer antenna). Measured field data (Radoš et al. 2024 Fig. 5): cross-satellite correlation coefficient drops from −0.76 (clean) to 0.99 (spoofed). Our model: measured mean pairwise correlation ≈0 clean vs 0.9996 spoofed (post-capture). C/N0-vs-elevation regression slope collapses from ~0.13 dB/deg (clean) to ~0.0002 dB/deg (spoofed). This signature is modelled explicitly and is exploitable by multi-satellite detectors even when snapshot RAIM is blind.

**Literature grounding:** Humphreys et al. 2008 (power-advantage capture, drag-within-loop-bandwidth); Radoš et al. 2024 (5 dB advantage → 98% SQM detection, field-measured correlation collapse); TEXBAT (general carry-off scenario pattern).

### Meaconing (record-and-rebroadcast)

**Construction:** Replayed pseudorange = clean pseudorange + replay_delay_m (common-mode shift). C/N0 rises slightly (+0.3–4 dB config-dependent). Doppler unchanged. Receiver experiences a common-delay shift in all PRNs simultaneously.

**Receiver view:** Looks like a common-mode clock jump (in the transmitted signal, not the receiver's own clock estimate). Distinguishable from per-satellite drag spoofing by the common-mode nature and absence of per-PRN C/N0 rise.

**Literature:** Psiaki & Humphreys 2016 (meaconing = record-and-rebroadcast, common delay + C/N0 rise).

### Abrupt (non-aligned) spoofing

**Mechanism:** Spoofer suddenly injects fake signal without alignment to the receiver's current tracking loops. Receiver experiences 15 dB C/N0 drop → forced lock-loss → 1 s reacquisition delay → sudden position/velocity jump on re-lock.

**Signature:** Momentary invalid fix (GNSS outage feature), then recovery to a fake trajectory.

**Literature:** Psiaki & Humphreys 2016 (unaligned spoofing cannot smoothly capture; requires loss-and-recapture).

### Jamming: CW (narrowband)

**Mechanism:** Continuous-wave interference at the L1 frequency. Effective C/N0 reduced by the J/S (jammer-to-signal) power ratio via the standard formula:
```
(C/N0)_eff^-1 = (C/N0)_nom^-1 + (J/S) / (Q * R_c)
```
where Q ≈ 2/3 (spreading gain for narrowband vs wideband CW [ASSUMPTION]), R_c = 1.023 Mchip/s (C/A rate).

**Jamming margin:** GPS civil signals (−158.5 dBW min rx power [ASSUMPTION], ICD-GPS-200) have very small jamming margin (~20–45 dB). Even sub-Watt jammers deny receivers at significant range.

**AGC:** AGC backs off (agc_db goes negative) as noise floor rises.

### Jamming: wideband/chirp

**Mechanism:** Wider bandwidth. Spreading gain Q ≈ 1 (less benefit than narrowband, but still some rejection). Same C/N0-reduction formula.

### Combined jam-then-spoof

**Sequence:** Jammer operates first (denial phase), then transitions to spoofer phase. Jamming phase: all satellites above lock threshold are lost. Spoof phase: power bump and carry-off capture (as in drift-in spoofing).

**Literature:** Psiaki & Humphreys 2016 (qualitative "jam-to-degrade-then-spoof-to-capture" pattern [ASSUMPTION] on exact sequencing).

---

## Attack signature validation

Per scenario, attacks are run on a static-truth node, single representative severity per attack class, with a dedicated clean reference row (same truth, no attack). Results saved to `results/attacks/signature_summary.txt` (seed 123).

**Key signatures:**

| Attack | C/N0 | AGC | Clock jump | Code/Doppler consistency | RAIM behavior | Notes |
|--------|---|---|---|---|---|---|
| Drift-in spoof | +3–10 dB bump during capture, decays to 15% maintenance | Unaffected | None (smooth clock tracking) | Self-consistent fake trajectory | Statistically indistinguishable from clean (KS p=0.99, n=40) | Single-antenna correlation collapse: r ≈0.9996 post-capture |
| Meaconing | +0.3–4 dB | Unaffected | Common-mode jump ±5 m | Common delay (all PRNs shift together) | Close to nominal | Distinguishable by common-mode pattern |
| Abrupt spoof | Drop ~15 dB during lock-loss | Unaffected | Position jump (discontinuous) | Discontinuity during reacq | Indistinguishable post-reacq (KS p=0.9999) | Invalid fix during lock-loss window |
| Jamming CW | (C/N0)_eff via J/S formula, Q=2/3 | Negative (backs off) | Indirect via clock RW during dropout | N/A (jamming raises noise floor) | Low when sats remain, NaN when <4 sats | Total denial at high J/S |
| Jamming wideband | Same as CW, Q=1 | Negative | Indirect | N/A | Low when sats remain, NaN when <4 sats | Slightly less degradation per unit J/S than CW |

### Cross-check against literature

**Radoš et al. 2024** ("Recent Advances on Jamming and Spoofing Detection in GNSS," *Sensors* 24(13):4210):
- Field-measured spoofed C/N0: 35–55 dB-Hz vs clean 20–40 dB-Hz ✓ (our model: elevated during alignment, decays to 45 dB nominal [ASSUMPTION])
- Cross-satellite correlation: −0.76 (clean) vs 0.99 (spoofed) ✓ (our model measures ≈0 vs 0.9996)
- 5 dB power advantage → 98% SQM detection ✓ (our range: 3–10 dB bump)
- Discrimination rule: AGC decreases + C/N0 constant → spoofing; both decrease → jamming ✓ (our jamming model: both drop; spoofing model: C/N0 rises during capture, then holds constant [slight variant, both literature-plausible])

**Borhani-Darian et al. 2024** ("Detecting GNSS spoofing using deep learning," *EURASIP J. Adv. Signal Process.* 2024):
- Operates at the CAF (Cross-Ambiguity Function, correlation domain), not post-correlator observables like our model ✓ (D-004 design choice: raw-observable level is complementary)
- Test C/N0 range: 36–45 dB-Hz ✓ (within our modelled range 38–51 dB-Hz)
- No signature table analogous to ours provided (features are CAF probability maps, not observable statistics)

---

## Runtime performance

**Configuration:** Windows 11, Python 3.13, single node, static truth, clean GNSS + WLS PVT only (no attack overhead).

| Rate | Wall time per sim-hour |
|------|---|
| 1 Hz GNSS epochs | 7–11 s / sim-hour |
| 10 Hz GNSS epochs | 68–88 s / sim-hour |

Variance (7–11 s range) attributable to OS scheduling on short benchmark window (3 simulated min). For publication-grade reporting, longer (≥1 sim-hour) benchmark is recommended. At these rates, GNSS layer is not the multi-hour multi-node bottleneck (risk R-3, PROJECT_STATE.md).

---

## Limitations and known simplifications

- **Constellation:** Synthetic Walker almanac, no J2/perturbation propagation. Qualitatively realistic geometry (correct PRN count, elevation/DOP spread) over multi-hour windows, not tied to a real epoch's dated sky plot.
- **Clean signal:** Multipath/iono/tropo Gauss-Markov coefficients are [ASSUMPTION]-tuned to plausible magnitudes, not fitted to a specific published dataset. Receiver clock TCXO parameters are order-of-magnitude [ASSUMPTION], not tied to a specific datasheet.
- **Attacks:** Spoofed observables use delta-on-clean construction to maintain geometric consistency, but cannot exactly rescale the already-realised thermal-noise draw when C/N0 increases (see Section 4b note in raw GNSS_ATTACK_NOTES.md). The `maintenance_bump_fraction=0.15` mitigation keeps receiver-weight/actual-noise mismatch small enough to be statistically undetectable at n=40 independent draws, but it is a mitigation, not an exact fix — flagged for awareness.
- **Detector assumptions:** Cross-satellite C/N0 correlation-coefficient collapse under spoofing (Radoš et al. 2024 Fig. 5: 0.99 clean vs −0.76 spoofed) is modelled and exposed, but not yet used as an explicit detector feature in the FUSION+TRUST layer — a candidate future enhancement.

---

## Related decisions

- **D-004 (Master):** Attacks operate at the raw-observable level (pseudorange, Doppler, C/N0, AGC), not IF-sample level. Spoofing and jamming signatures are published in terms of these observables (Radoš 2024; Borhani-Darian 2024). Position-level offset injection would be unconvincing; IF-sample-level simulation would be computationally too expensive for multi-hour multi-node runs.
- **D-010 (Master):** Spoofed observables are deltas on clean observables; RAIM weights come from the signal model's own UERE budget. Never read `GnssEpoch.meta` in attack code (enforced by contract). Prior to this, spoofed ranges were pure geometry + true clock read from `meta`, making RAIM χ² exactly 0 (trivial giveaway).
- **D-013 (Master):** Bibliography ruling. Borhani-Darian et al. citation corrected from "Ad Hoc Networks 163:103597" (wrong, belongs to Korium et al.) to EURASIP JASP 2024, DOI 10.1186/s13634-023-01103-1 (correct).
- **D-018 (Master):** Model the cross-satellite C/N0 correlation of single-antenna spoofers (D-018 item 2, this section). Fix the pre-attack RAIM reference window in `scripts/gen_gnss_attack_results.py` to use paired clean receiver, not PRE-ONSET single-receiver window (D-018 item 1).

---

## Validation test execution

Run:
```bash
python -m pytest tests/test_gnss_receiver.py -v          # 27 tests
python -m pytest tests/test_gnss_raim_calibration.py -v   # RAIM calibration + blindness
python -m pytest tests/test_attacks_spoofing.py -v         # Attack signature checks
python scripts/gen_gnss_attack_results.py                  # Generate signature_summary.txt
```

**Status:** All tests pass; `signature_summary.txt` and `dop_distribution.txt` are reproducible from the seed-specified runs above.
