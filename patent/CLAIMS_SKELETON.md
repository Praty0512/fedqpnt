# FedQPNT — Patent Claim Skeleton (engineering draft)

_Author: PATENT agent · 2026-09-29 (rev. 1) · against DECISION_LOG.md up to D-058, PROJECT_STATE.md (M1 signed off; M2 in
progress; M4 gated), docs/specs/ARCHITECTURE.md, docs/specs/TRUST_DESIGN_V2.md, docs/REFERENCES.md +
REFERENCES_ADDENDUM_D044.md._
_Rev. 2 (PATENT-2 agent, 2026-09-30): revised against the FROZEN core (git tag `core-freeze-1`, commit a7c8bf0;
`fedqpnt/` is byte-identical to that tag in the working tree) and DECISION_LOG D-063 … D-072 +
docs/specs/raw/TRUST_SPLIT_DESIGN.md §6._

## Change log (rev. 2, 2026-09-30)

Engineering draft for later attorney review. Not legal advice; will not be filed by us.

| # | Change | Where |
|---|---|---|
| 1 | **Claim 1(vi) / claim 2 kept single-value** (lower-risk option per TRUST_SPLIT_DESIGN §6; see drafting note D1). The split is added as new dependent claims 23–24, 26. | §3, §4 |
| 2 | **Claim 1(vi) / 2 probe limb reworded** (frozen code no longer applies a partial-trust `w_probe = 0.3` update in the probe; it applies NO update). Also "trust value below a distrust threshold" → "remaining in a distrust state" (the T_ex timer runs on the distrust state, not on w). See flags F1, F2. | §3 |
| 3 | **Claim 1(vii) / 2 reputation limb reworded** (reputation gates participation by quarantine, it does not weight contributions in the frozen code). See flag F3. Master may veto and instead re-open the FL code. | §3 |
| 4 | **New dependent claims 21 (shadow probe), 22 (consistency-gated reacquisition), 23 (split trust), 24 (normalised clock-jump evidence), 25 (jump-test baseline reset + quarantine), 26 (clock-domain probe / holdover).** | §4 |
| 5 | **Claims 14, 15 scoped to the position trust value**; 14 made conditional on the claim-22 waiver. | §4 |
| 6 | **Claims 4, 5, 12, 20 reworded** to match the frozen code (see flags F4–F7). | §4 |
| 7 | §5 evidence gaps extended; new §5A (claim-vs-code audit table with flags); new §2A (prior-art notes for the new claims: NO search done; attorney to-dos). | §2A, §5, §5A |
| 8 | Heading numbering fixed (dependent claims are 4–26, not "12–20"). | §4 |

---

> **See §6 — this document is an engineering draft for attorney review, not legal advice, and must not be
> filed or relied upon as a patentability opinion.**

---

## 1. Summary of the invention

A fleet of navigation nodes (vehicles/UAVs), each combining a cold-atom interferometric accelerometer (CAI)
with a classical IMU and GNSS in a loosely-coupled error-state Kalman filter, is protected against GNSS
spoofing and jamming by a closed loop of three cooperating mechanisms. First, each node runs a lightweight
learned classifier that estimates the probability that the current GNSS fix is under attack from
innovation-, RAIM-, C/N0-, AGC- and clock-domain features; the classifier is trained centrally on
ground-truth-labelled missions and thereafter improved across the fleet by federated learning in which only
model-parameter updates (never raw sensor data, position, or attack labels) leave a node, and the server
aggregates updates using a combination of per-update norm clipping, coordinate-wise trimmed-mean/median
aggregation, and a cosine-similarity-based per-node reputation score, so that a bounded fraction of
poisoned/Byzantine node updates cannot corrupt the shared model. Second, the calibrated attack probability
drives a continuous trust law that inflates the GNSS measurement-noise covariance (rather than performing a
binary include/exclude switch), with an evidence-bounded exclusion policy: after a maximum continuous
exclusion time the node is forced into a "probe" state rather than left excluded indefinitely; in the frozen
design (D-066) the probe is a SHADOW probe in which the GNSS innovation is evaluated against the inertially
coasted state without being applied, and recovery back to trust is conditioned jointly on the consistency of
the resulting innovations (a statistic over a probe window, compared with a threshold calibrated on clean data
per inertial-sensor grade) and on the absence of independent physical spoofing evidence (signal- and
kinematics-domain rules), decoupled from the trust law's own state so the evidence cannot be self-triggered
by the exclusion dynamics. Since D-072 the trust is split: a position trust value and an independent clock
trust value, the latter driven by clock-bias-jump evidence normalised by the oscillator model's predicted
innovation uncertainty, so that a clock-only attack (e.g. co-located meaconing) does not cost position
accuracy. Third, the CAI is fused not as an independent navigation aid but as a direct
observation of the classical accelerometer's bias state, letting a slow, high-purity quantum reference
continuously correct the fast classical IMU inside the same filter. The combination lets a fleet detect and
recover from GNSS attacks that no single node could label on its own, without any node exposing raw
measurements, trajectories, or attack ground truth to the fleet, and without conceding unbounded navigation
divergence when the learned detector itself misbehaves.

---

## 2. Prior-art map (verified references only; per docs/REFERENCES.md and the D-044 addendum)

Ratings reflect what each source's abstract/verified text discloses (D-013, D-044) — not the full paper,
which several agents could not access in full text.

### FL spoofing detection

| Ref | Discloses | Does NOT disclose |
|---|---|---|
| **Khan 2025** (Trans. Emerg. Telecom. Tech. 36(4), 10.1002/ett.70138) | Federated learning across vehicles for GPS-spoofing detection; local SVM classifiers with weights aggregated at an RSU ("secure aggregation", mechanism not named in the verified text). | No disclosed robust aggregation mechanism (trimmed mean, clipping, reputation) verified against poisoning; no stated post-detection recovery/mitigation action; no continuous trust/covariance weighting; no quantum sensor. |
| **Chai 2025** (IEEE IoT J. 12, 10.1109/JIOT.2025.3588162) | Federated learning for UAV navigation spoofing/jamming *identification*; aggregation is **accuracy-weighted** (per D-044 verified abstract). | Accuracy-weighting is not shown to be Byzantine-robust; no disclosed trimmed-mean/clipping/reputation combination; no stated post-detection action; no continuous trust law; no quantum sensor fusion. |
| **Akram 2026** (IEEE Trans. Consumer Electronics, 10.1109/tce.2026.3677491) | Privacy-preserving federated learning framework specifically for securing consumer AVs against AI-enabled GPS spoofing. | Verified text does not establish the specific robust-aggregation combination (clip + trim + reputation) claimed here, nor an evidence-bounded exclusion/recovery trust law, nor CAI fusion. |
| **G²FL / Liu 2026** (ICC Workshops, 10.1109/ICCWorkshops63917.2026.11586283) | Closest robust-FL prior art: a robust federated-learning scheme explicitly aimed at GNSS spoofing detection (robustness to poisoned client updates is the paper's stated focus). | Per D-013, this is a robust-*FL* contribution, not a trust-coupled closed loop back into a navigation filter; no disclosed continuous covariance-inflation trust law with evidence-bounded exclusion; no CAI/quantum-sensor fusion. **This is the highest-risk reference against the FL-aggregation claim elements** (see §5). |

### Adaptive / switch fusion

| Ref | Discloses | Does NOT disclose |
|---|---|---|
| **Pardhasaradhi 2022** (IEEE Sensors J. 22(11), 10.1109/JSEN.2022.3168940) | GPS-spoofing detection and mitigation for drones via distributed radar tracking and sensor fusion; a detect-then-switch-to-an-independent-track scheme (per D-011, the B-bin baseline class). | Binary detect-and-switch, not a continuous trust/covariance-inflation law; no federated learning; no evidence-bounded exclusion/probe/recovery structure; no quantum sensor; radar, not CAI. |
| **Chen 2025** (IEEE Trans. Veh. Technol., 10.1109/tvt.2024.3454416) | LSTM-based anomaly detector, then a camera+map UKF fallback — a detect-then-switch scheme (per D-044). | Same class of gap as Pardhasaradhi: binary switch, not continuous trust; no FL; no quantum sensor. |
| **Wang 2025** (IEEE IoT J., 10.1109/jiot.2024.3424518) | V2V density-clustering GPS-attack detection, then cooperative localization — detect-then-switch (per D-044). | No continuous trust law; no robust FL aggregation of the kind claimed; no quantum sensor. |
| **Mehra 1970** (IEEE TAC 15(2), 10.1109/tac.1970.1099422) | Foundational innovation-based adaptive Kalman filtering (variance/noise identification from innovations); the classical adaptive-KF baseline class (B′, per D-011). | No learned/FL-trained detector; no discrete attack-probability-to-trust mapping; no evidence-bounded exclusion or probe/recovery states; no GNSS-attack-specific features; no quantum sensor. |

### Quantum inertial sensing

| Ref | Discloses | Does NOT disclose |
|---|---|---|
| **Wright 2022** (Frontiers in Physics 10:994459, 10.3389/fphy.2022.994459) | Cold-atom inertial sensors for navigation applications generally (survey/positioning of the technology). | No GNSS-spoofing detection or trust application; no federated learning; no specific hybridisation architecture (CAI as a direct bias observation on a classical IMU) of the kind claimed. |
| **Lautier 2014** | Hybridisation of a cold-atom accelerometer with a classical (conventional) accelerometer, demonstrating the general concept of combining the two sensor types. | No GNSS or navigation-filter context of the kind claimed; no spoofing/attack application; no FL; the specific "CAI observes the classical bias state inside an ES-EKF used for navigation under adversarial GNSS" architecture is not shown. |
| **Cheiney 2018** | Atom-interferometer hybridisation with classical accelerometers, cycle-time and dead-time characterisation informing this project's `quantum.cycle_time` defaults (§1.2 ARCHITECTURE). | No navigation-filter integration as a bias observation for GNSS-attack robustness; no FL; no fleet context. |
| **Templier 2022** | Cold-atom interferometer performance/cycle-rate characterisation, also informing `quantum.cycle_time`. | Same gap as Cheiney 2018: sensor-physics characterisation only, no navigation/security application. |

### Quantum federated learning

| Ref | Discloses | Does NOT disclose |
|---|---|---|
| **Chehimi & Saad** (ICASSP 2022, 10.1109/ICASSP43922.2022.9746622) and companion **Chehimi et al.** (IEEE Network 2023, 10.1109/MNET.2023.3327365) | Federated learning over classical/quantum *communication and computation* networks (quantum-enhanced learning models, e.g. FedQLSTM). Per D-013, this is FL over quantum *networks/models*, verified. | Per D-013 ruling: **no clock synchronization or positioning application using quantum *sensors***. Does not disclose fusing a physical quantum inertial sensor's output into an FL-trained GNSS-attack detector or a navigation filter. |
| **Hazarika** (IEEE Trans. Commun. 2025, 10.1109/TCOMM.2024.3502667) | Quantum-*enhanced* federated learning (a computational technique) for metaverse-empowered vehicular networks. | Per D-013 ruling: quantum-enhanced *computation*, not quantum *sensing*; no GNSS, no navigation filter, no CAI hardware/model. |

**Novelty gap as re-verified by the Master (D-013):** with the originally proposed Kannamarlapudi 2025
reference dropped (unverifiable) and Chehimi/Hazarika reframed, **no verified prior-art reference combines
(a) physical cold-atom/quantum inertial sensing, (b) federated learning, and (c) GNSS-spoofing-robust trust
fusion** in one system. G²FL (robust FL for GNSS spoofing) and Pardhasaradhi-class switch fusion are the
closest single-axis priors; neither combines with the other two axes. This map must be re-run against the
issued/published claims of G²FL specifically before filing (§5).

---

## 2A. Prior-art notes for the rev. 2 claims (21–26) — NO SEARCH HAS BEEN RUN

The §2 map above was built for the rev. 1 claims (D-013/D-044). **No prior-art search of any kind has been
performed for claims 21–26, and no reference is cited for them here.** Nothing below is a finding that these
claims are novel or non-obvious. The following are search topics the attorney/searcher must cover; each is a
general technical field, not a reference:

- **Claim 21 (shadow probe):** probationary re-admission of a previously excluded GNSS measurement; evaluating
  a measurement's innovation against a free-running/coasted inertial estimate without updating (open-loop or
  "monitor-only" innovation tests); INS-aided GNSS integrity monitoring and consistency tests; clean-data
  (false-alarm-rate) calibration of an acceptance threshold per inertial-sensor grade. Innovation-based
  consistency testing is a long-established technique (cf. Mehra 1970 already in §2, which concerns adaptive
  noise identification, not this use). Whether the *combination* (probe state entered after a bounded
  exclusion time + no-update evaluation + windowed statistic + per-grade clean calibration) is known is
  UNKNOWN.
- **Claim 22 (consistency-gated reacquisition):** re-acquisition/first-fix handling after GNSS outages in
  INS/GNSS filters; inflation or capping of trust on the first post-outage fix and conditions that lift it.
- **Claims 23, 24, 26 (split trust; clock evidence):** separate treatment of receiver-clock and position
  errors in spoofing/meaconing defence; receiver clock-jump detection for spoofing/meaconing; oscillator-
  model-normalised clock innovation tests; clock holdover on measurement exclusion. The two-state TCXO
  oscillator model used for normalisation and holdover is the textbook model (Brown & Hwang; Krawinkel &
  Schön 2021; Qin et al. 2021 — these are cited in the repo, `fedqpnt/fusion/clock.py`, and were verified by the
  user for the *oscillator parameters*, NOT reviewed as prior art against these claims). The attorney should
  treat them, and the wider receiver-clock-modelling literature, as potentially relevant prior art for
  claims 24 and 26.
- **Claim 25 (baseline reset + quarantine):** short-baseline position-jump / delta-position consistency tests
  and their handling of data gaps.
- **Standing item (unchanged):** obtain and read the actual claims of G²FL/Liu 2026 and other robust-FL
  GNSS-spoofing schemes before finalising the FL limb (§5, "Elements at risk"). The reputation limb change in
  claim 1(vii) (flag F3) must be re-run against that search: quarantine-by-reputation is a different mechanism
  from reputation-weighting, and the prior-art position of each is unknown to us.

---

## 3. Independent claims

Standard US claim drafting form: a preamble, transitional "comprising," and antecedent basis established on
first recitation and reused thereafter. Numbering is provisional (Claim 1 = system, Claim 2 = method, Claim 3
= medium); dependent claims in §4 attach to whichever independent claim they most naturally extend, noted per
claim.

### Claim 1 (System)

1. A distributed navigation system comprising:
   a plurality of navigation nodes, each navigation node comprising:
   (i) an inertial measurement unit configured to output classical acceleration and angular-rate
   measurements;
   (ii) a cold-atom interferometric accelerometer configured to output a quantum acceleration measurement at
   a quantum-sensor cycle time;
   (iii) a global-navigation-satellite-system receiver configured to output a navigation fix derived from
   received satellite signals;
   (iv) a fusion filter configured to estimate a navigation state of the navigation node by propagating the
   navigation state using the classical acceleration and angular-rate measurements and correcting the
   navigation state using the navigation fix and the quantum acceleration measurement, wherein the fusion
   filter is configured to use the quantum acceleration measurement as a direct observation of a bias state
   of the inertial measurement unit;
   (v) a trained classifier configured to compute, from features derived at least from an innovation of the
   navigation fix against the fusion filter, a calibrated probability that the navigation fix is subject to a
   spoofing or jamming attack;
   (vi) a trust engine configured to compute, from the calibrated probability and from the innovation, a
   continuous trust value and to set a measurement-noise covariance applied by the fusion filter to the
   navigation fix as an inflation of a nominal measurement-noise covariance by an amount that varies
   continuously with the trust value, wherein the trust engine is further configured to: responsive to the
   navigation node remaining continuously in a distrust state for longer than a maximum exclusion duration,
   transition the navigation node from the distrust state to a probe state in which an influence of the
   navigation fix on the navigation state is determined independently of the calibrated probability; and
   responsive to an innovation consistency condition being satisfied during the probe state and to an absence
   of physical attack evidence determined independently of the trust value, transition the navigation node to
   a trust state; and
   (vii) a federated-learning client configured to train a local update to parameters of the trained
   classifier using data local to the navigation node and to transmit the local update, without transmitting
   raw sensor data, the navigation fix, or the navigation state, to a server; and
   a server communicatively coupled to the plurality of navigation nodes, the server comprising an aggregator
   configured to receive a plurality of local updates from the plurality of navigation nodes and to compute
   an aggregated update by: clipping each local update of the plurality of local updates to a bounded norm;
   computing a coordinate-wise trimmed-mean or coordinate-wise median of the clipped local updates; and
   updating, for each navigation node, a reputation score computed from a similarity between that navigation
   node's local update and the aggregated update over a preceding plurality of rounds, and excluding from
   subsequent aggregation rounds a navigation node whose reputation score remains below a reputation
   threshold for a predetermined number of consecutive rounds; and to transmit the aggregated update to the plurality of
   navigation nodes for use as updated parameters of the trained classifier.

### Claim 2 (Method)

2. A method for robust distributed navigation, comprising, at each navigation node of a plurality of
   navigation nodes:
   obtaining classical acceleration and angular-rate measurements from an inertial measurement unit;
   obtaining a quantum acceleration measurement from a cold-atom interferometric accelerometer;
   obtaining a navigation fix from a global-navigation-satellite-system receiver;
   propagating a navigation state using the classical acceleration and angular-rate measurements;
   correcting the navigation state using the quantum acceleration measurement as a direct observation of a
   bias state of the inertial measurement unit;
   computing, from features derived at least from an innovation of the navigation fix against the navigation
   state, a calibrated probability that the navigation fix is subject to a spoofing or jamming attack, using
   a classifier trained via federated learning;
   computing a continuous trust value from the calibrated probability and the innovation;
   setting a measurement-noise covariance for the navigation fix as an inflation of a nominal
   measurement-noise covariance that varies continuously with the continuous trust value, and correcting the
   navigation state using the navigation fix weighted by the measurement-noise covariance;
   responsive to the navigation node remaining continuously in a distrust state for longer than a maximum
   exclusion duration, entering a probe state in which an influence of the navigation fix on the navigation
   state is determined independently of the calibrated probability;
   during the probe state, evaluating an innovation consistency condition and evaluating, independently of the
   continuous trust value, whether physical attack evidence is present;
   responsive to the innovation consistency condition being satisfied and the physical attack evidence being
   absent, exiting the probe state to a trust state; responsive otherwise, returning to a distrust state;
   training a local update to parameters of the classifier using data local to the navigation node; and
   transmitting the local update, without transmitting raw sensor data, the navigation fix, or the navigation
   state, to a server that computes an aggregated update by clipping each of a plurality of local updates
   received from the plurality of navigation nodes to a bounded norm, computing a coordinate-wise
   trimmed-mean or median of the clipped local updates, updating for each navigation node a reputation score
   derived from consistency of that navigation node's local updates with the aggregated update over time,
   excluding from subsequent aggregation rounds a navigation node whose reputation score remains below a
   reputation threshold for a predetermined number of consecutive rounds, and transmitting the aggregated update back to the plurality of navigation nodes.

### Claim 3 (Non-transitory computer-readable medium)

3. A non-transitory computer-readable medium storing instructions that, when executed by one or more
   processors of a navigation node comprising an inertial measurement unit, a cold-atom interferometric
   accelerometer, and a global-navigation-satellite-system receiver, cause the one or more processors to
   perform the method of claim 2.

**Drafting note D1 — single vs "one or more" trust values (claim 1(vi)).** TRUST_SPLIT_DESIGN §6 offers two
options: (A) broaden 1(vi) to "one or more trust values / measurement-noise covariances" (single value as a
special case), or (B) keep the single value and add the split as a dependent claim. **Option B is chosen.**
Reasons: (1) it leaves the independent claims narrower in text but unchanged in scope relative to what rev. 1
already reviewed, so the prior-art map of §2 still applies to them; (A) widens the independent claims and
invites new prior art (any multi-channel weighting scheme) that has not been searched (§2A); (2) the split is
an *addition* to, not a replacement of, the position trust value: in the frozen code the "trust value applied
to the navigation fix" of 1(vi) is exactly the position law `gnss_law` (`fedqpnt/trust/trust_law.py`, class
`TrustEngineImpl.__init__`, ~L698–703; consumed by `fusion/eskf.py::correct`, ~L413–416), so a split system
still literally meets claim 1(vi); (3) the design note itself rates (B) the lower-risk option and the main
novelty gain (a second, independent clock trust value) is captured by dependent claim 23. Residual risk of (B):
a competitor who *only* trusts clock and position through one merged value is covered by claim 1, but a
competitor who uses a clock trust value and a position weight that does not inflate a measurement-noise
covariance per 1(vi) would not be; if the attorney wants to protect the split as a stand-alone invention, an
additional independent claim to claim 23's subject matter (without CAI/FL limbs) should be considered.
Note also that the aggregate weight `weights["gnss"] = min(w_pos, w_clk)` (trust_law.py ~L927) is a
back-compat alias only and is NOT what the ESKF uses when the split laws exist.

**Drafting note D2 — probe limb of 1(vi)/2.** Rev. 1 recited "the measurement-noise covariance is set to a
partial-trust value independent of the calibrated probability" (that was `w_probe = 0.3`). In the frozen code
`w_probe` is still written into the law (`_LawCoreV2.advance`, PROBE branch, ~L356) but
`ESKF.correct` **skips the GNSS update whenever `trust.probe_shadow` is true** (`fusion/eskf.py` ~L411–412), so
no partial-trust update is applied. The limb is therefore reworded to "an influence of the navigation fix on
the navigation state is determined independently of the calibrated probability", which reads on both the
frozen shadow probe (influence = none) and the earlier partial-trust embodiment; the shadow-specific
characterisation is dependent claim 21. The attorney should decide whether the earlier partial-trust
embodiment (which D-066 found to drag the state onto a persisting spoof) should remain in the disclosure as
an alternative embodiment.

**Drafting note D3 — "distrust state" vs "trust value below threshold".** The maximum-exclusion timer
`_distrust_timer` runs while the state machine is in DISTRUST (`_LawCoreV2.advance` ~L338–347), and DISTRUST is
entered from the hysteresis detection flag D, not from `w` crossing a threshold. Rev. 1 wording ("trust value
remaining below a distrust threshold") did not match; corrected.

**Drafting note D4 — reputation limb of 1(vii)/2 (flag F3).** In the frozen aggregator
(`fedqpnt/fl/aggregator.py::trim_nb_r_aggregate`, ~L83–150) the reputation score (EWMA, `rep_rho = 0.8`, of
`max(0, cosine)` between the clipped update and the aggregate) is used ONLY to trigger quarantine (a streak of
`quarantine_streak = 3` rounds below `rep_q = 0.2`, excluded for `quarantine_rounds = 10`); the reputation
score is never used as a weight on the node's contribution to the aggregate (grep: `reputation` is read only in
the aggregator and logged by `fl/orchestrator.py`). Rev. 1's "weighting ... by a reputation score" is therefore
not implemented. The claim now recites reputation-gated exclusion. If the intent was reputation weighting, the
FL code — not the claim — must change, and the freeze must be reopened.

---

## 4. Dependent claims (4–26)

Each attaches to Claim 1 (system) with a corresponding method-claim (Claim 2) analogue implied; the method and
medium analogues of claims 21–26 have NOT been drafted and should be added once the attorney selects which of
them to keep.

4. The system of claim 1, wherein the fusion filter is configured to apply a soft covariance-scaling gate
   that, responsive to a normalized innovation statistic of the navigation fix exceeding a chi-squared
   threshold, scales the measurement-noise covariance so that the scaled normalized innovation statistic
   equals the chi-squared threshold, rather than excluding the navigation fix.
   _[Rev. 2: rev. 1 said the trust engine "determines the physical attack evidence using" the gate. The gate is
   in the filter's correction step (`fusion/eskf.py::correct`, ~L421–435, D-057) and does not produce evidence;
   flag F4. Wording corrected. Note the ESKF still hard-skips the update below `w_excl` = 0.05 (~L417), which
   claim 1(vi)'s "inflation varies continuously" does not mention.]_

5. The system of claim 1, wherein the physical attack evidence comprises a result of a short-baseline jump
   test comparing a change in position of the navigation fix over a preceding navigation-fix epoch against a
   change over the same epoch in a pre-correction position estimate of the fusion filter, propagated using the
   inertial measurement unit, the comparison being normalised by a covariance comprising the covariances of
   the navigation fixes at both epochs, and being evaluated independently of the trust value or the trust
   engine's state history.
   _[Rev. 2: supported by `TrustEngineImpl._physical_spoof_evidence`, trust_law.py ~L766–836; d = ΔpGNSS −
   ΔpINS, statistic d'S⁻¹d vs chi2_3(0.999), S = cov_now + cov_prev + (0.05 m)²·I. The "INS" side is
   `p_prior = fix.pos + ν_pos` from the previous GNSS epoch, i.e. the filter's own pre-correction estimate, not a
   pure-IMU integration (flag F5, wording corrected). In the frozen design this term is SUPERSEDED during the
   probe state by the shadow-consistency test (`_LawCoreV2.advance`, `es_pos_active`, ~L307–311) and, after the
   split (D-072), feeds the position law only.]_

6. The system of claim 1, wherein each navigation node comprises a single antenna, and wherein the physical
   attack evidence comprises a correlation, across a plurality of satellites tracked by the
   global-navigation-satellite-system receiver, of a carrier-to-noise-density-ratio feature exceeding a
   floored nominal band.

7. The system of claim 1, wherein the trained classifier comprises a plurality of output heads, each output
   head corresponding to a class of attack, and wherein the calibrated probability for each output head is
   computed by applying a per-head Platt-scaling calibration fitted independently for that output head.

8. The system of claim 1, wherein the local update is trained using a loss function that applies a class
   weight to positive-labeled training examples, the class weight capped at a predetermined maximum
   multiplier relative to a negative-class weight.

9. The system of claim 1, wherein the federated-learning client is configured, responsive to the navigation
   node joining the distributed navigation system after the trained classifier has already been trained on
   other navigation nodes, to initialize the parameters of the trained classifier from a most-recently
   received aggregated update rather than from an untrained state.

10. The system of claim 1, wherein the trust engine is configured to distinguish jamming evidence, comprising
    a signal-strength loss or a tracking-lock loss, from the physical attack evidence, and to permit the
    transition to the trust state notwithstanding the presence of jamming evidence.

11. The system of claim 1, wherein the fusion filter comprises a world model in which a gravity vector and a
    navigation-frame rotation are modeled to reproduce a Schuler oscillation of a free-inertial position
    error, and wherein the bias state of the inertial measurement unit is estimated using the quantum
    acceleration measurement within that world model.

12. The system of claim 1, wherein the navigation fix comprises a receiver clock-bias estimate and a receiver
    clock-drift estimate, and wherein the trust engine determines clock-jump evidence from a deviation of the
    receiver clock-bias estimate from a prediction based on a preceding receiver clock-bias estimate and
    clock-drift estimate, or from a change in the receiver clock-drift estimate, exceeding a threshold
    expressed as a multiple of a standard deviation.
    _[Rev. 2, flag F6: rev. 1 recited "a jump in the clock-bias STATE of the fusion filter" as "the physical
    attack evidence" of claim 1. In the frozen code (a) the evidence is computed from the RECEIVER's reported
    clock bias/drift (features x8/x9, `trust/features.py` ~L186–194), not from a filter state; (b) the ESKF has
    no clock state (a separate `ClockKF`, `fusion/clock.py`); (c) since D-072 the clock jump no longer feeds the
    position law's probe veto or evidence (`trust_law.py` ~L889–892: position law receives only xsat/cn0
    `es_xc` and the position jump), only the clock law (~L895–901). Claim 12 therefore no longer depends on the
    claim 1 "physical attack evidence" and is reworded as a stand-alone evidence source; it is the basis of
    claims 23–24.]_

13. The system of claim 1, wherein the reputation score for a given navigation node is computed as an
    exponentially-weighted moving average of a cosine similarity between that navigation node's local update
    and the aggregated update, and wherein the aggregator is configured to reduce the influence of a
    newly-joined navigation node's local update for an initial plurality of rounds.

14. The system of claim 1, wherein responsive to the global-navigation-satellite-system receiver producing a
    first valid navigation fix after an outage exceeding a predetermined duration, the trust engine is
    configured to cap the trust value applied to the navigation fix (the position trust value) at a
    reacquisition ceiling below full trust, independent of the calibrated probability.
    _[Rev. 2: scoped to the position trust value per TRUST_SPLIT_DESIGN §6. Code: `SensorTrustLaw.
    apply_reacquisition_cap`, trust_law.py ~L483–489, `w = min(w, w_reacq = 0.5)`; outage > `T_gap` = 5 s, ~L902.
    In the frozen code the cap is applied to the position trust value only when the consistency waiver of claim
    22 does not hold. A separate cap on the clock trust value is applied unconditionally (~L914–915) — see
    claim 26 if the attorney wants it claimed.]_

15. The system of claim 1, wherein the trust engine is configured to suppress use of the calibrated
    probability for a predetermined suppression duration after transitioning from the probe state to the
    trust state, such that the trust value applied to the navigation fix (the position trust value) during the
    suppression duration is governed by the physical attack evidence rather than by the calibrated
    probability.
    _[Rev. 2: scoped to the position trust value. Code: `_suppress_timer`/`T_sup` = 120 s, trust_law.py
    ~L312–326, ~L369. FLAG F8: the clock law is the same `_LawCoreV2` class (`clk_law`, ~L702) and therefore also
    suppresses the detector for the clock trust value after ITS OWN probe exit; the claim is limited to the
    position value to match the design note, but the clock-law behaviour exists and can be claimed if wished.]_

16. The system of claim 1, wherein the quantum acceleration measurement is used to correct the bias state of
    the inertial measurement unit at a cycle time longer than an update rate of the inertial measurement unit,
    and wherein the fusion filter is configured to omit correction using the quantum acceleration measurement
    at ticks at which no quantum acceleration measurement is available.

17. The system of claim 1, wherein the trust engine applies asymmetric rates of change to the trust value,
    such that the trust value decreases toward the distrust threshold faster than it increases toward the
    trust state.

18. The system of claim 1, wherein the aggregator is configured to compute the coordinate-wise median of the
    clipped local updates responsive to a number of navigation nodes contributing to a given round falling
    below a predetermined threshold, and the coordinate-wise trimmed mean otherwise.

19. The system of claim 1, wherein the features from which the calibrated probability is computed comprise at
    least one of: a receiver autonomous integrity monitoring statistic, an automatic-gain-control feature, a
    satellite-count feature, and a slope feature derived from a rate of change of a carrier-to-noise-density
    ratio.

20. The method of claim 2, further comprising evaluating, over a preceding time interval, a normalized
    estimation error squared statistic of the navigation state against a chi-squared bound, and
    reporting a divergence event responsive to the statistic exceeding the chi-squared bound for longer than a
    predetermined duration.
    _[Rev. 2, flag F7: "innovation-normalized-error-squared" in rev. 1 is not a defined quantity (garbled NIS/NEES).
    Reworded to NEES. Also, in the frozen code ANEES is an EVALUATION metric (`fedqpnt/eval/metrics.py::anees_pos`,
    `node/runner.py` ~L215, needs ground truth) and no run-time "divergence event" reporting was found by
    grep in `fedqpnt/`; this claim is likely UNSUPPORTED as a node-side method step and should be deleted or
    re-based on a truth-free NIS-based statistic (which exists in the filter). Master/attorney to decide.]_

### New dependent claims added in rev. 2 (D-063 … D-072; frozen code tag `core-freeze-1`)

21. The system of claim 1, wherein, in the probe state, the fusion filter applies no correction of the
    navigation state using the navigation fix, and the trust engine: evaluates, for each navigation fix
    received during the probe state, an innovation of the navigation fix against the navigation state as
    propagated by the inertial measurement unit without correction by the navigation fix, normalised by a
    covariance comprising the covariance of the navigation state and a covariance reported by the
    global-navigation-satellite-system receiver for the navigation fix; accumulates a consistency statistic
    of the normalised innovations over a probe window; and transitions to the trust state only if the
    consistency statistic is below a probe threshold, the probe threshold having been calibrated on
    attack-free data for a grade of the inertial measurement unit.
    _[Support: `_LawCoreV2.advance` PROBE branch, trust_law.py ~L348–378 (mean joint 6-D shadow NIS over
    `T_probe` = 10 s vs `probe_nis_bound`, and no clk/xsat/cn0 evidence); shadow innovation built in
    `fusion/eskf.py::innovations` ~L349–360 (`sensor="gnss_shadow"`, receiver's un-inflated covariance, NOT the
    κ_R-inflated filter covariance; D-069); update skipped in `ESKF.correct` ~L411–412 via
    `TrustState.probe_shadow`; per-grade thresholds `PROBE_NIS_BOUND_BY_GRADE = {industrial_mems: 25.07,
    tactical: 6.74}` in `fedqpnt/node/methods.py` ~L49, ~L97–98, frozen by D-071 as the 99th percentile of the
    clean mean-shadow-NIS on disjoint tuning seeds 510–529 (default chi2_6(0.99) if unset). "Propagated by the
    IMU without correction by the fix" is the ESKF state before the update, which in the frozen design also
    includes the CAI bias correction — the claim deliberately does not exclude CAI. CANDOR/LIMITATION (D-066,
    D-071): a consistency-matched adversary that keeps the spoof inside the coast uncertainty passes the probe;
    on the MEMS grade, offsets of 10/26/50 m were vetoed in 0.00/0.07/0.70 of windows (tactical
    0.37/1.00/1.00) at the frozen bounds. These are tuning-seed, simulation results; nothing here is a claim of
    performance. The attorney should assess whether the specification must disclose this limitation.]_

22. The system of claim 14, wherein, responsive to the first valid navigation fix after the outage, the
    trust engine withholds the reacquisition cap when (i) a normalised innovation of the first valid navigation
    fix against the navigation state as propagated by the inertial measurement unit through the outage,
    without correction by the first valid navigation fix, is below a consistency threshold, and (ii) no
    physical attack evidence is present for the first valid navigation fix.
    _[Support: trust_law.py ~L902–915: `consistent = shadow_nis <= bound and not (es_xc or es_pos)`; cap applied
    only if not consistent; `tau_r` unchanged. Same bound and same consistency-matched-adversary limit as claim
    21 (comment at ~L903–906). "Physical evidence" here is the position jump test (claim 5 — which is skipped
    at this epoch by the gap reset of claim 25, so in practice only the xsat/cn0 evidence is live on that
    epoch; flag F9: the `es_pos` term in this waiver test is therefore near-vacuous on the very epoch tested)
    plus the xsat/C-N0 evidence. Depends on claim 14 for antecedent; the attorney may re-base it on claim 1
    directly.]_

23. The system of claim 1, wherein the trust engine is further configured to compute a second continuous
    trust value for a receiver clock state of the navigation node, independently of the trust value applied to
    the navigation fix, from clock-jump evidence derived from receiver clock-bias and clock-drift estimates of
    the navigation fix; wherein the navigation node further comprises a clock filter estimating the receiver
    clock state, the clock filter applying a clock measurement update with a clock measurement-noise
    covariance inflated by an amount that varies continuously with the second continuous trust value; and
    wherein the clock filter skips the clock measurement update and propagates the receiver clock state
    using an oscillator model alone when the second continuous trust value is below an exclusion threshold.
    _[Support: `TrustEngineImpl.clk_law` (trust_law.py ~L698–703), fed by `es_clk or es_xc` and the detector p,
    and NOT by the position jump test (~L895–901); the position law is NOT fed by the clock jump (~L889–892;
    "clk_event does NOT cost position", ~L890). Clock filter: `fusion/clock.py::ClockKF.step` ~L88–118
    (`R = diag(r_bias, r_drift)/max(w, w_min)`; update only if `w >= w_excl` = 0.05 ~L107; process noise Q is
    oscillator physics, not scaled by trust); wiring `node/agent.py` ~L131–134 (`w_clk` from
    `weights["gnss_clk"]`). Basis: TRUST_SPLIT_DESIGN §6 "main novelty gain". Independence caveat: both laws share
    the SAME learned detector output p and the xsat/cn0 evidence (D-072: "the detector p drives both"), so the
    two values are independent in their clock-jump and position-jump evidence terms only; under meaconing the
    trained detector still depresses the position value (D-072 caveat) — whether the split recovers position
    accuracy is UNMEASURED (D-072 step 4 pending). Claim language "independently of the trust value applied to
    the navigation fix" should be checked by the attorney against this shared-p coupling.]_

24. The system of claim 23, wherein the clock-jump evidence comprises a clock-bias deviation and a clock-drift
    deviation each normalised by a predicted oscillator innovation uncertainty computed, from an oscillator
    process-noise model and a receiver measurement-noise variance, as a function of the time elapsed since a
    preceding receiver clock estimate, the predicted oscillator innovation uncertainty increasing with the
    elapsed time.
    _[Support: `trust/features.py` ~L186–194 and module comment ~L62–72 (D-071): σ_b² = r_bias + q_bias·Δt +
    q_drift·Δt³/3; σ_d² = r_drift + q_drift·Δt; x8 = |clk_bias − (last_bias + last_drift·Δt)|/σ_b,
    x9 = |clk_drift − last_drift|/σ_d; q from `core/defaults.py` (TCXO, Brown & Hwang; Krawinkel & Schön 2021;
    Qin et al. 2021). Threshold `es_clk_sigma` = 5 (trust_law.py ~L811–813). FLAG F10 (possible implementation
    gap, to be verified by the Master, NOT asserted): `GnssFeatureExtractor.step` updates `_last_t` on EVERY
    call, including invalid/outage fixes (features.py ~L215 onward), whereas `_last_clk_bias/_drift` update only
    on non-outage epochs. If the receiver emits `valid=False` fixes during an outage (gnss/receiver.py ~L78–85
    does emit them) and the agent passes them to the extractor, Δt at the first post-outage fix is ~1 epoch, not
    the outage length, and the "normalised over the gap" behaviour claimed here would not hold on that path. The
    D-071 tests (tests/test_trust_features.py ~L98–131) skip the outage epochs, so they do not exercise this
    path. LIMITATION (D-071 test, ~L121): a 750 m replay-delay step after a 180 s gap gives x8 ≈ 2.85, below the
    threshold of 5 — the clock evidence is blind to it by construction; disclosed, not tuned.]_

25. The system of claim 5, wherein the trust engine stores, for each navigation-fix epoch, the position of the
    navigation fix and the pre-correction position estimate of the fusion filter; resets the stored values
    when an interval since a preceding valid navigation fix exceeds a multiple of a nominal navigation-fix
    epoch interval; and, after such a reset, suppresses the short-baseline jump test for a quarantine window
    of a predetermined number of navigation-fix epochs.
    _[Support: trust_law.py ~L838–871 (`es_gap_reset_factor` = 1.5 × `es_nominal_epoch_s` = 1.0 s; reset of
    `_last_gnss_pos/_last_gnss_cov/_last_p_prior`; `_es_position_quarantine = 2` covers the stale-baseline epoch
    and the corrective-pull epoch), D-058 follow-up and D-063 (accepted). Fixes a false fire of the jump test on
    every first post-outage fix. "Nominal epoch interval" 1 s is an [ASSUMPTION]-grade constant matching the 1 Hz
    GNSS rate.]_

26. The system of claim 23, wherein the trust engine operates the second continuous trust value with the same
    distrust, probe and trust states as the trust value applied to the navigation fix, and wherein, in the
    probe state of the second continuous trust value, the clock filter skips the clock measurement update, and
    the trust engine accepts a transition to the trust state only if a chi-squared statistic of the normalised
    clock-bias and clock-drift deviations, accumulated over the probe window, is below a clock probe threshold
    and no clock-jump or cross-satellite evidence is present.
    _[Support: `clk_law` is a second `SensorTrustLaw` (v2) with `probe_nis_bound = CHI2_2_99` (trust_law.py
    ~L44, ~L702); `clk_stat = x8² + x9²` fed as `nis_value` (~L896–899); in `node/agent.py` ~L134 the clock filter
    receives weight 0 while `clk_probe_shadow` is true (hard holdover). The clock reacquisition cap is applied
    unconditionally (~L914–915; comment: "cap kept (no clock-domain coast statistic)"), i.e. no clock analogue
    of claim 22. FLAG F11: the clock-domain probe statistic is NOT computed against a coasted clock state but
    against the last receiver clock estimate via the x8/x9 features; it is a jump/consistency statistic, not a
    "shadow innovation against the free-running oscillator" — the claim is worded accordingly (statistic of the
    normalised deviations) and should not be broadened to "shadow probe" of the clock without a code check.]_

---

## 5. Elements NOT yet evidenced — must be confirmed before filing (M4 campaign pending)

Per PROJECT_STATE.md, M1 (single-node) is signed off with stated limitations on **tuning seeds only**; M2
(federation) is infrastructure-complete but FL detection results are not yet valid (D-054 previews rejected,
D-056 protocol redesign in progress); M3 (baselines/stats) has not run at scale; **M4 (the full 15-scenario
campaign, including poisoning robustness S12 and CAI-benefit claims) is gated** (D-046/D-047) and has not
run; test seeds (10000+) are completely untouched. Concretely, before any claim relying on measured
performance or a specific numeric bound is filed:

1. **Robust-aggregation efficacy under poisoning (Claim 1(vii)/server; dependent claims 13, 18).** S12
   (poisoning at f = 20%/40%) has only run at N = 10 nodes with an inconclusive confidence interval
   (PROJECT_STATE open issue #4); the claimed clip+trim+reputation combination's robustness bound (β = 20%
   theoretical breakdown) is not yet empirically confirmed at fleet scale or against the D-058
   core-robustness-session filter changes.
2. **The federated-learning contribution itself (H2/H4, claim 1(v)/(vii), dependent claim 9).** Per D-054,
   the only completed H2/H4 previews were invalidated (identical AUCs across arms, a θ0-protocol flaw); D-056
   redesigned the evaluation to isolate learned-detector-only AUC from rule-based evidence; this redesigned
   protocol has not yet produced accepted results (open per PROJECT_STATE work queue item 2). **The system
   claims should not be filed representing a demonstrated FL benefit until this is re-run and accepted.**
3. **Evidence-bounded exclusion / E_s independence (claims 1(vi), dependent claim 5).** D-058 found the
   original E_s "position term" was self-contaminated by the trust law's own exclusion dynamics (fired on
   ~99% of drift/meaconing attack epochs via a coupled mechanism, not independent evidence) and replaced it
   with the short-baseline jump test recited in dependent claim 5 — **this replacement is specified but its
   validation (the D-058 core-robustness session) had not completed as of the last DECISION_LOG entry
   reviewed.** Confirm the jump test actually decouples from trust-law state before relying on "independent
   physical evidence" language in claim 1(vi)/5.
4. **Soft covariance-scaling gate (dependent claim 4).** D-057 adopted this as a fix for a catastrophic
   shared-core hard-gate lockout (s = 0 harm up to 22× worse than undefended); the fix is specified as a
   decision but the "must re-verify" list (S1, abrupt-spoof mitigation, s = 0 safety bound) in D-057 was not
   yet confirmed passing at time of writing.
5. **Overconfidence / κ_R (dependent claims 11, 16 to the extent they rely on P being well-calibrated).**
   PROJECT_STATE open issue #1: ESKF attitude/bias covariance is known overconfident; κ_R = 40 is PROVISIONAL;
   S6/S14/CAI-H3 claims are formally gated (D-047) pending the pre-M4 filter session.
6. **CAI quantitative benefit (claim 1(iv)/(vi), dependent claim 11).** PROJECT_STATE issue #3: CAI benefit
   for MEMS-grade IMUs is PRELIMINARY and blocked by the overconfidence issue; only a tactical-grade figure
   (7.0 → 3.3 m outage drift) exists, itself pre-M4-session. No claim should assert a specific quantitative
   CAI benefit.
7. **Jam-family detector head (dependent claim 19's jamming-derived features).** Originally trained on only 8
   positive epochs (M1 limitation #2); rebalanced in D-055 (jam AUC 0.996/0.988/0.997) but this is a
   single-node, tuning-seed result, not yet confirmed at fleet/FL scale.
8. **Signature-strength / minimum operating envelope (safety principle, D-055).** The system's protective
   claims are conditioned on GNSS attack signature strength s ≳ 0.5; below that (s < 0.5) the same mechanisms
   can make outcomes catastrophically worse (2360 m vs 108 m undefended, D-055). **Any claim to "improved
   navigation accuracy under attack" must be scoped to this operating envelope**, and the failure mode itself
   may need to be disclosed (37 CFR 1.56 duty of candor) rather than omitted.

9. **Shadow probe and consistency-gated reacquisition (claims 21, 22; D-066, D-069, D-071).** Thresholds
   were calibrated on clean tuning seeds (510–529) in simulation and frozen; detection power at the frozen
   bounds is partial on MEMS (sub-50 m consistency-matched spoofs pass). No held-out test-seed result exists.
   The rev. 1 finding that the partial-trust probe dragged the state onto a persisting spoof (D-065/D-066) is
   itself a candour item for the specification.
10. **Trust split (claims 23, 24, 26; D-063, D-072).** Implemented and unit-tested, but the D-072 combined
    re-verification has NOT run (it waits for detector v3 on the frozen core); D-072 states that under
    meaconing the trained detector still depresses the position trust value, and that whether the split
    recovers position accuracy is "measured, not assumed". The displaced-meaconer variant needed to exercise a
    position-affecting meaconer is not available in the scenario set (TRUST_SPLIT_DESIGN §7). No performance
    claim for the split can be made.
11. **E_s independence for the CLOCK evidence (extends item 3).** TRUST_SPLIT_DESIGN §6 requires its own
    validation pass for the clock evidence; not done. Also confirm the F10 gap (claim 24) before relying on
    "normalised over the elapsed time".
12. **All rev. 2 evidence is on simulated data, MEMS/tactical grades, tuning seeds only.** Test seeds
    (10000+) untouched.

### Elements at risk given the prior art

- **G²FL (Liu 2026)** is explicitly a robust-FL-for-GNSS-spoofing scheme. **Claim 1's server/aggregator
  limb in isolation (clip + trimmed-mean/median + reputation, for GNSS spoofing detection) is the
  highest-risk element** — it may not be separately patentable over G²FL without the specific reputation
  formulation (EWMA of cosine similarity, dependent claim 13) and, more importantly, the tight closed-loop
  coupling to the continuous trust law and CAI bias-observation architecture recited in claim 1 as a whole.
  Counsel should obtain and review G²FL's actual claims (not just the abstract) before finalizing claim scope.
- **Khan 2025 / Chai 2025** already disclose FL for GNSS-spoofing detection generally; the differentiation
  here rests on the *specific* aggregation robustness combination and, more heavily, on the trust-law and
  quantum-fusion elements, not on "FL for spoofing detection" as such.
- **Pardhasaradhi 2022 / Chen 2025 / Wang 2025** (detect-then-switch class) make the continuous
  trust/covariance-inflation mechanism (vs. binary switching) the key differentiator for claims 1(vi)/2; this
  differentiation is strong on the verified abstracts but full-text review is recommended (D-013/D-044 note
  several full texts were not retrieved, e.g. Pardhasaradhi 2022).
- **Lautier 2014 / Cheiney 2018** already disclose cold-atom/classical accelerometer hybridization as a
  general sensor-fusion concept; the claimed novelty must rest on using that hybridization specifically as a
  bias observation inside a GNSS-attack-robust navigation filter with FL-trained trust gating, not on
  hybridization per se — claim drafting should ensure claim 1(iv) is not read as covering hybridization in
  the abstract.

---

---

## 5A. Claim-vs-frozen-code audit (tag `core-freeze-1`, commit a7c8bf0) — flags

"OK" means: the element is present in the frozen code as read by the PATENT-2 agent (source reading only;
the test suite was not run and no behaviour was measured). Line numbers are approximate.

| Claim | Status | Note |
|---|---|---|
| 1(i)–(iii) sensors | OK | not re-audited beyond existing code layout |
| 1(iv) CAI as direct bias observation | OK | `fusion/eskf.py::innovations` quantum branch ~L362–398; unchanged by D-063–072 |
| 1(v) classifier from innovation features | OK | `trust/detector.py`, `trust/features.py` |
| 1(vi) continuous trust + inflation | OK (with note) | `R_eff = R/max(w,w_min)`, but hard skip below `w_excl` = 0.05 (eskf ~L417) not recited |
| 1(vi) probe: partial-trust covariance | **F1: NOT IMPLEMENTED** | `w_probe` = 0.3 is still set in the law but the ESKF applies NO GNSS update in the probe (D-066 shadow probe). Claim reworded (D2) |
| 1(vi) "trust value below a distrust threshold" for T_ex | **F2: MISMATCH** | timer runs on the DISTRUST state (hysteresis flag D). Reworded (D3) |
| 1(vi) consistency condition + no physical evidence | OK | mean shadow NIS ≤ bound over `T_probe` and no clk/xsat/cn0 evidence (`clk` veto applies only to the clock law after D-072; the position law's probe veto is xsat/cn0 only) |
| 1(vii)/2 reputation-weighted aggregation | **F3: NOT IMPLEMENTED as weighting** | reputation gates quarantine only. Claim reworded (D4) |
| 1(vii) clip + trimmed mean/median | OK | `fl/aggregator.py` ~L104–129: clip at `clip_c` × median norm; trimmed mean if ≥5 live nodes else median. NB: clip is relative to the median norm, not an absolute bound ("bounded norm" is satisfied only relative to the round) |
| 2 (method) | follows 1 | reworded in parallel |
| 3 (medium) | OK | |
| 4 soft gate | **F4: MISWORDED** | gate is a filter correction feature, not evidence. Reworded. Mechanism itself OK (eskf ~L421–435) |
| 5 jump test | **F5: PARTLY MISWORDED** | baseline is the filter's pre-correction estimate, not pure-IMU; superseded in probe. Reworded |
| 6 xsat C/N0 correlation | OK | `features.py` x14, `_physical_spoof_evidence` xsat_event (running mean + 1.96 σ, floored) |
| 7 per-head Platt | OK | `trust/detector.py` ~L124–181 |
| 8 class-weight cap | OK | `detector.py` ~L261 cap 10× (plus 50 %-positive sampling cap, ~L194) |
| 9 init from latest aggregate | OK (not deeply checked) | `fl/client.py::install_global`; `fl/orchestrator.py` ~L158–166 cold-start test |
| 10 jamming does not block recovery | OK (not deeply checked) | probe veto uses only upward C/N0 excess/xsat/clk evidence, not C/N0 loss |
| 11 world model / Schuler | not re-audited | TRUST_SPLIT_DESIGN §6: unchanged |
| 12 clock-bias jump | **F6: MISWORDED and semantically changed** | receiver clock bias/drift, not a filter state; no longer part of position-law evidence. Reworded; basis for 23–24 |
| 13 EWMA cosine reputation; newcomers | OK (partly) | EWMA ρ = 0.8 of max(0, cos); newcomers: tighter clip (1× median) for `probation_rounds` = 2, not "reduced influence" via weight — wording acceptable but attorney to check |
| 14 reacquisition cap | scoped; OK | position law, now conditional on claim 22 |
| 15 suppression window | scoped; OK | position law; clock law has own suppression (F8) |
| 16 CAI at cycle time | not re-audited | unchanged |
| 17 asymmetric rates | OK | `tau_d` = 0.5 s vs `tau_r` = 10 s |
| 18 median if few nodes | OK | median if `n_live < 5` (aggregator ~L123–129) |
| 19 features | OK | RAIM x3, AGC x7, nsat delta x11, C/N0 rate x6 |
| 20 divergence event via NEES | **F7: UNSUPPORTED / MISWORDED** | eval-only metric; no node-side reporting found. See note at claim 20 |
| 21–26 (new) | supported by code as cited | flags F9 (claim 22 `es_pos` near-vacuous at the tested epoch), F10 (claim 24 possible Δt gap on the invalid-fix path — verify), F11 (claim 26 clock "probe" is not a shadow innovation) |

**Other observations for the Master (not claim changes):**
- F12: `TrustLawConfig.T_probe` etc. and `probe_nis_bound` per-grade values are configuration, applied by
  `node/methods.py`; the claims recite calibration "per grade" — supported only through that table (two grades).
- F13: the doc header of rev. 1 said "dependent claims 12–20" while the section held 4–20 — fixed.
- The claim skeleton's date-stamped statements about D-058 (§5 items 3–4) are historical; D-063 accepted the
  jam-recovery/gap-reset fix, and D-057/D-058 "must re-verify" items still await the post-freeze
  re-verification (D-072 steps 3–6).

## 6. Disclaimer

This document is an **engineering draft** prepared to organize the technical disclosure and candidate claim
language for the FedQPNT system. It is **not legal advice** and has **not been reviewed by a registered
patent attorney or patent agent**. Claim scope, statutory subject-matter eligibility (including under 35
U.S.C. §101 for software/algorithmic claims), best-mode and enablement sufficiency, the prior-art map's
completeness (several full texts were not accessible to the drafting agents per docs/REFERENCES.md and the
D-044 addendum — only verified abstracts/metadata were used), and the experimental-evidence gaps in §5 must
all be reviewed and resolved with qualified patent counsel before any filing. No claim in this document should
be treated as final, and no performance figures should be understood as validated results suitable for
supporting a claim of criticality or unexpected results absent the confirmations listed in §5.
