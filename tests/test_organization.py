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


if __name__ == '__main__':
    unittest.main()
