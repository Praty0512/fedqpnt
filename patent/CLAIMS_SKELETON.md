# FedQPNT — Patent Claim Skeleton (engineering draft)

_Author: PATENT agent · 2026-09-29 · against DECISION_LOG.md up to D-058, PROJECT_STATE.md (M1 signed off; M2 in
progress; M4 gated), docs/specs/ARCHITECTURE.md, docs/specs/TRUST_DESIGN_V2.md, docs/REFERENCES.md +
REFERENCES_ADDENDUM_D044.md._

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
exclusion time the node is forced into a low-trust "probe" state rather than left excluded indefinitely, and
recovery back to full trust is conditioned jointly on the consistency of the resulting GNSS innovations
(a statistical test) and on the absence of independent physical spoofing evidence (signal- and
kinematics-domain rules), decoupled from the trust law's own state so the evidence cannot be self-triggered
by the exclusion dynamics. Third, the CAI is fused not as an independent navigation aid but as a direct
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
   trust value remaining below a distrust threshold for longer than a maximum exclusion duration, transition
   the navigation node from a distrust state to a probe state in which the measurement-noise covariance is
   set to a partial-trust value independent of the calibrated probability; and responsive to an innovation
   consistency condition being satisfied during the probe state and to an absence of physical attack evidence
   determined independently of the trust value, transition the navigation node to a trust state; and
   (vii) a federated-learning client configured to train a local update to parameters of the trained
   classifier using data local to the navigation node and to transmit the local update, without transmitting
   raw sensor data, the navigation fix, or the navigation state, to a server; and
   a server communicatively coupled to the plurality of navigation nodes, the server comprising an aggregator
   configured to receive a plurality of local updates from the plurality of navigation nodes and to compute
   an aggregated update by: clipping each local update of the plurality of local updates to a bounded norm;
   computing a coordinate-wise trimmed-mean or coordinate-wise median of the clipped local updates; and
   weighting each navigation node's contribution to the aggregated update by a reputation score computed for
   that navigation node from a similarity between that navigation node's local update and the aggregated
   update over a preceding plurality of rounds; and to transmit the aggregated update to the plurality of
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
   responsive to the continuous trust value remaining below a distrust threshold for longer than a maximum
   exclusion duration, entering a probe state in which the measurement-noise covariance is set to a
   partial-trust value independent of the calibrated probability;
   during the probe state, evaluating an innovation consistency condition and evaluating, independently of the
   continuous trust value, whether physical attack evidence is present;
   responsive to the innovation consistency condition being satisfied and the physical attack evidence being
   absent, exiting the probe state to a trust state; responsive otherwise, returning to a distrust state;
   training a local update to parameters of the classifier using data local to the navigation node; and
   transmitting the local update, without transmitting raw sensor data, the navigation fix, or the navigation
   state, to a server that computes an aggregated update by clipping each of a plurality of local updates
   received from the plurality of navigation nodes to a bounded norm, computing a coordinate-wise
   trimmed-mean or median of the clipped local updates, weighting each navigation node's contribution by a
   reputation score derived from consistency of that navigation node's local updates with the aggregated
   update over time, and transmitting the aggregated update back to the plurality of navigation nodes.

### Claim 3 (Non-transitory computer-readable medium)

3. A non-transitory computer-readable medium storing instructions that, when executed by one or more
   processors of a navigation node comprising an inertial measurement unit, a cold-atom interferometric
   accelerometer, and a global-navigation-satellite-system receiver, cause the one or more processors to
   perform the method of claim 2.

---

## 4. Dependent claims (12–20)

Each attaches to Claim 1 (system) with a corresponding method-claim (Claim 2) analogue implied.

4. The system of claim 1, wherein the trust engine is configured to determine the physical attack evidence
   using a soft covariance-scaling gate that, responsive to a normalized innovation statistic of the
   navigation fix exceeding a chi-squared threshold, scales the measurement-noise covariance so that the
   scaled normalized innovation statistic equals the chi-squared threshold, rather than excluding the
   navigation fix.

5. The system of claim 1, wherein the physical attack evidence comprises a result of a short-baseline jump
   test comparing a change in position derived from the navigation fix over a preceding time interval against
   a change in position derived by propagating the navigation state over the same time interval using the
   inertial measurement unit, evaluated independently of the trust value or the trust engine's state history.

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

12. The system of claim 1, wherein the fusion filter comprises a clock-bias and clock-drift state estimated
    jointly with the navigation state, and wherein the physical attack evidence comprises a jump in the
    clock-bias state exceeding a threshold expressed as a multiple of a standard deviation.

13. The system of claim 1, wherein the reputation score for a given navigation node is computed as an
    exponentially-weighted moving average of a cosine similarity between that navigation node's local update
    and the aggregated update, and wherein the aggregator is configured to reduce the influence of a
    newly-joined navigation node's local update for an initial plurality of rounds.

14. The system of claim 1, wherein responsive to the global-navigation-satellite-system receiver producing a
    first valid navigation fix after an outage exceeding a predetermined duration, the trust engine is
    configured to cap the trust value at a reacquisition ceiling below full trust, independent of the
    calibrated probability.

15. The system of claim 1, wherein the trust engine is configured to suppress use of the calibrated
    probability for a predetermined suppression duration after transitioning from the probe state to the
    trust state, such that the trust value during the suppression duration is governed by the physical attack
    evidence rather than by the calibrated probability.

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

20. The method of claim 2, further comprising evaluating, over the preceding time interval, a
    innovation-normalized-error-squared statistic of the navigation state against a chi-squared bound, and
    reporting a divergence event responsive to the statistic exceeding the chi-squared bound for longer than a
    predetermined duration.

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
