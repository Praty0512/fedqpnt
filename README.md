# FedQPNT

Federated, quantum-sensor-augmented PNT (positioning, navigation, and timing) with continuous attack-adaptive trust fusion.

## Status

**Results are PRELIMINARY on tuning seeds (500–599).** M1 Milestone (single-node closed loop) is signed off with stated limitations; federation, full campaign evaluation, and test-seed results are in progress. See [PROJECT_STATE.md](PROJECT_STATE.md) for milestone status and open issues.

- **M0 — Foundations:** ✅ Signed off 2026-09-26
- **M1 — Single-node closed loop:** ✅ Signed off 2026-09-28 (with limitations)
- **M2 — Federation:** 🔶 In progress
- **M3 — Baselines/eval/stats:** 🔶 Pipeline done, not yet at scale
- **M4 — Full 15-scenario campaign:** ⛔ Gated on issue #1 (κ_R/filter overconfidence)
- **M5 — Paper/patent/figures/repro:** ⏸ On hold

## Repository Layout

- **`fedqpnt/`** – Core package (subpackages below)
  - `attacks/` – GNSS spoofing (drift, meaconing) and jamming models
  - `core/` – Seeding, types, world model, interfaces
  - `data/` – Jarlaud et al. 2024 dataset parsing and calibration
  - `eval/` – Campaign runner, metrics, statistics
  - `fl/` – Federated learning client, aggregator, orchestration
  - `fleet/` – Multi-node runner and simulation harness
  - `fusion/` – Error-state EKF, GNSS receiver, Kalman filtering
  - `gnss/` – GNSS constellation, signal models, WLS receiver
  - `node/` – Single-node closed-loop agent and dataflow
  - `sensors/` – IMU, quantum accelerometer, trajectory strapdown
  - `sim/` – Trajectory generation, strapdown, simulation mechanics
  - `training/` – Detector training pipelines
  - `trust/` – Trust law and continuous soft-weighting models
- **`tests/`** – Pytest suite (40 test modules, ~300 tests)
- **`scripts/`** – Campaign runners, data processing, diagnostics (40 scripts)
- **`results/`** – Generated artefacts (tuning seeds only; test seeds gated by GATE_D047.json)
- **`data/`** – Raw (Jarlaud 2024) and processed datasets
- **`docs/`** – Specifications (simulation, GNSS/attacks, real data, architecture) and decision logs
- **`paper/`** – Paper outline and figures (on hold)

## Quickstart

### Install and validate

```bash
# Clone and check environment
git clone https://github.com/Praty0512/fedqpnt.git
cd fedqpnt
python -m pip install -r requirements.txt

# Run test suite
python -m pytest tests/ -v
```

**Expected:** 40 test modules, ~300 tests passing (all green on Python 3.11+).

### Single-node mission

```bash
# Run one nominal 30-min mission (seed 500, no attack)
python -c "
from fedqpnt.node.runner import RunSpec, run_single
spec = RunSpec(name='test', master_seed=500, method='fedqpnt_local', duration_s=1800, record=True)
result = run_single(spec)
print(f'Position RMSE: {result[\"rmse_h_m\"]:.2f} m')
"
```

### Dry-run campaign (tuning seeds, short duration)

```bash
# Test plumbing with 2 scenarios, 3 seeds, 120 s per mission
python scripts/run_campaign.py \
  --scenarios S1 S2-low \
  --methods fedqpnt_local baseline_a undefended \
  --seeds 500 501 502 \
  --duration 120 \
  --workers 2 \
  --run-root runs/dryrun
```

Results are written to `runs/dryrun/`.

## Key Design Docs

- **[ARCHITECTURE.md](docs/specs/ARCHITECTURE.md)** – System dataflow, EKF, trust law, detector, FL protocol
- **[TRUST_DESIGN_V2.md](docs/specs/TRUST_DESIGN_V2.md)** – Continuous soft-weighting trust model
- **[DECISION_LOG.md](DECISION_LOG.md)** – Master's rulings (D-001 through D-058)
- **[EXECUTION_LOG.md](EXECUTION_LOG.md)** – Reproducibility trace, all WP runs and seeds
- **[PROJECT_STATE.md](PROJECT_STATE.md)** – Milestone status, open issues, work queue

## Data

Real cold-atom interferometer data from [Jarlaud et al. 2024](https://doi.org/10.1038/s41467-024-50804-0) (*Nat. Commun.* 15:6406) is used to calibrate quantum-sensor noise. See [docs/DATA.md](docs/DATA.md) for dataset access and reproduction scripts.

## Reproducibility

Deterministic seeding (SHA-256 stream per seed) ensures bit-identical reruns. See [docs/REPRODUCE.md](docs/REPRODUCE.md) for seeds policy, gate conditions, and mapping of results files to scripts.

## Citation and License

License: TBD

For citation: see [CITATION.cff](CITATION.cff).

---

**Last updated:** 2026-09-29 · **Repository:** [github.com/Praty0512/fedqpnt](https://github.com/Praty0512/fedqpnt)
