"""
Retry a failed DAG run from the last failed task. Idempotent — tasks
already marked `success` are skipped.

  python manage.py retry_dag daily_aggregation/2026-05-26T12-00-00Z
"""

from django.core.management.base import BaseCommand, CommandError

from orchestrator.runner import retry_run


class Command(BaseCommand):
    help = 'Retry a failed DAG run from the last failed task.'

    def add_arguments(self, parser):
        parser.add_argument('run_id')

    def handle(self, *args, **options):
        try:
            result = retry_run(options['run_id'])
        except FileNotFoundError as exc:
            raise CommandError(f'unknown run id: {exc}') from exc

        self.stdout.write(self.style.SUCCESS(
            f'{result.run_id} -> {result.status}'
            + (f' (failed at {result.failed_task})' if result.failed_task else '')
        ))
