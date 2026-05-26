"""
JSON state files for DAG runs.

Layout:
  runs/
    <dag_name>/
      <utc_timestamp>.json

Each file has the shape:

  {
    "dag": "daily_aggregation",
    "run_id": "daily_aggregation/2026-05-26T12-00-00Z",
    "started_at": "...",
    "finished_at": "...",
    "status": "success" | "failed" | "running",
    "tasks": {
        "task_a": {"status": "success", "started_at": "...", ...},
        "task_b": {"status": "failed",  "error": "...", "traceback": "..."},
    },
    "context": {...}   # rolling context dict the tasks read/write
  }

Running the same DAG again (without --retry) creates a new file.
Retrying a run rewrites the existing file so the audit trail collapses
into "one row per run, last status wins" — which matches how teams
actually reason about retries.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.conf import settings


def runs_dir() -> Path:
    base = Path(getattr(settings, 'DAG_RUNS_DIR', settings.BASE_DIR / 'runs'))
    base.mkdir(parents=True, exist_ok=True)
    return base


def make_run_id(dag_name: str) -> str:
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')
    return f'{dag_name}/{ts}'


def run_path(run_id: str) -> Path:
    dag, ts = run_id.split('/', 1)
    d = runs_dir() / dag
    d.mkdir(parents=True, exist_ok=True)
    return d / f'{ts}.json'


def write_state(run_id: str, state: dict[str, Any]) -> None:
    path = run_path(run_id)
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(state, indent=2, default=str))
    os.replace(tmp, path)  # atomic on POSIX


def read_state(run_id: str) -> dict[str, Any]:
    path = run_path(run_id)
    if not path.exists():
        raise FileNotFoundError(run_id)
    return json.loads(path.read_text())


def list_runs(dag: str | None = None, limit: int = 25) -> list[dict]:
    base = runs_dir()
    out: list[dict] = []
    dirs = [base / dag] if dag else sorted(p for p in base.iterdir() if p.is_dir())
    for d in dirs:
        if not d.exists():
            continue
        for f in sorted(d.glob('*.json'), reverse=True):
            try:
                out.append(json.loads(f.read_text()))
            except json.JSONDecodeError:
                continue
            if len(out) >= limit:
                return out
    return out
