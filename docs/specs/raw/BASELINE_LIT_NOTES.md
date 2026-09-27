# Baseline Literature Fidelity Check (WP-6.0)

_Author: LIT-CHECK agent · 2026-09-23 · against ARCHITECTURE.md v1.0 §3.3, §5_

Scope: confirm whether Baseline A and Baseline B (as defined in ARCHITECTURE.md §5) faithfully represent
the five papers the proposal cites by surname+year+topic only. All full texts below were paywalled behind
IEEE Xplore / Wiley; identification and extraction rely on abstracts, search-engine snippets, and
publicly indexed metadata (ADS, ResearchGate previews, ACM/Springer landing pages) — never full PDFs I
actually opened, except where a WebFetch succeeded. Nothing here should be treated as a verified quote
from the full text unless marked as such.

---

## 1. Baseline A — FL detector + memoryless detect-and-exclude (w=1 if p<0.5 else 0)

### 1.1 Khan 2025 (connected vehicles)

- **Best-match title:** "Enhancing Autonomous Vehicle Security: Federated Learning for Detecting GPS
  Spoofing Attack"
- **Venue:** *Transactions on Emerging Telecommunications Technologies* (Wiley), Vol. 36, No. 4, 2025.
- **DOI/URL:** 10.1002/ett.70138 — https://onlinelibrary.wiley.com/doi/10.1002/ett.70138 (page load
  returned HTTP 403 to WebFetch; identification is from Wiley/ACM index pages and search snippets only,
  **UNVERIFIED against full text**).
- **Confidence: medium.** Surname, year, topic ("FL for GPS spoofing detection, connected/autonomous
  vehicles") all match. No serious alternative candidate surfaced with "Khan" as first author in this
  exact niche for 2025; the ACM/Wiley catalogue entries agree on venue/volume/issue. Full author list not
  confirmed (could not open the paper).
- **Extraction (from abstract/snippets only, UNVERIFIED against full text):**
  - Detects: GPS spoofing via **localization consistency** — each vehicle computes its own position from
    dead-reckoning-style sensors (yaw rate, steering angle, wheel speed) and compares it against the GNSS
    fix; disagreement is the spoof signal, not a channel/PVT-feature classifier like our x1–x13.
  - Classifier: **SVM**, not an MLP, aggregated at a Roadside Unit (RSU) rather than a peer FL server.
  - FL mechanics: vehicles "compute weights" that feed the RSU aggregation — this appears to be an
    **aggregation weight**, not a post-detection navigation trust weight. **UNVERIFIED**: no snippet
    describes what happens to the *navigation solution* after a spoof flag (alarm-only vs. GNSS exclusion
    vs. switch to dead-reckoning). This is the load-bearing gap for Baseline A's claim.
  - Evaluation setup: CARLA-simulated vehicle trajectories.

### 1.2 Chai 2025 (UAV swarms)

- **Best-match candidate: none identified with usable confidence.** Search across Google/arXiv-indexed
  engines for "Chai 2025 federated learning UAV swarm GNSS spoofing/jamming detection" did not surface a
  paper with first author "Chai" matching this description. Closest neighbors found (none are "Chai" and
  none are proposed as the match): "FIDSUS: Federated Intrusion Detection for Securing UAV Swarms" (IEEE
  IoT-J, 2025, authors unconfirmed), "A Federated Learning Framework with LSTM-RNN for UAV Network
  Intrusion Detection" (CCSICC 2025 workshop chapter).
- **Confidence: low / UNVERIFIED (identification failed).** Do not treat any of the above as Chai 2025.
- **Extraction:** not possible — paper unidentified. Detection target, features, aggregator, and
  post-detection navigation behaviour are all **UNVERIFIED**.
- Recommendation to Master: needs the proposal's actual reference-list entry (full title or DOI) to
  proceed; surname+year+topic alone was not enough to disambiguate inside the FL/UAV/spoofing literature,
  which is crowded in 2025.

### Baseline A verdict

**PARTIALLY FAITHFUL, with one confirmed identification and one unresolved.**

- What is supported: Khan 2025 (medium confidence) does describe an FL-trained *classifier* for GPS
  spoofing in a connected-vehicle setting, consistent with "FL-trained detector" in Baseline A's label.
- What is NOT confirmed: (a) whether Khan 2025's post-detection behaviour is actually a **memoryless
  binary exclude** (w=1/w=0, no hysteresis) as Baseline A specifies — the located material describes
  detection/classification but not an explicit fusion-side action; (b) Chai 2025 could not be identified
  at all, so its "UAV swarm" half of the justification is currently unsupported by any concrete source.
- **Suggested minimal change:** flag Baseline A's design rationale as resting on one partially-verified
  paper. Before results exist, the Master should either (i) obtain the actual proposal reference list
  entries (title/DOI) for both papers so full text can be pulled, or (ii) soften the citation in
  ARCHITECTURE.md §5 to "FL detection literature, exemplified by Khan 2025 (medium-confidence ID);
  detect-and-exclude is our own simplification of the general FL-detection pattern, not a documented rule
  from either paper" — since neither paper's exact post-detection navigation rule is currently verified to
  match "w=1 if p<0.5 else 0".

---

## 2. Baseline B / B′ — local-only detector + continuous adaptive trust law (B′: χ²-driven weighting)

### 2.1 Meng 2025 (adaptive multi-sensor fusion isolating a compromised sensor)

- **Best-match candidate: none identified with usable confidence.** Search for "Meng 2025 adaptive
  multi-sensor fusion isolate compromised sensor GNSS/INS" surfaced only tangential hits: Meng et al. 2016
  (covariance-matching adaptive UKF, wrong year), and an unrelated 2025 UAV paper ("MARS: Defending UAVs
  from attacks on inertial sensors...", H. Meng, first-author match on surname only, topic is IMU
  anomaly/recovery not GNSS trust fusion — **not proposed as a match**, too weak on topic fit).
- **Confidence: low / UNVERIFIED (identification failed).**
- **Extraction:** not possible. Fusion/weighting rule, binary-vs-continuous behaviour, recovery, and
  sensors used are all **UNVERIFIED**.

### 2.2 Gu 2021 (fault-tolerant adaptive Kalman fusion, GNSS/INS)

- **Best-match candidate: none identified with usable confidence.** Repeated searches for "Gu 2021
  fault-tolerant adaptive Kalman filter GNSS/INS" returned only non-matching authors (Jiang/Zhang/Li 2021
  GPS Solutions "Performance evaluation of the filters with adaptive factor and fading factor", and several
  2024–2026 papers on adaptive fault-tolerant federated Kalman filters with no "Gu" as lead author). No
  candidate with surname "Gu" and year 2021 on this exact topic was found.
- **Confidence: low / UNVERIFIED (identification failed).**
- **Extraction:** not possible. **UNVERIFIED.**

### 2.3 Pardhasaradhi 2022 (GPS-spoofing-resilient fusion via residual-based trust isolation)

- **Confirmed title:** "GPS Spoofing Detection and Mitigation for Drones Using Distributed Radar Tracking
  and Fusion"
- **Authors:** Bethi Pardhasaradhi, Linga Reddy Cenkeramaddi.
- **Venue:** IEEE Sensors Journal, Vol. 22, Issue 11, pp. 11122–11134, 2022.
- **DOI:** 10.1109/JSEN.2022.3168940 (from search-engine-indexed abstract page; IEEE Xplore itself returned
  no readable content to WebFetch, so this is **UNVERIFIED against the primary IEEE page**, but the DOI is
  consistent across two independent index sources — ADS and the paper's own IEEE Xplore document id
  9760395).
- **Confidence: high** for identification (surname, year, and topic — GPS spoofing mitigation for
  drones via fusion — all match cleanly; only one candidate paper surfaced across multiple searches).
- **Extraction (abstract-level, UNVERIFIED against full text/figures):**
  - Sensors: UAV's own onboard estimate (EKF, "primary data") **plus ground-based distributed radar with a
    local tracker** (EKF + global-nearest-neighbor tracker, "secondary data") — i.e., an **independent
    external sensor**, not GNSS/IMU/CAI trust reweighting within one platform.
  - Fusion rule after detection: **"correlation-free fusion"** of the secondary (radar) data, whose fused
    state is then used **as the control input** to the UAV. This reads as a **detect-then-switch** pattern
    (falls back to radar-derived state), not the continuous, innovation-magnitude-proportional trust weight
    `w ∈ [w_min,1]` that our §3.3 trust law or B′'s `p_j = F_{χ²_3}(3·x1_j)` describe.
  - Binary vs. continuous: closer to **binary switch-over on detection**, not obviously continuous
    (**UNVERIFIED** — the abstract snippet does not state whether the fusion weight varies continuously
    with the residual before/after the switch; could not confirm from methodology/figures, which are
    behind the IEEE paywall).
  - Recovery behaviour after the attack ends: **UNVERIFIED** (not stated in any accessible abstract text).

### Baseline B / B′ verdict

**PARTIALLY FAITHFUL, and possibly misattributed on two of three citations.**

- Only one of the three cited papers (Pardhasaradhi 2022) could be identified with high confidence, and
  even that one does not obviously match Baseline B's "continuous adaptive trust law" framing — its
  described mechanism looks like a **binary fallback to an independent radar-based fusion track**, not a
  continuously varying trust weight applied to the *same* GNSS/INS filter the way §3.3's `w_j` update or
  B′'s χ²-cdf rule works. If confirmed on full text, this is closer in spirit to Baseline A's exclude
  behaviour (or to A0/Abl-binary) than to Baseline B's continuous law.
  it is also GNSS+radar, not GNSS+INS, so "sensors used" differs from our GNSS/IMU/CAI setup.
- Meng 2025 and Gu 2021 could not be identified at all, so two-thirds of Baseline B's literature basis is
  currently **unsupported by any verified source**.
- **Suggested minimal change:** (1) get the exact reference-list entries (title/DOI) for Meng 2025 and Gu
  2021 from the proposal document itself — surname+year+topic was insufficient to disambiguate against a
  large 2021–2026 literature on adaptive/fault-tolerant Kalman fusion; (2) for Pardhasaradhi 2022
  specifically, either re-derive B′'s rule from a paper that actually does continuous χ²-based GNSS trust
  weighting within the same filter (e.g., classic residual-chi-square RAIM/innovation-weighting literature,
  which is closer to what B′ already implements structurally), or relabel Pardhasaradhi 2022 as motivating
  only the general "detect a compromised source, isolate it, keep navigating on the others" *philosophy*
  of Baseline B rather than its exact continuous-law mechanics.

---

## 3. Summary table

| Paper | Best-match title | DOI | Post-detection behaviour / fusion rule (as found) | ID confidence |
|---|---|---|---|---|
| Khan 2025 | Enhancing Autonomous Vehicle Security: FL for Detecting GPS Spoofing Attack | 10.1002/ett.70138 (unverified vs. primary page) | UNVERIFIED — SVM classifies spoof via dead-reckoning-vs-GNSS mismatch; navigation-side action after flag not found | medium |
| Chai 2025 | not identified | — | UNVERIFIED | low / failed |
| Meng 2025 | not identified | — | UNVERIFIED | low / failed |
| Gu 2021 | not identified | — | UNVERIFIED | low / failed |
| Pardhasaradhi 2022 | GPS Spoofing Detection and Mitigation for Drones Using Distributed Radar Tracking and Fusion | 10.1109/JSEN.2022.3168940 (unverified vs. primary page) | Detect → correlation-free fusion of independent radar track → used as control input (looks like binary switch-over, not continuous weighting); recovery UNVERIFIED | high |

## 4. Master action items

1. Supply full reference-list entries (title/DOI, not just surname+year) for Chai 2025, Meng 2025 and
   Gu 2021 — three of five citations could not be resolved from surname+year+topic alone, and the
   IEEE/Wiley pages for the two that were identified (Khan 2025, Pardhasaradhi 2022) returned HTTP 403 to
   automated fetch, so even those need a manual full-text check (library access / institutional login)
   before §5's claims are treated as confirmed.
2. Re-examine whether Pardhasaradhi 2022, if it is the intended citation, actually supports "continuous
   adaptive trust law" — the accessible material points to a detect-then-switch-to-independent-sensor
   pattern, which is a materially different claim from §3.3's continuously varying `w_j`.
3. None of the five DOIs above should be inserted into ARCHITECTURE.md §5 yet — Khan's and
   Pardhasaradhi's DOIs are index-sourced, not confirmed against the publisher's own page, and the other
   three are unidentified.
