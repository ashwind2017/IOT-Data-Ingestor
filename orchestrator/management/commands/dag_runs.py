"""
List recent DAG runs and statuses.

  python manage.py dag_runs
  python manage.py dag_runs --dag daily_aggregation
  python manage.py dag_runs --limit 50
"""

from django.core.management.base import BaseCommand

from orchestrator.state import list_runs


STATUS_STYLES = {
    'success': lambda s: s,
    'failed': lambda s: s,
    'running': lambda s: s,
}


class Command(BaseCommand):
    help = 'List recent DAG runs (observability for the orchestrator).'

    def add_arguments(self, parser):
        parser.add_argument('--dag', default=None)
        parser.add_argument('--limit', type=int, default=25)

    def handle(self, *args, **options):
        runs = list_runs(dag=options['dag'], limit=options['limit'])
        if not runs:
            self.stdout.write('no runs found')
            return

        for r in runs:
            line = (
                f"{r['run_id']:60}  status={r['status']:8}  "
                f"started={r.get('started_at', '?')[:19]}  "
                f"finished={(r.get('finished_at') or '-')[:19]}"
            )
            self.stdout.write(line)

            failed = [n for n, t in r.get('tasks', {}).items() if t.get('status') == 'failed']
            for n in failed:
                err = r['tasks'][n].get('error', '')
                self.stdout.write(self.style.ERROR(f'  failed: {n} -- {err}'))
