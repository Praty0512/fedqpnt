# Method References — Verification Report (Round 2)

Verified against Crossref API (`api.crossref.org/works`), OpenAlex (`api.openalex.org/works`), arXiv, and dblp/ION/publisher pages where Crossref had no record (PMLR, MLSys, NeurIPS proceedings, ION GNSS, and pre-DOI-era journals commonly lack DOIs). No metadata invented; every entry below is grounded in an API/page response captured during this pass. Psiaki & Humphreys 2016 was skipped per instructions (already verified).

Status legend: **VERIFIED** / **MISMATCH** (identity confirmed but a field differs from what was expected) / **NOT FOUND**.

---

## A. Federated learning (robustness / aggregation methods)

1. **McMahan, H. B., Moore, E., Ramage, D., Hampson, S., Agüera y Arcas, B.** "Communication-Efficient Learning of Deep Networks from Decentralized Data," *AISTATS 2017* (PMLR 54:1273–1282). — **VERIFIED**. arXiv:1602.05629 (v4, 2017). Source: OpenAlex (W2541884796), arXiv. No Crossref DOI (PMLR proceedings do not register DOIs); cite via PMLR volume/arXiv.

2. **Li, T., Sahu, A. K., Zaheer, M., Sanjabi, M., Talwalkar, A., Smith, V.** "Federated Optimization in Heterogeneous Networks," *MLSys 2020*. — **VERIFIED**. arXiv:1812.06127. Source: OpenAlex (W2914328083). No Crossref DOI (MLSys proceedings unindexed by Crossref).

3. **Yin, D., Chen, Y., Ramchandran, K., Bartlett, P. L.** "Byzantine-Robust Distributed Learning: Towards Optimal Statistical Rates," *ICML 2018*, PMLR 80:5650–5659. — **VERIFIED**. arXiv:1803.01498. Source: dblp (conf/icml/YinCRB18), proceedings.mlr.press/v80/yin18a.html. No Crossref DOI.

4. **Sun, Z., Kairouz, P., Suresh, A. T., McMahan, H. B.** "Can You Really Backdoor Federated Learning?" arXiv:1911.07963, 2019. — **VERIFIED**. Source: arXiv abstract page. No DOI (preprint only; not published in a proceedings with DOI as of this check).

5. **Baruch, G., Baruch, M., Goldberg, Y.** "A Little Is Enough: Circumventing Defenses For Distributed Learning," *NeurIPS 2019* (NeurIPS 32). — **VERIFIED**. arXiv:1902.06156. Source: arXiv abstract page, NeurIPS proceedings (proceedings.neurips.cc/paper/2019/hash/ec1c59141046cd1866bbbcdfb6ae31d4-Abstract.html). No Crossref-resolvable DOI (NeurIPS proceedings use non-resolving `10.5555/...` ACM DL catalogue numbers, not registered DOIs).

6. **Blanchard, P., El Mhamdi, E. M., Guerraoui, R., Stainer, J.** "Machine Learning with Adversaries: Byzantine Tolerant Gradient Descent," *NeurIPS 2017* (NeurIPS 30), pp. 119–129. — **VERIFIED** (Krum). Source: dblp (conf/nips/BlanchardMGS17), proceedings.neurips.cc/paper/2017/hash/f4b9ec30ad9f68f89b29639786cb62ef-Abstract.html. No true DOI — the commonly cited `10.5555/3294771.3294783` is an ACM Digital Library catalogue identifier, not a Crossref-registered DOI (confirmed 404 on `api.crossref.org/works/10.5555/3294771.3294783`). Cite via NeurIPS proceedings URL.

7. **Cao, X., Fang, M., Liu, J., Gong, N. Z.** "FLTrust: Byzantine-robust Federated Learning via Trust Bootstrapping," *NDSS 2021*. — **VERIFIED**. DOI: [10.14722/ndss.2021.24434](https://doi.org/10.14722/ndss.2021.24434). Source: Crossref + OpenAlex (both agree).

8. **Xie, C., Koyejo, S., Gupta, I.** "Asynchronous Federated Optimization," arXiv:1903.03934, 2019 (FedAsync). — **VERIFIED**. Source: arXiv abstract page. No DOI (preprint).

---

## B. Estimation / statistics

9. **Page, E. S.** "Continuous Inspection Schemes," *Biometrika*, 41(1–2):100–115, 1954. — **VERIFIED** (CUSUM). DOI: [10.1093/biomet/41.1-2.100](https://doi.org/10.1093/biomet/41.1-2.100) (OUP publisher DOI; Crossref also lists the older JSTOR-era alias `10.2307/2333009` for the same article — use the OUP DOI as canonical). Source: Crossref.

10. **Solà, J.** "Quaternion kinematics for the error-state Kalman filter," arXiv:1711.02508, 2017. — **VERIFIED**. Source: arXiv abstract page, dblp. No DOI (preprint, unpublished elsewhere).

11. **Anderson, B. D. O., Moore, J. B.** *Optimal Filtering*. Prentice-Hall, Englewood Cliffs, NJ, 1979. — **VERIFIED**. ISBN-10: 0-13-638122-7; ISBN-13: 978-0-13-638122-8. Source: publisher listing / Amazon catalogue record cross-checked against the standard citation.

12. **Wilcoxon, F.** "Individual Comparisons by Ranking Methods," *Biometrics Bulletin*, 1(6):80–83, 1945. — **VERIFIED**. DOI: [10.2307/3001968](https://doi.org/10.2307/3001968) (exact match to the expected DOI given in the task). Source: Crossref.

13. **Holm, S.** "A Simple Sequentially Rejective Multiple Test Procedure," *Scandinavian Journal of Statistics*, 6(2):65–70, 1979. — **VERIFIED** (bibliographic details), but **no DOI could be resolved**. Source: JSTOR stable URL http://www.jstor.org/stable/4615733; Crossref queries returned only later citing/related papers (e.g., Holland & Copenhaver 1987), not this original article — Wiley/JSTOR appears not to have back-registered a DOI for this 1979 volume in Crossref. Cite without DOI, using the JSTOR stable link if a locator is needed.

14. **Demšar, J.** "Statistical Comparisons of Classifiers over Multiple Data Sets," *Journal of Machine Learning Research*, 7:1–30, 2006. — **VERIFIED** (bibliographic details; well-known JMLR paper, PDF at jmlr.org/papers/v7/demsar06a.html), but **no DOI** — JMLR did not assign DOIs to papers from this era, and neither Crossref nor OpenAlex returned a record for it under any query tried. Cite without DOI.

15. **Bar-Shalom, Y., Li, X. R., Kirubarajan, T.** *Estimation with Applications to Tracking and Navigation: Theory, Algorithms and Software*. Wiley, 2001. — **VERIFIED**. ISBN-10: 0-471-41655-X; ISBN-13: 978-0-471-41655-5. Source: Wiley/Amazon catalogue listing (NEES/NIS consistency-test source text).

16. **Groves, P. D.** *Principles of GNSS, Inertial, and Multisensor Integrated Navigation Systems*, 2nd ed. Artech House, 2013, 776 pp. — **VERIFIED**. ISBN-13: 978-1-60807-005-3 (print), 978-1-60807-006-0 (eBook). Source: Cambridge Core book-review record, Artech House catalogue.

17. **IEEE Std 952-1997**, "IEEE Standard Specification Format Guide and Test Procedure for Single-Axis Interferometric Fiber Optic Gyros" (Allan-variance specification format). — **VERIFIED**. DOI: [10.1109/IEEESTD.1998.86153](https://doi.org/10.1109/IEEESTD.1998.86153). Source: Crossref (query matched exact title). Note: a later corrigendum exists as a separate standard/DOI (`952-1997/Cor 1-2016`, DOI 10.1109/IEEESTD.2017.7862718) — not needed unless the corrigendum content is specifically cited.

---

## C. Cold-atom interferometry (CAI) physics

18. **Lautier, J., Volodimer, L., Hardin, T., Merlet, S., Lours, M., Pereira Dos Santos, F., Landragin, A.** "Hybridizing matter-wave and classical accelerometers," *Applied Physics Letters*, 105:144102, 2014. — **VERIFIED**. DOI: [10.1063/1.4897358](https://doi.org/10.1063/1.4897358). Source: Crossref (title, journal, year all match; article/page number 144102 consistent with journal record).

19. **Cheiney, P., Fouché, L., Templier, S., Napolitano, F., Battelier, B., Bouyer, P., Barrett, B.** "Navigation-Compatible Hybrid Quantum Accelerometer Using a Kalman Filter," *Physical Review Applied*, 10:034030, 2018. — **VERIFIED**. DOI: [10.1103/PhysRevApplied.10.034030](https://doi.org/10.1103/PhysRevApplied.10.034030). Source: Crossref (exact title/venue/article-number match).

20. **Templier, S., Cheiney, P., d'Armagnac de Castanet, Q., Gouraud, B., et al.** "Tracking the vector acceleration with a hybrid quantum accelerometer triad," *Science Advances*, 8:eadd3854, 2022. — **VERIFIED**. DOI: [10.1126/sciadv.add3854](https://doi.org/10.1126/sciadv.add3854). Source: Crossref. This is the exact DOI already recorded in `docs/specs/ARCHITECTURE.md` (lines 194, 873) — confirms it is correct.

21. **Geiger, R., Landragin, A., Merlet, S., Pereira Dos Santos, F.** "High-accuracy inertial measurements with cold-atom sensors," *AVS Quantum Science*, 2:024702, 2020. — **VERIFIED**. DOI: [10.1116/5.0009093](https://doi.org/10.1116/5.0009093). Source: Crossref (exact title/author/venue/year match).

22. **Bidel, Y., Zahzam, N., Blanchard, C., Bonnin, A., Cadoret, M., Bresson, A., Rouxel, D., Lequentrec-Lalancette, M. F.** "Absolute marine gravimetry with matter-wave interferometry," *Nature Communications*, 9:627, 2018. — **VERIFIED**. DOI: [10.1038/s41467-018-03040-2](https://doi.org/10.1038/s41467-018-03040-2). Source: Crossref (exact title/venue/year match).

23. **Wang, X., et al.** "Enhancing Inertial Navigation Performance via Fusion of Classical and Quantum Accelerometers," arXiv:2103.09378, 2021. — **VERIFIED** (this is the "Wang et al. 2021" cited in `docs/specs/ARCHITECTURE.md` lines 194 and 873, confirmed by grep). Source: arXiv abstract page (arxiv.org/abs/2103.09378) — title and topic (fusing classical + quantum/cold-atom accelerometer data for INS) match the architecture doc's usage exactly. No DOI (preprint).

---

## D. GNSS models and attack/testbed references

24. **Klobuchar, J. A.** "Ionospheric Time-Delay Algorithm for Single-Frequency GPS Users," *IEEE Transactions on Aerospace and Electronic Systems*, AES-23(3):325–331, 1987. — **VERIFIED**. DOI: [10.1109/TAES.1987.310829](https://doi.org/10.1109/TAES.1987.310829). Source: Crossref (exact match).

25. **Saastamoinen, J.** "Atmospheric Correction for the Troposphere and Stratosphere in Radio Ranging Satellites," in *The Use of Artificial Satellites for Geodesy*, Geophysical Monograph Series, vol. 15, AGU, Washington, D.C., pp. 247–251, 1972. — **VERIFIED with a metadata caveat (MISMATCH on year field only)**. DOI: [10.1029/GM015p0247](https://doi.org/10.1029/GM015p0247). Source: Crossref. Crossref's `published` field shows 2013, which reflects AGU/Wiley's retroactive DOI registration/digitization date for this monograph series, not the actual publication year; the monograph itself (Geophysical Monograph 15) was published in 1972, and the original citation year (1972) should be kept in the bibliography with the DOI attached.

26. **Parkinson, B. W., Axelrad, P.** "Autonomous GPS Integrity Monitoring Using the Pseudorange Residual," *Navigation*, 35(2):255–274, 1988. — **VERIFIED** (RAIM). DOI: [10.1002/j.2161-4296.1988.tb00955.x](https://doi.org/10.1002/j.2161-4296.1988.tb00955.x). Source: Crossref (exact title/author/venue/year match).

27. **Humphreys, T. E., Bhatti, J. A., Shepard, D. P., Wesson, K. D.** "The Texas Spoofing Test Battery: Toward a Standard for Evaluating GPS Signal Authentication Techniques," *Proceedings of the ION GNSS 2012*, Nashville, TX, 2012. — **VERIFIED**, **no DOI**. Source: ION.org abstract page (ion.org/publications/abstract.cfm?articleID=10532), Semantic Scholar, UT Austin Radionavigation Lab (radionavlab.ae.utexas.edu/texbat). ION GNSS conference proceedings are not DOI-registered in Crossref. This is a distinct paper from the already-verified Humphreys et al. 2008 ION GNSS entry (#22 in `docs/REFERENCES.md`) — that one is "Assessing the Spoofing Threat"; this one introduces TEXBAT.

28. **Kaplan, E. D., Hegarty, C. J. (eds.)** *Understanding GPS/GNSS: Principles and Applications*, 3rd ed. Artech House, 2017, 1064 pp. — **VERIFIED**, resolving the "catalogue check pending" note in `docs/REFERENCES.md`. ISBN-13: 978-1-63081-058-0. Source: Cambridge Core (Journal of Navigation book review), Artech House catalogue.

29. **Misra, P., Enge, P.** *Global Positioning System: Signals, Measurements, and Performance*, 2nd ed. Ganga-Jamuna Press, 2006. — **MISMATCH (edition/printing ambiguity)**. Two distinct ISBNs exist for what is nominally the "2nd edition": (a) the original 2nd edition, 2006, 569 pp., ISBN-13 978-0-9709544-0-4 (ISBN-10 0-9709544-0-9); (b) a "Revised Second Edition" reprint, 2010, ISBN-13 978-0-9709544-2-8 (ISBN-10 0-9709544-2-5). `docs/REFERENCES.md` cites "2006" — that corresponds to ISBN-13 **978-0-9709544-0-4**, not the 2010 revised-reprint ISBN found in the first search pass. Use 978-0-9709544-0-4 for a 2006-dated citation. Source: AbeBooks/Amazon catalogue listings, SCIRP reference record (Misra & Enge 2006, Ganga-Jamuna Press, Lincoln).

---

## Notes for BibTeX build

- Only entries with status VERIFIED (all of A–D except the two flagged caveats, which are still usable — Saastamoinen with DOI+1972 year, Misra & Enge with the corrected ISBN) are included in `refs_methods.bib`.
- Holm 1979 and Demšar 2006 are included in the .bib without a `doi` field (none exists in Crossref/OpenAlex/JMLR for these).
- Krum (Blanchard et al. 2017) and Baruch et al. 2019 are included using their arXiv/NeurIPS-proceedings identifiers since no Crossref DOI exists; `10.5555/...` style ACM catalogue numbers were deliberately NOT used as `doi` fields since they do not resolve via `doi.org`.

## Summary counts

- **VERIFIED:** 27 (including 2 with a noted caveat: Saastamoinen 1972 year-field caveat, Misra & Enge 2006 ISBN/edition caveat)
- **MISMATCH:** 2 (Saastamoinen year metadata; Misra & Enge edition/ISBN — both folded into the VERIFIED count above since the underlying reference is confirmed to exist and is usable, just with a corrected field)
- **NOT FOUND:** 0
