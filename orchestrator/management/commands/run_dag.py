"""
Trigger a DAG run.

  python manage.py run_dag daily_aggregation
  python manage.py run_dag daily_aggregation --dry-run
"""

from django.core.management.base import BaseCommand, CommandError

from orchestrator.dag import known_dags
from orchestrator.runner import run_dag


class Command(BaseCommand):
    help = 'Run a DAG once. Cron-friendly entry point.'

    def add_arguments(self, parser):
        parser.add_argument('dag_name')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        name = options['dag_name']
        if name not in known_dags():
            raise CommandError(f'unknown DAG {name!r}; known: {known_dags()}')

        result = run_dag(name, dry_run=options['dry_run'])

        style = self.style.SUCCESS if result.status == 'success' else self.style.WARNING
        self.stdout.write(style(f'{result.run_id} -> {result.status}'))
        if result.failed_task:
            self.stdout.write(self.style.ERROR(f'failed at: {result.failed_task}'))
