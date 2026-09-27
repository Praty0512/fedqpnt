"""Build the file manifest for the Jarlaud et al. 2024 raw dataset.

Walks data/raw/jarlaud2024/extracted/Raw Data and writes one row per file to
data/processed/jarlaud2024/manifest.csv with: figure, date, run, category,
relative path, size (bytes), line count (text files), column header (if any),
sample rate estimate (Streaming/RTData files) and duration estimate.

Owned by DATA-INGEST (WP-2.5). Read-only w.r.t. fedqpnt/sensors, fedqpnt/core.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / "data" / "raw" / "jarlaud2024" / "extracted" / "Raw Data"
OUT = ROOT / "data" / "processed" / "jarlaud2024" / "manifest.csv"

RUN_RE = re.compile(r"Run (\d+)")


def classify(name: str) -> str:
    if name == "Parameters.txt":
        return "parameters"
    if name.startswith("Raman-DetectData"):
        return "detect_data"
    if "Avg01-Ratios" in name:
        return "avg01_ratios"
    if "AvgRatios" in name:
        return "avg_ratios"
    if name.endswith("RotationsData.txt"):
        return "rotations_data"
    if name.endswith("RTData.txt"):
        return "rt_data"
    if name.endswith(".csv"):
        return "streaming"
    return "other"


def count_lines_and_header(path: Path) -> tuple[int, str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return -1, ""
    n = len(lines)
    header = lines[0].strip() if n else ""
    return n, header


def main() -> None:
    rows = []
    for path in sorted(EXTRACTED.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(EXTRACTED)
        parts = rel.parts
        figure = parts[0] if len(parts) > 0 else ""
        date = parts[1] if len(parts) > 1 else ""
        # run folder, e.g. "Run 21" under .../Raman/Run 21/...
        run = ""
        for p in parts:
            m = RUN_RE.match(p)
            if m:
                run = m.group(1)
                break
        else:
            # streaming files: Run19_1.csv -> run 19
            m2 = re.match(r"Run(\d+)_", path.name)
            if m2:
                run = m2.group(1)
        category = classify(path.name)
        size = path.stat().st_size

        if category == "streaming":
            # Large (up to ~2.5M rows); just read the header line, don't load fully.
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                header = f.readline().strip()
            n_lines = -1  # filled in separately for the small set of files we actually use
        else:
            n_lines, header = count_lines_and_header(path)

        rows.append(
            {
                "figure": figure,
                "date": date,
                "run": run,
                "category": category,
                "path": str(rel).replace("\\", "/"),
                "size_bytes": size,
                "n_lines": n_lines,
                "header": header,
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["figure", "date", "run", "category", "path", "size_bytes", "n_lines", "header"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
