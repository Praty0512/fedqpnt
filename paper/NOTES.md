# NOTES.md — Claim → Evidence map for main.tex Sections II (Related Work) and III (System and Threat Model)

Format: sentence/claim (paraphrased) → source (reference key from refs.bib, or project file / decision ID).
Every factual sentence in II and III is covered below in document order.

## Section II. Related Work

### II.A FL for GNSS security
- "Khan et al. localize via dead-reckoning signals, compare to GNSS, aggregate weights at an RSU, train a global SVM via FL, ~99% accuracy on CARLA." → `khan2025enhancing`; docs/specs/raw/REFERENCES_VERIFIED.md item 3/15.
- "Chai et al. use FL to identify spoofing and jamming signals for UAVs." → `chai2025navigation`; REFERENCES_VERIFIED.md item 4.
- "Namagembe et al. propose ML-based GPS spoofing detection/mitigation for UAVs." → `namagembe2026machine`; docs/REFERENCES.md #5.
- "Zhou et al. propose spatial-temporal federated transfer learning with multi-sensor fusion for cooperative positioning; targets heterogeneous-distribution positioning, not adversarial spoofing." → `zhou2023spatiotemporal`; REFERENCES_VERIFIED.md item 1 (Candidate B, "BEST MATCH").
- "G²FL provides robust FL for GNSS spoofing detection under Byzantine/poisoned clients." → `liu2026g2fl`; REFERENCES_VERIFIED.md "New related-work items".
- "None of this group couples the detector to a continuous trust weight; none uses a physical quantum sensor." → DECISION_LOG.md D-013 ("no verified prior work implements FL together with physical-quantum-sensor models"); ARCHITECTURE.md §5 baseline table (Baseline A = fixed/binary trust).
- "TRIM-NB-R differs from G²FL in aggregation detail; central departure is architectural (continuous trust law, not exclude decision)." → ARCHITECTURE.md §4.5 (TRIM-NB-R spec) and §5 (Baseline A row: "fixed... memoryless detect-and-exclude").

### II.B Adaptive and fault-tolerant fusion and trust
- "Mehra introduced innovation-based adaptive Kalman estimation, root of B′." → `mehra1970identification`; DECISION_LOG D-013 row 6 ("replaced by Mehra 1970 ... the root of B′").
- "Carlson's federated filter: local filters + master filter, classical single-platform sense of 'federated'." → `carlson1988federated`, `carlson1990federated`; DECISION_LOG D-013 row 2.
- "Ren et al. adaptive fusion of camera/GNSS/IMU for autonomous driving; used as B-cont representative." → `ren2020adaptive`; ARCHITECTURE.md §5 note block ("B-cont: adaptive-fusion class, Ren 2020").
- "Pardhasaradhi & Cenkeramaddi: GPS spoofing detection via distributed radar tracking, switch to radar track on detection (detect-and-switch); used as B-bin representative." → `pardhasaradhi2022gps`; REFERENCES_VERIFIED.md item 7; ARCHITECTURE.md §5 ("B-bin: Pardhasaradhi 2022 class").
- "Negru et al. 2024 Sensors: local EKFs feeding a GRU master filter; classical federated-filter architecture, NOT federated learning across clients despite the title." → `negru2024resilient`; REFERENCES_VERIFIED.md item 2; DECISION_LOG D-013 row 2 ("Correction to proposal... NOT federated learning... classical federated-filter (multi-sensor Kalman fusion) sense").
- "Companion paper: UWB-aided hybrid navigation in degraded GNSS." → `negru2024uwb`; REFERENCES_VERIFIED.md "New related-work items".
- "None of this group's mechanisms is trained/shared by FL across a fleet, none uses a physical quantum sensor." → DECISION_LOG D-013 gap-impact note.

### II.C Quantum inertial sensing for navigation
- "Wright et al. review cold-atom inertial sensors for navigation: principle, sensitivities, dead-time/dynamic-range/SWaP challenges." → `wright2022cold`; docs/REFERENCES.md #16.
- "d'Armagnac de Castanet et al.: 3-axis hybrid cold-87Rb atom interferometer at arbitrary orientation/rotation rate; per-shot Raman residuals at several T; measured contrast-vs-rotation law in rigid and inertial-pointing modes." → `darmagnac2024atom`; docs/REAL_DATA_JARLAUD2024.md (Dataset structure; Contrast loss vs rotation rate sections).
- "We use this dataset to calibrate noise density, per-T scaling, and a Gilbert-Elliott bursty-outlier channel." → docs/REAL_DATA_JARLAUD2024.md §"Quantum-sensor (atom interferometer) calibration"; DECISION_LOG D-014/D-015/D-019/D-020/D-021.
- "Neither addresses fleet-wide learning or GNSS attack robustness; foundation not a navigation-security contribution itself." → author synthesis, consistent with both papers' stated scope (REFERENCES_VERIFIED.md has no FL/attack claim for either).

### II.D Quantum FL (distinguished from quantum sensing)
- "Hazarika et al.: quantum-enhanced FL for metaverse-empowered vehicular networks; quantum-enhanced computation, not a physical sensor." → `hazarika2025quantum`; DECISION_LOG D-013 row 11 ("quantum-enhanced FL (computation), not quantum sensing"); REFERENCES_VERIFIED.md item 11.
- "Chehimi et al. 2023: foundations of QFL over classical/quantum networks." → `chehimi2023foundations`; REFERENCES_VERIFIED.md item 8 ("Foundations of Quantum Federated Learning...").
- "Related paper, QFL with quantum data (Chehimi & Saad, ICASSP 2022)." → `chehimi2022quantum`; REFERENCES_VERIFIED.md item 8 candidate list.
- "None of this group involves a physical quantum sensor or targets GNSS spoofing/jamming." → DECISION_LOG D-013 row 8 ("none of the three does GNSS clock synchronization or positioning... quantum-network/temporal-data FL papers").

### II.E GNSS spoofing/jamming signatures
- "Psiaki & Humphreys: foundational survey, capture-and-carry-off dynamics, reacquisition vulnerability." → `psiaki2016gnss`; docs/GNSS_AND_ATTACKS.md "Literature grounding" (Spoofing, Abrupt spoofing, Combined jam-then-spoof sections).
- "Humphreys et al. 2008: assesses practical spoofing threat/feasibility." → `humphreys2008assessing`; docs/GNSS_AND_ATTACKS.md "Literature grounding" (Spoofing section).
- "Radoš et al.: field-measured cross-satellite C/N0 correlation collapse (−0.76 clean → 0.99 spoofed) under single-antenna spoofing." → `rados2024recent`; docs/GNSS_AND_ATTACKS.md "Single-antenna C/N0 correlation" and "Cross-check against literature" sections; DECISION_LOG D-018.
- "Borhani-Darian et al.: deep-learning detector on the cross-ambiguity function (correlation domain), complementary to raw-observable level." → `borhanidarian2024detecting`; docs/GNSS_AND_ATTACKS.md "Cross-check against literature — Borhani-Darian et al. 2024"; DECISION_LOG D-013 row 13 (citation correction from wrong Ad Hoc Networks DOI).
- "Tariq & Ahanger: multi-model fusion (Kalman + ensemble ML + transformer) for BeiDou spoofing in UAV swarms; ~99% detection accuracy, >97% mission success (not detection accuracy); per-model ensembling, not explicit consensus." → `tariq2026multimodel`; DECISION_LOG D-013 row 9; REFERENCES_VERIFIED.md item 9.
- "This group establishes attack signatures motivating our attack simulator/detector features." → docs/GNSS_AND_ATTACKS.md throughout (Attack scenarios, Attack signature validation sections).

### Table II (comparison table)
Every cell is sourced as follows:
- Khan 2025 row: FL=Yes (khan2025enhancing abstract, RSU-aggregated SVM), Quantum=No, Adaptive trust=No ("binary exclude" — REFERENCES_VERIFIED item 3/15 notes post-detection action unstated in abstract but Baseline A framing in ARCHITECTURE §5 treats class as memoryless exclude), Attack-tested=Yes (GPS spoofing, per title).
- Chai 2025 row: FL=Yes, Quantum=No, Adaptive trust=No (classification only, per title "Identification"), Attack-tested=Yes (spoofing/jamming, per title).
- G²FL row: FL=Yes(robust) (title), Quantum=No, Adaptive trust=No (REFERENCES_VERIFIED "New related-work items" — no trust-law claim), Attack-tested=Yes (spoofing, Byzantine clients per title/topic).
- Negru 2024 row: FL=No (classical federated filter) (DECISION_LOG D-013 row 2 correction), Quantum=No, Adaptive trust=Continuous (GRU master filter combines EKF outputs continuously — REFERENCES_VERIFIED item 2 "local filters ... GRU block"), Attack-tested=No (degraded GNSS conditions tested, not adversarial per REFERENCES_VERIFIED item 2 abstract).
- Pardhasaradhi 2022 row: FL=No, Quantum=No, Adaptive trust=No (detect-and-switch to independent radar — REFERENCES_VERIFIED item 7 "detect-then-switch... not continuous... weighting"), Attack-tested=Yes (GPS spoofing, title).
- Hazarika 2025 row: FL=Yes, Quantum=No (quantum-enhanced compute — DECISION_LOG D-013 row 11), Adaptive trust=No, Attack-tested=No (vehicular metaverse trajectory context, no spoofing claim in REFERENCES_VERIFIED item 11).
- Chehimi 2023 row: FL=Yes (quantum FL), Quantum=No, Adaptive trust=No, Attack-tested=No (REFERENCES_VERIFIED item 8 — networking/learning framework only).
- Tariq 2026 row: FL=No (multi-model fusion, not FL — REFERENCES_VERIFIED item 9), Quantum=No, Adaptive trust=Partial (model ensembling per REFERENCES_VERIFIED item 9), Attack-tested=Yes (BeiDou spoofing).
- FedQPNT row: all four Yes, sourced from ARCHITECTURE.md §2 (fusion), §3 (trust), §4 (FL), and docs/REAL_DATA_JARLAUD2024.md (real-data-calibrated quantum sensor).

## Section III. System and Threat Model

### III.A Node model
- "Fleet of N independent nodes, same code path." → PROJECT_STATE.md "Identity"; ARCHITECTURE.md §1.1 module map.
- "Environment half / Agent half split; only sensor outputs cross; TruthState/AttackLabel/GnssEpoch.meta never cross." → ARCHITECTURE.md §0 ("Node boundary"), §1.3 (per-tick dataflow), §4.4 (leakage guards, AST scan).
- "100 Hz global tick; per-tick sequence (truth→sensors→attack→receiver→filter→features→detector→trust→correction→pseudo-label/FL buffer)." → ARCHITECTURE.md §1.2 (rates table), §1.3 (per-tick sequence diagram).
- "Nodes exchange only FL model updates on a fixed round schedule; navigation never blocks on model availability." → ARCHITECTURE.md §1.4 ("Missing global model... node keeps its last detector. Navigation never waits on comms"), §4.2 (round schedule), §8 (node blocks only at round boundary for the reply, not for navigation).

### III.B Sensors
- "15-state loosely-coupled error-state Kalman filter: position, velocity, attitude error, accel bias, gyro bias." → ARCHITECTURE.md §2.2 (state definition).
- "IMU: MEMS or tactical grade, reported separately, differ by ~order of magnitude in free-inertial error growth." → ARCHITECTURE.md §2.5 ("CAI benefit expected small for MEMS and significant for tactical"); DECISION_LOG D-009 (Architect's risk note), PROJECT_STATE.md R-6.
- "GNSS receiver: WLS+RAIM PVT from pseudorange/Doppler/C-N0/AGC." → docs/GNSS_AND_ATTACKS.md "Receiver architecture (WLS + RAIM)" table.
- "CAI hybridized with classical accel via bias-observation residual; gravity/attitude/trajectory cancel." → ARCHITECTURE.md §2.5 ("Cold-atom hybridisation" block, "Key property" bullet).
- "CAI noise calibrated from real data: 2T=20ms, σ_shot≈5.6µg (within 11% of paper-implied), Gilbert-Elliott channel, 9.0% outlier rate, 66% burst persistence." → docs/REAL_DATA_JARLAUD2024.md "Per-2T robust statistics", "Outlier process" sections; DECISION_LOG D-015, D-019.
- "CAI keeps valid=True during a burst — silently wrong." → docs/REAL_DATA_JARLAUD2024.md "Replay usage (D-019)"; DECISION_LOG D-019.

### III.C Attacker capabilities and limits
- "Attacker acts only on GNSS, at raw-observable level; never IMU/quantum/comms in reported scenarios." → DECISION_LOG D-004 (raw-observable level); ARCHITECTURE.md §11 note ("No attack in v1 targets the IMU", §3.4).
- "Five attack families: gradual spoof, meaconing, abrupt spoof, CW/wideband jamming, combined jam-then-spoof." → docs/GNSS_AND_ATTACKS.md "Attack scenarios" section (all subsections).
- "Gradual spoof: power-advantage capture then smooth drag, RAIM-blind." → docs/GNSS_AND_ATTACKS.md "Spoofing (drift-in carry-off)"; "RAIM under drift-in spoofing" (KS p=0.99).
- "Meaconing: common-mode delay/clock shift, small C/N0 rise." → docs/GNSS_AND_ATTACKS.md "Meaconing" section.
- "Abrupt spoofing: lock-loss, reacquisition delay, discontinuous jump." → docs/GNSS_AND_ATTACKS.md "Abrupt (non-aligned) spoofing" section.
- "Jamming: raises noise floor, reduces locked satellites." → docs/GNSS_AND_ATTACKS.md "Jamming: CW" and "Jamming: wideband/chirp" sections.
- "Combined jam-then-spoof: denial then capture at reacquisition, the classic vulnerable window." → docs/GNSS_AND_ATTACKS.md "Combined jam-then-spoof"; `psiaki2016gnss` citation there; ARCHITECTURE.md §1.4 (reacquisition cap rule, citing Psiaki & Humphreys 2016).
- "Single-antenna spoofer common-mode C/N0 signature modelled, following Radoš et al." → docs/GNSS_AND_ATTACKS.md "Single-antenna C/N0 correlation (D-018 item 2)"; DECISION_LOG D-018.
- "Signature not itself exposed as a hand-crafted detector feature by the attack layer." → DECISION_LOG D-018 ("Expose no new detector feature in the attack layer; the FUSION+TRUST detector computes its own features").
- "FL threat surface: fraction f Byzantine nodes, sign-flip/Gaussian/label-flip/ALIE; self-reported n untrusted." → ARCHITECTURE.md §4.5 (Aggregators, attack list), §4.1 ("ModelUpdate.n_samples is self-reported... FedAvg does weight by it").

### III.D What never leaves a node
- "Only object crossing to server: ModelUpdate — detector delta (882 params, ~3.5kB), norm stats, scalar metrics." → ARCHITECTURE.md §3.2 (882 parameters, ~3.5 kB), §4.1 (table of shared items).
- "Server never receives ground truth, position, velocity, raw features." → ARCHITECTURE.md §4.4 (leakage guards); §0 (node boundary).
- "Trust-law hyperparameters and fusion filter fixed, identical across methods, tuned once on disjoint tuning seeds before test seeds." → ARCHITECTURE.md §4.1 ("Trust-law hyper-parameters... not learned in v1... fixed, identical across methods"); §7.6 tuning discipline (item 6 in Statistical protocol, §7).

## Uncited-but-relevant items flagged for Master (not used in main.tex per the citation hard rule)
- FedAvg (McMahan et al. 2017), FedProx (Li et al. 2020), trimmed-mean (Yin et al. 2018), norm-clipping (Sun et al. 2019), ALIE (Baruch et al. 2019), Krum (Blanchard et al. 2017), FLTrust (Cao et al. 2021), FedAsync staleness (Xie et al. 2019), CUSUM (Page 1954), reset Jacobian (Solà 2017), Wilcoxon (1945), Holm (1979), Demšar (2006), Anderson & Moore (1979), Lautier (2014), Cheiney (2018), Templier (2022), Wang (2021), Klobuchar (1987), Saastamoinen (1972), Vig (1992), Parkinson & Axelrad (1988) — all appear in ARCHITECTURE.md/GNSS_AND_ATTACKS.md as method citations but are **not** in docs/REFERENCES.md, so they are described in main.tex only by mechanism name, without a `\cite`, per the HARD RULE restricting citations to docs/REFERENCES.md.
