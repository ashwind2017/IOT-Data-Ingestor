"""
DAG runner.

Behavior:

* Resolves task order via Kahn's algorithm.
* For each task: marks running, calls fn(context), captures return into
  context, marks success / failed (with traceback) — and persists state
  after every status change so a crash is recoverable.
* Idempotent retry: on retry, tasks already marked "success" are
  skipped so re-running picks up exactly where the failure happened.
* A failed task aborts the run (downstream tasks marked "skipped").
* `dry_run=True` prints the order without executing.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .dag import DAG, get_dag
from .state import make_run_id, read_state, run_path, write_state


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunResult:
    run_id: str
    status: str
    failed_task: str | None
    context: dict[str, Any]


def run_dag(
    dag_name: str,
    *,
    run_id: str | None = None,
    context: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> RunResult:
    dag: DAG = get_dag(dag_name)
    order = dag.topological_order()
    task_map = dag.task_map()

    if run_id:
        # Resume path. Load existing state; preserve any task already
        # marked success so we don't re-run them.
        state = read_state(run_id)
        resumed = True
    else:
        run_id = make_run_id(dag_name)
        state = {
            'dag': dag_name,
            'run_id': run_id,
            'started_at': _now_iso(),
            'finished_at': None,
            'status': 'running',
            'tasks': {n: {'status': 'pending'} for n in order},
            'context': context or {},
        }
        resumed = False

    if dry_run:
        print(f'DRY RUN {run_id}')
        for n in order:
            print(f'  - {n} (depends_on={task_map[n].depends_on})')
        return RunResult(run_id=run_id, status='dry-run', failed_task=None, context={})

    write_state(run_id, state)

    failed_task: str | None = None

    for name in order:
        task_state = state['tasks'].setdefault(name, {'status': 'pending'})

        if task_state.get('status') == 'success':
            if resumed:
                # Idempotent skip — this task already succeeded in a
                # prior run.
                continue

        task_state.update({
            'status': 'running',
            'started_at': _now_iso(),
        })
        write_state(run_id, state)

        try:
            result = task_map[name].fn(state['context'])
            if isinstance(result, dict):
                state['context'].update(result)
            task_state.update({
                'status': 'success',
                'finished_at': _now_iso(),
            })
        except Exception as exc:  # noqa: BLE001 — orchestrator catches everything
            task_state.update({
                'status': 'failed',
                'finished_at': _now_iso(),
                'error': str(exc),
                'traceback': traceback.format_exc(),
            })
            failed_task = name
            write_state(run_id, state)
            break
        finally:
            write_state(run_id, state)

    if failed_task:
        # Anything downstream of the failure that hadn't started is
        # marked skipped so the run report is honest.
        for name in order:
            if state['tasks'][name]['status'] == 'pending':
                state['tasks'][name]['status'] = 'skipped'
        state['status'] = 'failed'
    else:
        state['status'] = 'success'

    state['finished_at'] = _now_iso()
    write_state(run_id, state)

    return RunResult(
        run_id=run_id,
        status=state['status'],
        failed_task=failed_task,
        context=state['context'],
    )


def retry_run(run_id: str) -> RunResult:
    """Retry a previously failed run from the last failed task."""
    state = read_state(run_id)
    if state['status'] == 'success':
        return RunResult(run_id, 'success', None, state['context'])

    # Reset failed + skipped tasks back to pending so they re-run.
    for name, ts in state['tasks'].items():
        if ts['status'] in ('failed', 'skipped'):
            state['tasks'][name] = {'status': 'pending'}
    state['status'] = 'running'
    state['finished_at'] = None
    write_state(run_id, state)

    return run_dag(state['dag'], run_id=run_id)
