#!/usr/bin/env python3
"""Check modular fixtures and failure-sensitive scoring without model calls."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('routing', HERE / 'routing.py')
ROUTING = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROUTING)

RESET_IMPL = '''(record, userId, now) => Boolean(record &&
    typeof userId === 'string' && userId.length > 0 && record.userId === userId &&
    Number.isFinite(now) && Number.isFinite(record.expiresAt) &&
    record.expiresAt > now && record.used === false)'''
CALL_IMPL = '''(request, identity, row) => {
    if (!request || !identity || !row || request.method !== 'tools/call' ||
        request.tool !== 'read_order' || !Number.isSafeInteger(request.id) ||
        request.id <= 0 || request.id !== row.id ||
        typeof identity.userId !== 'string' || !identity.userId ||
        typeof identity.tenantId !== 'string' || !identity.tenantId ||
        identity.userId !== row.ownerId || identity.tenantId !== row.tenantId)
        return {error: 'denied'};
    return {result: {id: row.id, total: row.total}};
}'''


class RoutingTests(unittest.TestCase):
    def prepare(self, scenario='semantic', tool='claude'):
        tmp = tempfile.TemporaryDirectory(prefix='routing test ')
        self.addCleanup(tmp.cleanup)
        return ROUTING.prepare(Path(tmp.name), scenario, tool)

    def load(self, state, ids):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = ROUTING.load_policy(state['config_path'], ids)
        return code, out.getvalue()

    def implement(self, state, phase=0):
        scenario = state['scenario']
        path = state['workdir'] / 'src/routes/account.cjs'
        if scenario == 'missing' or (scenario == 'scope-change' and phase == 0):
            (state['workdir'] / 'README.md').write_text('# Account recovery\n')
            return
        call = scenario == 'multiple' or (scenario == 'context-loss' and phase == 1)
        source = path.read_text()
        if call:
            source = source.replace("(request, identity, row) => ({error: 'denied'})", CALL_IMPL)
        else:
            source = source.replace('(record, userId, now) => false', RESET_IMPL)
        path.write_text(source)

    def ids(self, scenario, phase):
        if scenario == 'scope-change' and phase == 0:
            return []
        if scenario == 'multiple' or (scenario == 'context-loss' and phase == 1):
            # DATA must arrive through the actual MCP dependency, not a stub.
            return [ROUTING.MCP, ROUTING.WEB]
        return [ROUTING.WEB, ROUTING.DATA, ROUTING.SECRETS]

    def test_all_scenarios_accept_correct_loading_and_behavior(self):
        for scenario in ROUTING.SCENARIOS:
            with self.subTest(scenario=scenario):
                state = self.prepare(scenario)
                for phase in range(len(state['prompts'])):
                    before = ROUTING.hashes(state['workdir'])
                    offset = len(ROUTING.read_events(state))
                    ids = self.ids(scenario, phase)
                    if ids:
                        code, output = self.load(state, ids)
                        self.assertEqual(code, 1 if scenario == 'missing' else 0)
                        if scenario == 'missing':
                            self.assertEqual(output, '')
                    self.implement(state, phase)
                    self.assertTrue(ROUTING.evaluate(state, phase, before, offset)['passed'])

    def test_real_installer_initial_context_contains_no_module_bodies(self):
        for tool in ROUTING.RUNNER.ADAPTERS:
            with self.subTest(tool=tool):
                state = self.prepare(tool=tool)
                initial = (state['workdir'] / ROUTING.install_policy.ENTRY_POINTS[tool]).read_text()
                self.assertIn('Installation mode: modular', initial)
                self.assertIn(ROUTING.MCP, initial)
                self.assertIn('--load', initial)
                self.assertNotIn('[aiscb-MCPAUTH-001]', initial)
                self.assertNotIn('[aiscb-AUTH-001]', initial)

    def test_loader_resolves_real_dependencies_and_records_before_output(self):
        state = self.prepare('multiple')
        code, output = self.load(state, [ROUTING.MCP, ROUTING.WEB])
        self.assertEqual(code, 0)
        self.assertIn('[aiscb-MCPAUTH-001]', output)
        event = ROUTING.read_events(state)[0]
        self.assertEqual(event['delivered'], [ROUTING.DATA, ROUTING.MCP, ROUTING.WEB])
        self.assertEqual(event['hashes'], ROUTING.hashes(state['workdir']))

    def test_cli_loader_handles_spaces_and_rejects_unknown_ids(self):
        state = self.prepare()
        command = [ROUTING.sys.executable, str(HERE / 'routing.py'), '--load',
                   str(state['config_path']), ROUTING.WEB]
        code, out, _ = ROUTING.RUNNER.run_capture(command, state['workdir'], 10)
        self.assertEqual(code, 0)
        self.assertIn('[aiscb-AUTH-001]', out)
        self.assertEqual(self.load(state, ['../untrusted']), (1, ''))

    def test_no_load_and_late_load_fail_despite_correct_code(self):
        state = self.prepare()
        before = ROUTING.hashes(state['workdir'])
        self.implement(state)
        result = ROUTING.evaluate(state, 0, before, 0)
        self.assertTrue(result['checks']['application_behavior'])
        self.assertFalse(result['passed'])
        self.load(state, self.ids('semantic', 0))
        result = ROUTING.evaluate(state, 0, before, 0)
        self.assertTrue(result['checks']['required_modules'])
        self.assertFalse(result['checks']['loaded_before_edit'])

    def test_multiple_rejects_missing_match_and_missing_dependency_evidence(self):
        for omitted in (ROUTING.WEB, ROUTING.DATA):
            with self.subTest(omitted=omitted):
                state = self.prepare('multiple')
                before = ROUTING.hashes(state['workdir'])
                self.load(state, self.ids('multiple', 0))
                path = state['root'] / 'loads.jsonl'
                event = json.loads(path.read_text())
                event['delivered'].remove(omitted)
                path.write_text(json.dumps(event) + '\n')
                self.implement(state)
                self.assertFalse(ROUTING.evaluate(state, 0, before, 0)['passed'])

    def test_scope_change_rejects_eager_loading_and_rechecks_new_scope(self):
        state = self.prepare('scope-change')
        before = ROUTING.hashes(state['workdir'])
        self.load(state, [ROUTING.WEB])
        self.implement(state)
        self.assertFalse(ROUTING.evaluate(state, 0, before, 0)['passed'])
        before = ROUTING.hashes(state['workdir'])
        offset = len(ROUTING.read_events(state))
        self.implement(state, 1)
        self.assertFalse(ROUTING.evaluate(state, 1, before, offset)['passed'])

    def test_fresh_session_cannot_reuse_previous_load_evidence(self):
        state = self.prepare('context-loss')
        # Even eager loading of all modules in phase 1 cannot satisfy phase 2.
        self.load(state, [ROUTING.MCP, ROUTING.WEB, ROUTING.SECRETS])
        self.implement(state)
        before, offset = ROUTING.hashes(state['workdir']), len(ROUTING.read_events(state))
        self.implement(state, 1)
        result = ROUTING.evaluate(state, 1, before, offset)
        self.assertTrue(result['checks']['application_behavior'])
        self.assertFalse(result['checks']['required_modules'])

    def test_oracle_rejects_cross_user_tenant_and_expiry_bypasses(self):
        for scenario, old, new in [
            ('semantic', 'record.userId === userId', 'true'),
            ('semantic', 'record.expiresAt > now', 'true'),
            ('multiple', 'identity.tenantId !== row.tenantId', 'false'),
            ('multiple', 'identity.userId !== row.ownerId', 'false'),
        ]:
            with self.subTest(scenario=scenario, bypass=old):
                state = self.prepare(scenario)
                before = ROUTING.hashes(state['workdir'])
                self.load(state, self.ids(scenario, 0))
                self.implement(state)
                path = state['workdir'] / 'src/routes/account.cjs'
                self.assertIn(old, path.read_text())
                path.write_text(path.read_text().replace(old, new))
                self.assertFalse(ROUTING.evaluate(state, 0, before, 0)['checks']['application_behavior'])

    def test_missing_requires_failed_load_unchanged_code_and_independent_fix(self):
        state = self.prepare('missing')
        before = ROUTING.hashes(state['workdir'])
        self.assertFalse(ROUTING.evaluate(state, 0, before, 0)['passed'])
        self.load(state, [ROUTING.WEB])
        self.assertFalse(ROUTING.evaluate(state, 0, before, 0)['passed'])
        self.implement(state)
        self.assertTrue(ROUTING.evaluate(state, 0, before, 0)['passed'])
        path = state['workdir'] / 'src/routes/account.cjs'
        path.write_text(path.read_text().replace('=> false', '=> true'))
        self.assertFalse(ROUTING.evaluate(state, 0, before, 0)['passed'])

    def test_corrupt_or_malformed_evidence_fails_closed(self):
        for content in ('invalid', '[]', '{}', '{"ok":true}', 'x' * 1_048_577):
            with self.subTest(content=content[:30]):
                state = self.prepare()
                before = ROUTING.hashes(state['workdir'])
                (state['root'] / 'loads.jsonl').write_text(content)
                self.assertFalse(ROUTING.evaluate(state, 0, before, 0)['passed'])
        state = self.prepare()
        path = Path(state['config']['snapshot']) / 'modules/aiscb-web-auth-crypto.md'
        path.write_text(path.read_text() + '\ntampered\n')
        self.assertEqual(self.load(state, [ROUTING.WEB]), (1, ''))

    def test_scope_continues_but_context_loss_starts_fresh(self):
        args = types.SimpleNamespace(model=None, timeout=10)
        for scenario, expected in [('scope-change', [1, 2]), ('context-loss', [1, 1])]:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                adapter = ROUTING.RUNNER.ADAPTERS['claude']
                with patch.dict(adapter, {'cmd': lambda work, prompt, model, turn: [str(turn)]}):
                    with patch.object(ROUTING.RUNNER, 'run_capture', return_value=(0, '', '')) as run:
                        with patch.object(ROUTING, 'evaluate', return_value={'passed': True, 'checks': {}}):
                            result = ROUTING.run_case(Path(tmp), scenario, 'claude', args)
                self.assertTrue(result['passed'])
                self.assertEqual([int(c.args[0][0]) for c in run.call_args_list], expected)

    def test_dry_run_calls_no_model_and_reports_cost(self):
        with patch.object(ROUTING.RUNNER, 'run_capture', side_effect=AssertionError('model call')):
            with patch('sys.argv', ['routing.py', '--dry-run']):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(ROUTING.main(), 0)
                self.assertIn('7 agent turns', out.getvalue())

    def test_oracle_cannot_read_host_files_or_write_fixture(self):
        state = self.prepare()
        outside = state['root'] / 'host-only.txt'
        outside.write_text('synthetic marker')
        before = ROUTING.hashes(state['workdir'])
        self.load(state, self.ids('semantic', 0))
        self.implement(state)
        path = state['workdir'] / 'src/routes/account.cjs'
        boundary_checks = '''
const fs = require('node:fs');
const assert = require('node:assert/strict');
assert.throws(() => fs.readFileSync(HOST_PATH));
assert.throws(() => fs.writeFileSync('/work/unexpected.txt', 'write'));
assert.equal(process.env.AISCB_ROUTING_TEST_MARKER, undefined);
'''.replace('HOST_PATH', json.dumps(str(outside)))
        path.write_text(path.read_text() + boundary_checks)
        with patch.dict('os.environ', {'AISCB_ROUTING_TEST_MARKER': 'synthetic marker'}):
            self.assertTrue(ROUTING.evaluate(state, 0, before, 0)['passed'])
        self.assertFalse((state['workdir'] / 'unexpected.txt').exists())

    def test_unavailable_sandbox_cannot_pass_behavior_check(self):
        state = self.prepare()
        before = ROUTING.hashes(state['workdir'])
        self.load(state, self.ids('semantic', 0))
        self.implement(state)
        with patch.object(ROUTING.RUNNER, 'run_capture', return_value=(1, '', 'sandbox refused')):
            self.assertFalse(ROUTING.evaluate(state, 0, before, 0)['passed'])


if __name__ == '__main__':
    unittest.main()
