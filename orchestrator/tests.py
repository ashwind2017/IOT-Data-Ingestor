"""
Orchestrator unit tests. Covers ordering, failure capture, retry
idempotency, and observability of state files.
"""

import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

from orchestrator.dag import DAG, Task
from orchestrator.runner import retry_run, run_dag
from orchestrator.state import list_runs, read_state


class DagPrimitivesTests(TestCase):
    def test_topological_order_simple(self):
        dag = DAG('t', [
            Task('a', lambda c: None),
            Task('b', lambda c: None, depends_on=['a']),
            Task('c', lambda c: None, depends_on=['b']),
        ])
        self.assertEqual(dag.topological_order(), ['a', 'b', 'c'])

    def test_cycle_detected(self):
        dag = DAG('t', [
            Task('a', lambda c: None, depends_on=['b']),
            Task('b', lambda c: None, depends_on=['a']),
        ])
        with self.assertRaisesRegex(ValueError, 'cycle'):
            dag.topological_order()

    def test_unknown_dep_rejected(self):
        dag = DAG('t', [Task('a', lambda c: None, depends_on=['ghost'])])
        with self.assertRaisesRegex(ValueError, 'unknown'):
            dag.topological_order()


class RunnerTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Apply override for the whole test method so writer + reader
        # agree on the runs directory.
        self._override = override_settings(DAG_RUNS_DIR=Path(self.tmpdir))
        self._override.enable()

    def tearDown(self):
        self._override.disable()

    def _patched_get_dag(self, dag):
        return mock.patch('orchestrator.runner.get_dag', return_value=dag)

    def test_success_path_persists_state(self):
        calls = []
        dag = DAG('happy', [
            Task('a', lambda c: calls.append('a') or {'a': 1}),
            Task('b', lambda c: calls.append('b') or {'b': c['a'] + 1}, depends_on=['a']),
        ])
        with self._patched_get_dag(dag):
            res = run_dag('happy')

        self.assertEqual(res.status, 'success')
        self.assertEqual(calls, ['a', 'b'])
        self.assertEqual(res.context, {'a': 1, 'b': 2})

        state = read_state(res.run_id)
        self.assertEqual(state['tasks']['a']['status'], 'success')
        self.assertEqual(state['tasks']['b']['status'], 'success')

    def test_failure_records_traceback_and_skips_downstream(self):
        def boom(ctx):
            raise RuntimeError('kaboom')

        dag = DAG('sad', [
            Task('a', lambda c: {'a': 1}),
            Task('b', boom, depends_on=['a']),
            Task('c', lambda c: {'c': 1}, depends_on=['b']),
        ])

        with self._patched_get_dag(dag):
            res = run_dag('sad')

        self.assertEqual(res.status, 'failed')
        self.assertEqual(res.failed_task, 'b')

        state = read_state(res.run_id)
        self.assertEqual(state['tasks']['a']['status'], 'success')
        self.assertEqual(state['tasks']['b']['status'], 'failed')
        self.assertIn('kaboom', state['tasks']['b']['error'])
        self.assertIn('Traceback', state['tasks']['b']['traceback'])
        self.assertEqual(state['tasks']['c']['status'], 'skipped')

    def test_retry_is_idempotent_and_resumes_from_failed_task(self):
        attempts = {'b': 0, 'a': 0}

        def a_fn(ctx):
            attempts['a'] += 1
            return {'a_done': True}

        def b_fn(ctx):
            attempts['b'] += 1
            if attempts['b'] == 1:
                raise RuntimeError('first try fails')
            return {'b_done': True}

        dag = DAG('retry_me', [
            Task('a', a_fn),
            Task('b', b_fn, depends_on=['a']),
            Task('c', lambda c: {'c_done': True}, depends_on=['b']),
        ])

        with self._patched_get_dag(dag):
            first = run_dag('retry_me')
            self.assertEqual(first.status, 'failed')

            retried = retry_run(first.run_id)
            self.assertEqual(retried.status, 'success')

        # Task `a` succeeded on first run and must not have re-executed.
        self.assertEqual(attempts['a'], 1)
        self.assertEqual(attempts['b'], 2)
        self.assertTrue(retried.context.get('a_done'))
        self.assertTrue(retried.context.get('b_done'))
        self.assertTrue(retried.context.get('c_done'))

    def test_list_runs_returns_recent(self):
        dag = DAG('observable', [Task('a', lambda c: None)])
        with self._patched_get_dag(dag):
            r1 = run_dag('observable')
            r2 = run_dag('observable')

        runs = list_runs(limit=10)
        run_ids = {r['run_id'] for r in runs}
        self.assertIn(r1.run_id, run_ids)
        self.assertIn(r2.run_id, run_ids)
