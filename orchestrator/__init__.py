"""
Lightweight DAG orchestrator.

Trade-off: Airflow / Prefect are heavy for a single-service ingestor.
This module gives us the same shape — DAG of tasks, dependency edges,
idempotent retries, JSON state files per run, observable history — in
a few hundred lines, driven by cron instead of a separate scheduler
process.

Entry points:

  python manage.py run_dag <dag_name>   one-shot run, cron-friendly
  python manage.py dag_runs [--dag X]   list recent runs and statuses
  python manage.py retry_dag <run_id>   resume a failed run from the
                                        last failed task (idempotent)

State lives in DAG_RUNS_DIR (defaults to BASE_DIR / 'runs') and is
just JSON, so it's trivially inspectable and survives process
restarts.
"""

from .dag import DAG, Task  # noqa: F401
from .runner import RunResult, run_dag  # noqa: F401
