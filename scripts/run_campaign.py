#!/usr/bin/env python
"""CLI entry point for ``fedqpnt.eval.campaign`` (EVALUATION agent, WP-8.x).

Examples
--------
Dry-run plumbing check (TUNING seeds, SHORT runs)::

    python scripts/run_campaign.py --scenarios S1 S2-low --methods fedqpnt_local baseline_a undefended \\
        --seeds 500 501 502 --duration 120 --workers 2 --run-root runs/dryrun

Resuming just re-runs the same command; completed run files are skipped.

The TEST seed range (>= 10000) is refused unless both ``--final`` and
``--gate-cleared`` are given, and ``--gate-cleared`` is itself refused
unless ``results/GATE_D047.json`` says ``{"cleared": true}`` (D-046/D-047).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fedqpnt.eval.campaign import CampaignGateError, run_campaign
from fedqpnt.core.defaults import DEFAULT_KAPPA_R  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenarios", nargs="+", required=True, help="Scenario ids, e.g. S1 S2-low S2-med")
    ap.add_argument("--methods", nargs="+", default=None,
                     help="Method names; default is each scenario's own declared method list")
    ap.add_argument("--seeds", nargs="+", type=int, required=True)
    ap.add_argument("--duration", type=float, default=None, help="Override duration_s (e.g. short dry-runs)")
    ap.add_argument("--kappa-R", type=float, default=DEFAULT_KAPPA_R)
    ap.add_argument("--kappa-Q", type=float, default=1.0)
    ap.add_argument("--workers", type=int, default=2, help="Hard-capped at 4 (fedqpnt.eval.campaign.MAX_WORKERS)")
    ap.add_argument("--run-root", default="runs")
    ap.add_argument("--final", action="store_true", help="Required (with --gate-cleared) to run TEST seeds")
    ap.add_argument("--gate-cleared", action="store_true",
                     help="Required (with --final) to run TEST seeds; also checked against results/GATE_D047.json")
    args = ap.parse_args()

    try:
        results = run_campaign(args.scenarios, args.seeds, methods=args.methods, run_root=args.run_root,
                                duration_s=args.duration, kappa_R=args.kappa_R, kappa_Q=args.kappa_Q,
                                n_workers=args.workers, final=args.final, gate_cleared_flag=args.gate_cleared)
    except CampaignGateError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        raise SystemExit(2)

    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(json.dumps({"n_tasks": len(results), "counts": counts}, indent=2))


if __name__ == "__main__":
    main()
