"""Run recorder (WP-1.2, ARCHITECTURE.md section 11.5).

Writes a self-contained run directory::

    <root>/<run_id>[/<subdir>]/
        config.json         # RunConfig.to_json(), written immediately
        events.jsonl         # log_event(), appended + flushed immediately
        series/<stream>.<chunk:05d>.npz    # log()/flush(), chunked
        manifest.json         # written by close()

``load_run`` reconstructs a :class:`RunData` from a run directory.
"""
from __future__ import annotations

import hashlib
import json
import platform as _platform
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import scipy

from fedqpnt.core.types import CONTRACT_VERSION, TruthTrajectory

from .config import RunConfig

CHUNK_ROWS = 10_000


def code_version(root: Path | None = None) -> str:
    """sha256 over sorted (relative posix path + b'\\0' + file bytes) of fedqpnt/**/*.py."""
    base = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    pkg_dir = base / "fedqpnt"
    h = hashlib.sha256()
    files = sorted(
        (p for p in pkg_dir.rglob("*.py") if "__pycache__" not in p.parts),
        key=lambda p: p.relative_to(base).as_posix(),
    )
    for p in files:
        rel = p.relative_to(base).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _jsonable(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, np.ndarray):
            out[k] = v.tolist()
        elif isinstance(v, np.floating):
            out[k] = float(v)
        elif isinstance(v, np.integer):
            out[k] = int(v)
        else:
            out[k] = v
    return out


class RunRecorder:
    def __init__(self, root: str | Path, config: RunConfig, run_id: str | None = None,
                 subdir: str | None = None):
        self.config = config
        root = Path(root)
        if run_id is None:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            run_id = f"{ts}_{config.name}_{config.config_hash()[:8]}"
        self.run_id = run_id
        run_dir = root / run_id
        if subdir:
            run_dir = run_dir / subdir
        self.run_dir = run_dir

        manifest_path = self.run_dir / "manifest.json"
        if manifest_path.exists():
            raise FileExistsError(f"manifest already exists at {manifest_path}")

        (self.run_dir / "series").mkdir(parents=True, exist_ok=True)
        config.to_json(self.run_dir / "config.json")

        self._events_path = self.run_dir / "events.jsonl"
        self._events_file = open(self._events_path, "a", encoding="utf-8")
        self._buffers: dict[str, dict[str, list]] = {}
        self._chunk_idx: dict[str, int] = {}
        self._seed_log: list[dict] = []
        self._t_start_wall = time.time()
        self._closed = False

    def log_seed(self, name: str, keys: tuple[str, ...]) -> None:
        self._seed_log.append({"name": name, "master_seed": self.config.master_seed, "keys": list(keys)})

    def log(self, stream: str, t: float, **fields: Any) -> None:
        buf = self._buffers.setdefault(stream, {"t": []})
        buf["t"].append(float(t))
        for k, v in fields.items():
            arr = np.asarray(v, dtype=float)
            buf.setdefault(k, []).append(arr)
        if len(buf["t"]) >= CHUNK_ROWS:
            self._flush_stream(stream)

    def log_event(self, t: float, kind: str, **data: Any) -> None:
        rec = {"t": float(t), "kind": kind}
        rec.update(_jsonable(data))
        self._events_file.write(json.dumps(rec) + "\n")
        self._events_file.flush()

    def _flush_stream(self, stream: str) -> None:
        buf = self._buffers.get(stream)
        if not buf or not buf["t"]:
            return
        idx = self._chunk_idx.get(stream, 0)
        out = {"t": np.array(buf["t"])}
        for k, v in buf.items():
            if k == "t":
                continue
            out[k] = np.stack(v, axis=0)
        path = self.run_dir / "series" / f"{stream}.{idx:05d}.npz"
        np.savez(path, **out)
        self._chunk_idx[stream] = idx + 1
        self._buffers[stream] = {"t": []}

    def flush(self) -> None:
        for stream in list(self._buffers):
            self._flush_stream(stream)

    def close(self, status: str = "ok") -> None:
        if self._closed:
            return
        self.flush()
        manifest = {
            "run_id": self.run_id,
            "config_hash": self.config.config_hash(),
            "code_version": code_version(),
            "contract_version": CONTRACT_VERSION,
            "python": sys.version,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": _platform.platform(),
            "seeds": self._seed_log,
            "t_start_wall": self._t_start_wall,
            "t_end_wall": time.time(),
            "status": status,
        }
        try:
            import torch
            manifest["torch"] = torch.__version__
        except ImportError:
            pass
        (self.run_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        self._events_file.close()
        self._closed = True

    def __enter__(self) -> "RunRecorder":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None:
            self.close(status=f"error: {exc_type.__name__}")
        else:
            self.close(status="ok")
        return False


def save_trajectory(rec: RunRecorder, traj: TruthTrajectory, stream: str = "truth") -> None:
    """Bulk-write a whole TruthTrajectory to chunked npz files (faster than per-sample log())."""
    N = len(traj)
    idx = rec._chunk_idx.get(stream, 0)
    for start in range(0, max(N, 1), CHUNK_ROWS):
        end = min(start + CHUNK_ROWS, N)
        if end <= start:
            break
        out = {
            "t": traj.t[start:end], "pos": traj.pos[start:end], "vel": traj.vel[start:end],
            "acc": traj.acc[start:end], "att": traj.att[start:end],
            "omega_b": traj.omega_b[start:end], "f_b": traj.f_b[start:end],
        }
        path = rec.run_dir / "series" / f"{stream}.{idx:05d}.npz"
        np.savez(path, **out)
        idx += 1
    rec._chunk_idx[stream] = idx


@dataclass
class RunData:
    config: RunConfig
    manifest: dict
    series: dict[str, dict[str, np.ndarray]]
    events: list[dict]


def load_run(run_dir: str | Path) -> RunData:
    run_dir = Path(run_dir)
    config = RunConfig.from_json(run_dir / "config.json")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("config_hash") != config.config_hash():
        raise ValueError("config hash mismatch between config.json and manifest.json")

    series: dict[str, dict[str, np.ndarray]] = {}
    series_dir = run_dir / "series"
    if series_dir.exists():
        by_stream: dict[str, list[Path]] = {}
        for f in series_dir.glob("*.npz"):
            stream = f.name.rsplit(".", 2)[0]
            by_stream.setdefault(stream, []).append(f)
        for stream, files in by_stream.items():
            files.sort(key=lambda p: p.name)
            arrs: dict[str, list[np.ndarray]] = {}
            for f in files:
                with np.load(f) as data:
                    for k in data.files:
                        arrs.setdefault(k, []).append(data[k])
            series[stream] = {k: np.concatenate(v, axis=0) for k, v in arrs.items()}

    events: list[dict] = []
    events_path = run_dir / "events.jsonl"
    if events_path.exists():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))

    return RunData(config=config, manifest=manifest, series=series, events=events)
