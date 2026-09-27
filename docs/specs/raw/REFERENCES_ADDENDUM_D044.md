# References addendum (D-044), 2026-09-27

All DOIs below were resolved by the Master against Crossref/DataCite on 2026-09-27, unless marked otherwise. Merge into `paper/refs.bib` and `docs/REFERENCES.md` on the next paper pass.

## New related work (Crossref-resolved)
| Key | Citation | DOI |
|---|---|---|
| akram2026privacy | W. Akram et al., "A Privacy Preserving Federated Learning Framework for Securing Consumer Autonomous Vehicles Against AI-Enabled GPS Spoofing Attacks," *IEEE Trans. Consumer Electronics*, 2026 | 10.1109/tce.2026.3677491 |
| chen2025anomaly | Q. Chen et al., "Anomaly Detection and Secure Position Estimation Against GPS Spoofing Attack: A Security-Critical Study of Localization in Autonomous Driving," *IEEE Trans. Veh. Technol.*, 2025. Abstract: LSTM detector, then a camera+map UKF fallback (detect-then-switch; B-bin class) | 10.1109/tvt.2024.3454416 |
| wang2025gps | Z. Wang et al., "GPS Attack Detection and Defense for Secure Localization of Automated Vehicles Based on Vehicle-to-Vehicle Technology," *IEEE IoT J.*, 2025. Abstract: V2V density-clustering detection, then cooperative localisation (detect-then-switch) | 10.1109/jiot.2024.3424518 |
| jung2024analysis | J. Jung et al., "An Analysis of GPS Spoofing Attack and Efficient Approach to Spoofing Detection in PX4," *IEEE Access*, 2024. Spoofing kept under the EKF innovation-test threshold, which supports our RAIM/NIS-blind attack model | 10.1109/access.2024.3382543 |
| deng2024gnss | M. Deng et al., "GNSS Interference Signal Classification Based on Federated Learning," IEEE VTC2024-Fall, 2024 (uses TEXBAT) | 10.1109/vtc2024-fall63153.2024.10757822 |
| psiaki2020civilian | M. Psiaki, T. Humphreys, "Civilian GNSS Spoofing, Detection, and Recovery," in *Position, Navigation, and Timing Technologies in the 21st Century*, Wiley, 2020. Treats detection and recovery as distinct problems | 10.1002/9781119458449.ch25 |
| psiaki2011civilian | M. Psiaki et al., "Civilian GPS Spoofing Detection based on Dual-Receiver Correlation of Military Signals," ION GNSS 2011, pp. 2619–2645 (UT repository DOI) | 10.15781/t2513vc49 |
| humphreys2010assimilator | T. Humphreys, J. Bhatti, B. Ledvina, "The GPS Assimilator…," ION GNSS 2010, pp. 1942–1952 (UT repository DOI) | 10.15781/t20863n8q |

## Resolved / updated existing entries
| Entry | Update |
|---|---|
| Humphreys et al. 2008, "Assessing the Spoofing Threat: Development of a Portable GPS Civilian Spoofer," ION GNSS 2008, pp. 2314–2325 | DOI **10.15781/t26t0hc7q** (UT repository; DataCite resolved). Removes "no DOI" |
| Bar-Shalom, Li, Kirubarajan, *Estimation with Applications to Tracking and Navigation*, Wiley | DOI **10.1002/0471221279**; Crossref confirms ISBN 978-0-471-41655-5 (print) / 978-0-471-22127-2 (online); Crossref issued date 2002 (print 2001) |
| Chai et al. 2025 | Full biblio: *IEEE IoT J.* vol. 12, pp. 44177–44188 (Consensus). Aggregation = **accuracy-weighted** (abstract). Post-detection action: not stated |
| Khan et al. 2025 | Authors: M. M. Khan, M. Kamal, M. Shabbir, S. Alahmari (Consensus). Aggregation: SVM weights aggregated at an RSU ("secure aggregation", rule not named). Post-detection action and recovery: **NOT stated** in the text Consensus accessed |

## Still unverified (user/library)
- TEXBAT (Humphreys, Bhatti, Shepard, Wesson, ION GNSS 2012): no DOI in Crossref/DataCite. The page range is **unconfirmed**: sources conflict ("2845–2859" from a non-authoritative source). Needs the ION proceedings page.
- Misra & Enge 2006 ISBN: two candidates, 978-0-9709544-0-4 (REF-VERIFY-2) vs 978-0-9709544-1-1 (non-authoritative source). Unresolved.
- Anderson & Moore 1979, Groves 2013, Kaplan & Hegarty 2017 ISBNs: consistent across sources, but not checked against a catalogue.
- Pardhasaradhi 2022 full text: not retrieved. The abstract (Consensus) suffices for the B-bin characterisation.

## Rejected input
A second, non-Consensus pasted summary (links tagged `utm_source=gemini`) was **rejected as unreliable**:
- It asserted post-detection IMU fallback, sliding-window recovery and robust weighted aggregation for Khan 2025, contradicting the Consensus text (not stated).
- It asserted trimmed-mean/median aggregation for Chai 2025, contradicting Chai's abstract (accuracy-weighted).
- It gave truncated non-DOIs ("10.1109/TCE.2026", "10.1109/JIOT.2025", "10.1109/VTC2024-Fall").
None of its unverifiable claims were used (D-002, D-012).
