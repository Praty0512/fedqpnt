# Verified Bibliography (WP-10.0)

_Author: REF-VERIFY agent · 2026-09-23. Sources: Crossref API (`api.crossref.org/works`), OpenAlex API
(`api.openalex.org/works`), doi.org resolution. IEEE/Wiley/ResearchGate direct pages still return HTTP 403
to WebFetch (confirmed again this pass) so all IEEE/Wiley items below are metadata- and abstract-verified
via Crossref/OpenAlex, not the publisher's own rendered page. OpenAlex abstracts are reconstructed from an
inverted index; quoted phrases are taken from that reconstruction. Nothing below is invented — any field
Crossref/OpenAlex did not supply is marked UNVERIFIED._

---

## 1. Zhou et al. 2023 — MISMATCH (wrong paper cited; a better-fitting alternative exists)

**Candidate A — "MVMAFOL" (the user-supplied title):**
- Zhou, J., Zheng, J., Cao, B., Wu, W. "MVMAFOL: A Multi-Access Three-Layer Federated Online Learning
  Algorithm for Internet of Vehicles." 2023 International Joint Conference on Neural Networks (IJCNN),
  2023. DOI: 10.1109/IJCNN54540.2023.10191843. [Crossref, OpenAlex]
- **What it actually does:** three-layer federated **online learning** for IoV **traffic/resource
  allocation** — vehicles train per-region models (not one global model) and aggregate across edge/cloud
  servers because "different regions may have different distribution" of traffic data. It is NOT about
  cooperative multi-vehicle **positioning**. [OpenAlex abstract]
- **Verdict on this candidate: MISMATCH.** Exists, three-layer/federated/IoV terms match, but the content
  (online learning for traffic-model aggregation) does not match the proposal's description (three-layer
  federated transfer learning for cooperative multi-vehicle positioning).

**Candidate B — "Spatial–Temporal Federated Transfer Learning with multi-sensor data fusion for
cooperative positioning":**
- Zhou, X., Yang, Q., Liu, Q., Liang, W., Wang, K., Liu, Z., Ma, J., Jin, Q. "Spatial–Temporal Federated
  Transfer Learning with multi-sensor data fusion for cooperative positioning." *Information Fusion*,
  2024 (published online 2023). DOI: 10.1016/j.inffus.2023.102182. [Crossref; OpenAlex confirms title,
  authors, topic tag "Indoor and Outdoor Localization Technologies"; full abstract text not returned by
  OpenAlex (`abstract_inverted_index` null) — topical match is from title/keywords, not a quoted abstract]
- **Verdict on this candidate: BEST MATCH for the proposal's description.** Title itself names federated
  transfer learning + multi-sensor fusion + cooperative positioning — directly matches what the proposal
  describes, unlike MVMAFOL.
- **Recommendation:** cite Zhou et al., *Information Fusion* (DOI 10.1016/j.inffus.2023.102182) in place of
  MVMAFOL for the "three-layer federated transfer learning for cooperative multi-vehicle positioning"
  claim. Flag to Master: the proposal's reference-list entry currently points to the wrong Zhou paper.

---

## 2. Negru et al. 2024 — VERIFIED (exists), MISMATCH on FL framing (important correction)

- Negru, S. A., Geragersian, P., Petrunin, I., Guo, W. "Resilient Multi-Sensor UAV Navigation with a
  Hybrid Federated Fusion Architecture." *Sensors*, 24(3):981, 2024. DOI: 10.3390/s24030981.
  [Crossref, OpenAlex abstract]
- **What it actually does:** integrates GNSS, IMU, monocular camera, and barometer using **local Extended
  Kalman Filters (EKFs) feeding a GRU-based master filter** — i.e., a **classical federated Kalman-filter
  architecture** (Carlson-style local/master filter structure, with a learned GRU master filter), tested
  in AirSim + Spirent GSS7000 hardware simulation, achieving 0.54 m 95th-percentile error in degraded
  conditions vs. 1.72 m nominal. [OpenAlex abstract: "local filters are implemented using EKFs ... while a
  master filter is used in the form of a GRU block"]
- **Correction to proposal:** "federated fusion" here is **NOT federated learning** across distributed
  clients/vehicles — it is the classical federated-filter (multi-sensor Kalman fusion) sense of the term,
  with one machine-learning component (GRU master filter) inside a single UAV. **This changes how we may
  cite it**: use as classical/hybrid multi-sensor fusion architecture literature (relevant to our own
  GNSS/IMU/CAI fusion design), not as FL-across-agents literature. Do not group it with the
  Khan/Chai/G²FL-style federated-learning-for-spoofing-detection citations.

---

## 3 / 15. Khan et al. 2025 — VERIFIED

- Khan, M. M., Kamal, M., Shabbir, M., Alahmari, S. "Enhancing Autonomous Vehicle Security: Federated
  Learning for Detecting GPS Spoofing Attack." *Transactions on Emerging Telecommunications Technologies*,
  36(4):e70138, 2025. DOI: 10.1002/ett.70138 (online 16 Apr 2025). [Crossref, OpenAlex full abstract]
- **What it does:** each vehicle localizes itself from yaw-rate/steering-angle/wheel-speed
  (dead-reckoning-style) sensors, compares against GNSS; the resulting localization mismatch is used to
  compute weights aggregated at a **Roadside Unit (RSU)**, where a global **SVM** classifier is trained via
  FL. Reports 99% accuracy / 98% F1 / 99% AUC-ROC on CARLA-simulated trajectories, beating KNN/RF baselines.
- **Confirms and extends the baseline pass:** full author list now confirmed (Khan, Kamal, Shabbir,
  Alahmari). Detector is SVM at an RSU aggregator, not a peer-to-peer MLP classifier. **Still unresolved
  even with the full abstract:** what navigation-side action follows a spoof flag (exclude vs. fallback vs.
  alarm-only) — the abstract does not state it, so Baseline A's "memoryless exclude" framing remains
  unverified against this specific paper and should stay flagged as "our own simplification," per the
  baseline notes.

---

## 4. Chai et al. 2025 — VERIFIED (identification succeeded this pass; baseline pass had failed)

- Chai, Y., Liu, M., Li, M. "Navigation Spoofing and Jamming Signals Identification of UAV Based on
  Federated Learning." *IEEE Internet of Things Journal*, 2025. DOI: 10.1109/JIOT.2025.3588162.
  [Crossref]
- Title/topic match the proposal's description exactly (FL-based spoofing/jamming identification for UAVs).
  Abstract text was not independently pulled in this pass (Crossref bibliographic metadata only) — full
  extraction of detector type / aggregator / post-detection behaviour remains a follow-up if the exact
  fusion rule is needed for Baseline A justification.

---

## 5. Meng 2025 (adaptive multi-sensor fusion isolating a compromised sensor) — NOT FOUND

No paper by a first author "Meng," 2025, matching "adaptive multi-sensor fusion that isolates a
compromised sensor after detection" was located via Crossref or OpenAlex. Confirms the baseline pass's
failure to identify it. Up to 3 topically closest **candidates** found this pass (none proposed as the
actual match — surname does not match "Meng" except where noted, and none map exactly onto "isolate a
compromised sensor"):

1. Dai, Y., Park, S., Lee, K. "Adaptive Multi-Sensor Fusion for Robust Outdoor Localization and Path
   Tracking Under Weak GNSS Conditions." *Electronics*, 15(13):2768, 2026. DOI: 10.3390/electronics15132768.
   [Crossref] — adaptive fusion under weak/degraded GNSS, but not framed as sensor isolation, wrong year.
2. Foss, D. T. "Distributed Fault Detection and Isolation for Multi-Sensor Fusion Under Adversarial
   Corruption." SSRN preprint, 2026. DOI: 10.2139/ssrn.6196538. [Crossref] — closest conceptually
   (isolation of a corrupted sensor under adversarial conditions) but different author/year and unreviewed
   preprint.
3. (From the baseline pass, re-flagged, not independently re-confirmed here) "MARS: Defending UAVs from
   attacks on inertial sensors..." — H. Meng, 2025 — surname matches but topic is IMU
   anomaly/recovery, not GNSS trust fusion; too weak a fit per the baseline notes.

**Recommendation:** obtain the exact title/DOI from the proposal's own reference list; surname+year+topic
is insufficient in this crowded sub-literature.

---

## 6. Gu 2021 (fault-tolerant adaptive Kalman fusion, GNSS/INS) — NOT FOUND

No paper by a first author "Gu," 2021, on fault-tolerant adaptive Kalman fusion for GNSS/INS was located.
Confirms the baseline pass's failure. Up to 3 candidates (topical match only, none are "Gu" or 2021):

1. Gao, G., Li, G., Yi, Y., Zhong, Y. "An Adaptive Fault-Tolerant Federated Kalman Filter for a
   Multi-Sensor Integrated Navigation System." *Sensors*, 26(4):1360, 2026. DOI: 10.3390/s26041360.
   [Crossref] — closest topical match (adaptive + fault-tolerant + federated Kalman filter + multi-sensor
   nav), but wrong author and year by 5 years.
2. Ramezanifard, A., Salarieh, H. "Adaptive Federated Kalman Filter With Fault Detection for
   INS/GNSS/VC/SFC Integration." *IEEE Sensors Journal*, 2026. DOI: 10.1109/JSEN.2026.3652366. [Crossref]
   — same caveat (2026, different author).
3. Carlson, N. A. "Federated filter for fault-tolerant integrated navigation systems." *IEEE PLANS '88*,
   1988. DOI: 10.1109/PLANS.1988.195473. [Crossref] — the foundational/classical federated-filter paper;
   correct concept, wrong (much earlier) year and not "Gu."

**Recommendation:** same as item 5 — get the exact reference-list entry from the proposal.

---

## 7. Pardhasaradhi et al. 2022 — VERIFIED (DOI confirmed against Crossref; baseline caveats stand)

- Pardhasaradhi, B., Cenkeramaddi, L. R. "GPS Spoofing Detection and Mitigation for Drones Using
  Distributed Radar Tracking and Fusion." *IEEE Sensors Journal*, 22(11):11122–11134, 2022.
  DOI: 10.1109/JSEN.2022.3168940. [Crossref confirms title, authors, volume/issue/pages, DOI — resolves
  the baseline pass's "index-sourced, unconfirmed against primary page" caveat with an authoritative
  Crossref record]
- No other 2022 Pardhasaradhi paper on this topic was found; this remains the single best/only candidate.
- **Standing caveat (unchanged from baseline pass, still true — abstract not independently re-pulled this
  round):** the described mechanism (fuse ground-radar track, switch UAV control input to it) reads as a
  **detect-then-switch to an independent radar sensor**, not the proposal's "residual-based trust
  isolation" with continuously varying trust weight on the *same* GNSS/INS filter. Keep the baseline's
  recommendation: cite this paper only for the general "detect a compromised source → isolate it → keep
  navigating on the others" philosophy, not for continuous χ²-weighting mechanics.

---

## 8. Chehimi & Saad 2023 — MISMATCH (year and content; two real candidates, neither matches "clock
sync/positioning")

- Best author-pair match: Chehimi, M., Chen, S. Y.-C., Saad, W., Towsley, D., Debbah, M. "Foundations of
  Quantum Federated Learning Over Classical and Quantum Networks." *IEEE Network*, 2023 (online) /
  2024 (issue). DOI: 10.1109/MNET.2023.3327365. [Crossref] — a survey/foundations paper on QFL network
  architectures; general networking/learning framework, **not** clock synchronization or positioning.
- Also real, closer to "Chehimi & Saad" as sole authors: Chehimi, M., Saad, W. "Quantum Federated Learning
  with Quantum Data." *ICASSP 2022*. DOI: 10.1109/ICASSP43922.2022.9746622. [Crossref] — 2022, not 2023;
  about FL over quantum data generally, not clock sync/positioning either.
- Also real, most cited "FedQLSTM" work (likely what the proposal actually means by "Chehimi & Saad
  2023"): Chehimi, M., Chen, S. Y.-C., Saad, W., Yoo, S. "Federated Quantum Long Short-Term Memory
  (FedQLSTM)." *Quantum Machine Intelligence*, 2024. DOI: 10.1007/s42484-024-00174-z. [Crossref] —
  integrates QLSTM models for **temporal/sequential data** in a privacy-preserving distributed-learning
  setting; general time-series FL, not specifically clock-sync or positioning.
- **Verdict:** all three are real papers by Chehimi & Saad (+ coauthors) on quantum federated learning, but
  none is dated exactly 2023 with sole authorship "Chehimi & Saad," and **none of the three does GNSS clock
  synchronization or positioning** — they are quantum-network/temporal-data FL papers. The proposal's
  description ("clock sync/positioning") does not match any of them. **Recommend the Master supply the
  exact title** the proposal intended, or reframe the citation as "quantum FL over distributed quantum
  networks (general capability), not GNSS clock-sync-specific" and pick FedQLSTM (2024) as the closest
  concrete instantiation if a single citation is needed.

---

## 9. Tariq 2026 — MISMATCH (real paper exists; "consensus-based" and "~97% accuracy" don't match)

- Best candidate: Tariq, U., Ahanger, T. A. "Multi-model fusion for robust detection and resilient
  mitigation of BeiDou spoofing in decentralized UAV swarm systems." *PeerJ Computer Science*, 2026.
  DOI: 10.7717/peerj-cs.3875. [Crossref, OpenAlex abstract]
- **What it actually does:** integrates Kalman filtering + ensemble ML (XGBoost, Random Forest) +
  transformer-based detection across a **decentralized** UAV swarm — matches "decentralized... UAV swarms."
  But detection is via per-model fusion, **not an explicit consensus mechanism** ("does not mention
  decentralized consensus-based detection," per OpenAlex abstract). Reported figures: **~99% detection
  accuracy**, false-alarm rate <2%, mitigation within ~3 s, and mission success rate **>97%** — i.e., the
  "~97%" the proposal cites is the *mission success rate*, not detection accuracy.
- Two other 2026 Tariq papers on BeiDou/UAV-swarm spoofing exist but fit worse: "Mission-aware BeiDou
  spoofing defense in UAV swarms with LLM-assisted context validation" (Tariq & Shaukat, *Frontiers in
  Communications and Networks*, DOI 10.3389/frcmn.2026.1760543 — 98.1% accuracy, LLM-based not
  consensus-based) and "Tri-stream multi-model architecture for real-time detection of BeiDou signal
  manipulation in UAV swarms" (Tariq, Ahanger, Shaukat, *Scientific Reports*, DOI
  10.1038/s41598-026-46655-y — transformer+GNN+Kalman, no consensus mechanism either).
- **Recommendation:** cite PeerJ CS 10.7717/peerj-cs.3875 but correct the description — drop "consensus-based"
  (not supported) and correct "~97% accuracy" to "~99% detection accuracy / >97% mission success rate under
  active spoofing."

---

## 10. Kannamarlapudi 2025 — NOT FOUND

Zero results from both Crossref (`query.author=Kannamarlapudi`, 0 hits) and OpenAlex (topic + author
search, 0 hits) for any author surnamed Kannamarlapudi, in any year. No arXiv, dblp, or landing-page
alternative surfaced either. **This reference could not be verified to exist at all** — it may be a
non-indexed/predatory-venue item, a misspelled name, or a fabricated citation. **Recommend the Master
either supply the exact venue/DOI for manual lookup, or drop this citation** — do not include an unverified
"architectural proposal for quantum-AI sensor fusion" claim in the final paper without a resolvable source.

---

## 11. Hazarika 2025 — VERIFIED (close match, minor framing note)

- Hazarika, B., Singh, K., Dobre, O. A., Li, C.-P., Duong, T. Q. "Quantum-Enhanced Federated Learning for
  Metaverse-Empowered Vehicular Networks." *IEEE Transactions on Communications*, 2025 (online 2024).
  DOI: 10.1109/TCOMM.2024.3502667. [Crossref]
- Matches "quantum-enhanced FL for vehicular metaverse" precisely on authors/venue/topic. The proposal's
  narrower framing "...trajectory prediction" is plausible as one application within the paper but was not
  independently confirmed from a pulled abstract this pass (Crossref bibliographic record only) — flag as
  a minor unverified sub-claim, not a mismatch.
- A related, likely earlier/conference version by the same group also exists: "Quantum-Driven
  Context-Aware Federated Learning in Heterogeneous Vehicular Metaverse Ecosystem," Hazarika et al.,
  *ICC 2024*, DOI: 10.1109/ICC51166.2024.10623010 — useful as a companion citation if needed.

---

## 12. Radoš, Brkić & Begušić 2024 — VERIFIED exactly

- Radoš, K., Brkić, M., Begušić, D. "Recent Advances on Jamming and Spoofing Detection in GNSS."
  *Sensors*, 24(13):4210, 2024. DOI: 10.3390/s24134210. [Crossref] Matches the proposal's citation exactly
  on authors, venue, volume/issue/page, year.

---

## 13. Borhani-Darian et al. 2024 — MISMATCH (wrong venue/volume/article — citation appears mixed up
with a different paper)

- The proposal cites "Ad Hoc Networks 163:103597" for Borhani-Darian et al. 2024. **Crossref confirms that
  DOI/volume/article number (10.1016/j.adhoc.2024.103597, Vol. 163, Art. 103597) actually belongs to a
  different paper**: Korium, M. S., Saber, M., Ahmed, A. M., Narayanan, A., Nardelli, P. H. J.
  "Image-based intrusion detection system for GPS spoofing cyberattacks in unmanned aerial vehicles."
  *Ad Hoc Networks*, 163:103597, 2024. Borhani-Darian is **not** an author on this paper. [Crossref]
- Borhani-Darian's actual 2024 GNSS-spoofing deep-learning paper is a different one entirely: Borhani-Darian,
  P., Li, H., Wu, P., Closas, P. "Detecting GNSS spoofing using deep learning." *EURASIP Journal on
  Advances in Signal Processing*, 2024(1):14, 2024. DOI: 10.1186/s13634-023-01103-1. [Crossref] This one
  matches "Borhani-Darian et al., deep-learning GNSS spoofing detection, 2024" on authorship and topic.
- **Recommendation:** replace the citation with DOI 10.1186/s13634-023-01103-1 (EURASIP JASP 2024(1):14)
  and drop the "Ad Hoc Networks 163:103597" venue/volume, which belongs to an unrelated Korium et al. paper.

---

## 14. Namagembe, Ibrahim, Rahman & Pillai 2026 — VERIFIED (note: proposal says 2026, matches)

- Namagembe, C. O., Ibrahim, M., Rahman, M. A., Pillai, P. "Machine Learning-Based GPS Spoofing Detection
  and Mitigation for UAVs." *Computers, Materials & Continua*, 86(2), 2026. DOI: 10.32604/cmc.2025.070316.
  [Crossref] Authors, venue, volume/issue all match.

---

## 16. Wright et al. 2022 — VERIFIED exactly

- Wright, M. J., Anastassiou, L., Mishra, C., Davies, J. M., Phillips, A. M., Maskell, S., Ralph, J. F.
  "Cold atom inertial sensors for navigation applications." *Frontiers in Physics*, 10:994459, 2022.
  DOI: 10.3389/fphy.2022.994459. [Crossref] Matches exactly.

---

## New related-work items

- **Liu et al. 2026, "G²FL: Robust Federated Learning for GNSS Spoofing Detection" — VERIFIED.**
  Liu, S., Liu, W., Hussain, A., Papadimitratos, P. *2026 IEEE ICC Workshops*, DOI:
  10.1109/ICCWorkshops63917.2026.11586283. [Crossref] A closely related companion paper by the same group
  also exists and may be useful: "Self-supervised federated GNSS spoofing detection with opportunistic
  data," Liu, W., Papadimitratos, P., *2025 IEEE/ION PLANS*, DOI: 10.1109/PLANS61210.2025.11028268.

- **Ren et al. 2020, "Adaptive Sensor Fusion of Camera, GNSS and IMU for Autonomous Driving Navigation" —
  VERIFIED.** Ren, W., Jiang, K., Chen, X., Wen, T., Yang, D. *2020 4th CAA International Conference on
  Vehicular Control and Intelligence (CVCI)*, DOI: 10.1109/CVCI51460.2020.9338655. [Crossref]

- **Negru et al., "UWB-Aided Hybrid Navigation System in Degraded GNSS Environments" — VERIFIED.**
  Negru, S. A., Geragersian, P., Petrunin, I., Guo, W. *ION GNSS+ 2024, Proceedings of the 37th
  International Technical Meeting*, DOI: 10.33012/2024.19737. [Crossref] Same author team as item 2
  (Sensors 2024 paper) — confirms this is a companion/earlier-stage publication from the same group.

---

## Summary table

| # | Ref | Status | DOI | Note |
|---|---|---|---|---|
| 1 | Zhou 2023 | MISMATCH | 10.1109/IJCNN54540.2023.10191843 (MVMAFOL, wrong fit) / 10.1016/j.inffus.2023.102182 (better fit) | MVMAFOL = online learning/resource alloc, not positioning; use Info Fusion paper instead |
| 2 | Negru 2024 | VERIFIED / reframe | 10.3390/s24030981 | "federated fusion" = classical EKF+GRU master filter, not FL |
| 3/15 | Khan 2025 | VERIFIED | 10.1002/ett.70138 | SVM @ RSU; post-detection nav action unstated |
| 4 | Chai 2025 | VERIFIED | 10.1109/JIOT.2025.3588162 | Identified this pass (baseline pass failed) |
| 5 | Meng 2025 | NOT FOUND | — | 3 weak candidates listed |
| 6 | Gu 2021 | NOT FOUND | — | 3 weak candidates listed |
| 7 | Pardhasaradhi 2022 | VERIFIED | 10.1109/JSEN.2022.3168940 | Detect-then-switch-to-radar, not continuous weighting (unchanged caveat) |
| 8 | Chehimi & Saad 2023 | MISMATCH | 10.1109/MNET.2023.3327365 / 10.1109/ICASSP43922.2022.9746622 / 10.1007/s42484-024-00174-z | None do clock-sync/positioning |
| 9 | Tariq 2026 | MISMATCH | 10.7717/peerj-cs.3875 | Not consensus-based; 97% = mission success, not detection accuracy |
| 10 | Kannamarlapudi 2025 | NOT FOUND | — | Zero hits anywhere |
| 11 | Hazarika 2025 | VERIFIED | 10.1109/TCOMM.2024.3502667 | Trajectory-prediction sub-claim unconfirmed |
| 12 | Radoš/Brkić/Begušić 2024 | VERIFIED | 10.3390/s24134210 | Exact match |
| 13 | Borhani-Darian 2024 | MISMATCH | 10.1186/s13634-023-01103-1 (correct) vs 10.1016/j.adhoc.2024.103597 (wrong, = Korium et al.) | Citation mixed up with unrelated Ad Hoc Networks paper |
| 14 | Namagembe 2026 | VERIFIED | 10.32604/cmc.2025.070316 | Exact match |
| 16 | Wright 2022 | VERIFIED | 10.3389/fphy.2022.994459 | Exact match |
| new | Liu 2026 G²FL | VERIFIED | 10.1109/ICCWorkshops63917.2026.11586283 | — |
| new | Ren 2020 | VERIFIED | 10.1109/CVCI51460.2020.9338655 | — |
| new | Negru ION UWB | VERIFIED | 10.33012/2024.19737 | Same group as item 2 |
