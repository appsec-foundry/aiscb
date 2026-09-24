#!/usr/bin/env python3
"""Exercise policy delivery and scoring locally, without an assistant."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('organization', HERE / 'organization.py')
ORG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ORG)


class OrganizationTests(unittest.TestCase):
    def test_dry_run_never_calls_an_assistant(self):
        with patch.object(ORG.RUNNER, 'run_capture', side_effect=AssertionError('model call')):
            with patch('sys.argv', ['organization.py', '--dry-run']):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(ORG.main(), 0)

    def test_loader_cli_works_with_spaces_in_paths(self):
        with tempfile.TemporaryDirectory(prefix='organization test ') as tmp:
            state = ORG.prepare(Path(tmp), 'matching', 'claude')
            rc, out, _ = ORG.RUNNER.run_capture(
                [ORG.sys.executable, str(HERE / 'organization.py'), '--load',
                 str(state['policy'] / 'config.json'), 'access-pack'],
                state['workdir'], 5)
            self.assertEqual(rc, 0)
            self.assertIn('access-blueprint', out)
            self.assertTrue((state['policy'] / 'events.jsonl').is_file())

    def load(self, state, artifact):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = ORG.load_policy(state['policy'] / 'config.json', artifact)
        return rc, out.getvalue()

    def implement(self, state, *, tenant=True, known_group=True):
        source = ORG.SOURCE
        scenario = state['scenario']
        if scenario == 'overlay':
            condition = 'identity && r.userId === identity.userId'
            if tenant:
                condition += ' && r.tenantId === identity.tenantId'
            source = source.replace('=> [];', f'=> rows.filter(r => {condition});')
        if scenario == 'matching':
            group = json.dumps(state['group'] if known_group else 'invented-group')
            source = source.replace('claims => false',
                'claims => Boolean(claims && Array.isArray(claims.organization_groups) '
                f'&& claims.organization_groups.includes({group}))')
        if scenario in ('missing', 'unrelated'):
            source = source.replace('value.toLowerCase()', 'value.trim().toLowerCase()')
        (state['workdir'] / 'service.cjs').write_text(source)

    def test_each_scenario_accepts_correct_behavior(self):
        for scenario in ORG.SCENARIOS:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                state = ORG.prepare(Path(tmp), scenario, 'claude')
                if scenario in ('matching', 'missing'):
                    self.assertEqual(self.load(state, 'access-pack')[0], 0)
                    self.assertEqual(self.load(state, 'access-blueprint')[0],
                                     1 if scenario == 'missing' else 0)
                self.implement(state)
                self.assertTrue(ORG.evaluate(state)['passed'])

    def test_overlay_does_not_eagerly_include_pack_or_blueprint(self):
        for tool in ORG.RUNNER.ADAPTERS:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as tmp:
                state = ORG.prepare(Path(tmp), 'matching', tool)
                path = state['workdir'] / (
                    '.claude/rules/organization.md' if tool == 'claude' else 'AGENTS.md')
                instructions = path.read_text()
                self.assertIn('fixture-org-1.0.0', instructions)
                self.assertIn(ORG.RUNNER.baseline_identifier(), instructions)
                self.assertIn('--load', instructions)
                self.assertNotIn(state['group'], instructions)
                self.assertNotIn('organization_groups', instructions)
                self.assertNotIn((state['policy'] / 'access-pack').read_text(), instructions)

    def test_overlay_detects_missing_tenant_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = ORG.prepare(Path(tmp), 'overlay', 'claude')
            self.implement(state, tenant=False)
            self.assertFalse(ORG.evaluate(state)['checks']['application_behavior'])

    def test_matching_case_rejects_non_delivery_and_invented_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = ORG.prepare(Path(tmp), 'matching', 'claude')
            for artifact in ORG.ARTIFACTS:
                self.load(state, artifact)
            self.assertFalse(ORG.evaluate(state)['passed'])
            self.implement(state, known_group=False)
            self.assertFalse(ORG.evaluate(state)['passed'])

    def test_loader_checks_digest_missing_content_and_artifact_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = ORG.prepare(Path(tmp), 'matching', 'claude')
            for artifact in ['../config.json', '/etc/passwd', 'unknown']:
                self.assertEqual(self.load(state, artifact), (1, ''))
            pack = state['policy'] / 'access-pack'
            pack.write_text('unreviewed replacement')
            self.assertEqual(self.load(state, 'access-pack'), (1, ''))
            pack.unlink()
            self.assertEqual(self.load(state, 'access-pack'), (1, ''))

    def test_loader_rejects_oversized_and_symlinked_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = ORG.prepare(Path(tmp), 'matching', 'claude')
            pack = state['policy'] / 'access-pack'
            pack.write_text('x' * 32769)
            config_path = state['policy'] / 'config.json'
            config = state['config']
            config['manifest']['access-pack'] = ORG.digest(pack)
            config_path.write_text(json.dumps(config))
            self.assertEqual(self.load(state, 'access-pack'), (1, ''))
            pack.unlink()
            pack.symlink_to(state['policy'] / 'access-blueprint')
            self.assertEqual(self.load(state, 'access-pack'), (1, ''))

    def test_blueprint_rejects_wrong_schema_even_with_matching_digest(self):
        for content in ['[]', '{"claim":"organization_groups","approved_group":4}',
                        '{"claim":"organization_groups","claim":"other"}',
                        '{"claim":"organization_groups","approved_group":"x","extra":true}']:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                state = ORG.prepare(Path(tmp), 'matching', 'claude')
                path = state['policy'] / 'access-blueprint'
                path.write_text(content)
                config = state['config']
                config['manifest']['access-blueprint'] = ORG.digest(path)
                (state['policy'] / 'config.json').write_text(json.dumps(config))
                self.assertEqual(self.load(state, 'access-blueprint'), (1, ''))

    def test_malformed_load_records_fail_instead_of_passing(self):
        for content in ['not json', '[]', '{}', 'x' * 100_001]:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                state = ORG.prepare(Path(tmp), 'unrelated', 'claude')
                self.implement(state)
                (state['policy'] / 'events.jsonl').write_text(content)
                self.assertFalse(ORG.evaluate(state)['passed'])
    def test_loading_after_edit_or_not_loading_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = ORG.prepare(Path(tmp), 'matching', 'claude')
            self.implement(state)
            self.assertFalse(ORG.evaluate(state)['checks']['selected_packs'])
            for artifact in ORG.ARTIFACTS:
                self.load(state, artifact)
            result = ORG.evaluate(state)
            self.assertTrue(result['checks']['application_behavior'])
            self.assertFalse(result['checks']['loaded_before_edit'])

    def test_unrelated_case_detects_unnecessary_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = ORG.prepare(Path(tmp), 'unrelated', 'claude')
            self.load(state, 'access-pack')
            self.implement(state)
            self.assertFalse(ORG.evaluate(state)['passed'])

    def test_missing_policy_requires_independent_task_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = ORG.prepare(Path(tmp), 'missing', 'claude')
            for artifact in ORG.ARTIFACTS:
                self.load(state, artifact)
            self.assertFalse(ORG.evaluate(state)['passed'])
            self.implement(state)
            self.assertTrue(ORG.evaluate(state)['passed'])
            source = state['workdir'] / 'service.cjs'
            source.write_text(source.read_text().replace('claims => false', 'claims => true'))
            self.assertFalse(ORG.evaluate(state)['passed'])

    def test_oversized_loader_config_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = ORG.prepare(Path(tmp), 'matching', 'claude')
            (state['policy'] / 'config.json').write_text(' ' * 8193)
            rc, out = self.load(state, 'access-pack')
            self.assertEqual((rc, out), (1, ''))
            self.assertFalse((state['policy'] / 'events.jsonl').exists())

    def test_load_record_without_a_named_artifact_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = ORG.prepare(Path(tmp), 'unrelated', 'claude')
            record = {'artifact': 7, 'ok': True, 'source_hash': '0' * 64}
            (state['policy'] / 'events.jsonl').write_text(json.dumps(record) + '\n')
            self.assertEqual(ORG.evaluate(state),
                             {'passed': False, 'checks': {'valid_load_evidence': False}})


class OrganizationMainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'evidence'

    def evidence_root(self, prefix):
        self.root.mkdir()
        return str(self.root)

    def main(self, *argv, which='/usr/bin/tool', probes=None, runs=None):
        out, err = io.StringIO(), io.StringIO()
        runs = list(runs or [])
        calls = []

        def run_capture(cmd, cwd, timeout):
            calls.append(cmd)
            # Oracle calls always pass; agent calls return the scripted result.
            return (0, '', '') if cmd[0] == 'node' else runs.pop(0)

        preflight = patch.object(ORG.RUNNER, 'preflight',
                                 side_effect=probes if isinstance(probes, Exception) else None,
                                 return_value=probes if not isinstance(probes, Exception) else None)
        with patch('sys.argv', ['organization.py', *argv]), \
             patch.object(ORG.shutil, 'which', return_value=which), \
             preflight as preflight_mock, \
             patch.object(ORG.RUNNER, 'run_capture', side_effect=run_capture), \
             patch.object(ORG.tempfile, 'mkdtemp', side_effect=self.evidence_root), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = ORG.main()
            except SystemExit as exit:
                code = exit.code
        return code, out.getvalue(), err.getvalue(), calls, preflight_mock

    def test_invalid_selection_or_missing_cli_starts_nothing(self):
        for argv in (('--cases', 'unknown'), ('--cases', 'overlay,overlay'),
                     ('--timeout', '0'), ('--timeout', '901')):
            code, _, _, calls, preflight = self.main(*argv)
            self.assertEqual(code, 2, argv)
            self.assertEqual(calls, [])
            preflight.assert_not_called()
        code, _, err, _, _ = self.main('--cases', 'overlay', which=None)
        self.assertEqual(code, 2)
        self.assertIn('claude CLI not found on PATH', err)

    def test_quota_or_failed_preflight_stops_before_cases(self):
        code, _, err, calls, _ = self.main('--cases', 'overlay',
                                           probes=ORG.RUNNER.QuotaExhausted())
        self.assertEqual((code, calls), (1, []))
        self.assertIn('quota exhausted', err)
        code, _, err, calls, _ = self.main('--cases', 'overlay', probes=[{'ok': False}])
        self.assertEqual((code, calls), (1, []))
        self.assertIn('Baseline preflight failed', err)

    def test_cases_run_in_fresh_fixtures_and_write_results(self):
        code, out, _, calls, _ = self.main('--cases', 'unrelated', probes=[{'ok': True}],
                                           runs=[(0, 'agent output', '')])
        self.assertEqual(code, 0, out)
        self.assertIn('unrelated: pass', out)
        self.assertEqual(calls[0][0], 'claude')
        report = json.loads((self.root / 'results.json').read_text())
        self.assertEqual(report['expected_runs'], 1)
        self.assertTrue(report['runs'][0]['passed'] and report['runs'][0]['complete'])
        self.assertEqual((self.root / 'unrelated/agent.log').read_text(), 'agent output')

    def test_quota_during_a_case_stops_the_matrix_and_fails(self):
        code, out, _, calls, _ = self.main('--cases', 'unrelated,overlay',
                                           probes=[{'ok': True}],
                                           runs=[(1, '', 'Usage limit reached')])
        self.assertEqual(code, 1)
        self.assertIn('unrelated: incomplete', out)
        self.assertEqual(len([c for c in calls if c[0] != 'node']), 1)
        report = json.loads((self.root / 'results.json').read_text())
        self.assertEqual(len(report['runs']), 1)

    def test_load_flag_runs_the_loader_instead_of_cases(self):
        with patch.object(ORG, 'load_policy', return_value=0) as load:
            code = self.main('--load', '/nonexistent/config.json', 'access-pack')[0]
        self.assertEqual(code, 0)
        load.assert_called_once_with(Path('/nonexistent/config.json'), 'access-pack')


if __name__ == '__main__':
    unittest.main()
