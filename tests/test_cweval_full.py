#!/usr/bin/env python3
"""Full-profile boundary and metric tests; no credentials, API or Docker needed."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import tarfile
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import cweval_full as full


class FullTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for group, count in full.EXPECTED.items():
            lang = group.split('/')[1]
            directory = self.root / 'benchmark' / group
            directory.mkdir(parents=True)
            for i in range(count):
                name = f'cwe_{100 + i}_0' + (f'_{lang}' if lang != 'py' else '')
                comment = '#' if lang == 'py' else '//'
                (directory / f'{name}_task.{lang}').write_text(
                    f'{comment} BEGIN PROMPT\nfunction specification\n'
                    f'{comment} BEGIN SOLUTION\nREFERENCE_SECRET\n')
                (directory / f'{name}_test.py').write_text('TEST_SECRET\n')
        ppt = self.root / 'cweval/ppt'
        ppt.mkdir(parents=True)
        (ppt / '__init__.py').write_text(
            'raise RuntimeError("must never import")\n'
            'class DirectPrompt:\n'
            '    PPT = "Implement {lang_instr}{lang}: {code_prompt}"\n'
            '    LANG_INSTR = {"py":"Python ", "js":"JS ", "c":"C ", "cpp":"C++ ", "go":"Go "}\n')
        self.args = SimpleNamespace(api_url='https://api.example.com/v1/chat/completions',
                                    api_key_env='CWEVAL_TEST_KEY', model='model-snapshot',
                                    max_completion_tokens=2048, timeout=10, eval_timeout=30,
                                    image='co1lin/cweval@sha256:' + 'a' * 64)

    def test_all_languages_and_prompt_boundaries(self):
        selected = full.tasks(self.root)
        self.assertEqual(len(selected), 119)
        self.assertEqual({t['language'] for t in selected.values()}, {'py','c','cpp','js','go'})
        for task in selected.values():
            self.assertNotIn('REFERENCE_SECRET', task['prompt'])
            self.assertNotIn('TEST_SECRET', task['prompt'])
            self.assertEqual(len(task['task_sha256']), 64)
        # Upstream Go task has two solution markers; match its first-marker rule.
        p = self.root/'benchmark/core/go/cwe_100_0_go_task.go'
        p.write_text(p.read_text() + '// BEGIN SOLUTION\nOTHER_SECRET\n')
        self.assertNotIn('SECRET', full.tasks(self.root)[p.relative_to(self.root/'benchmark').as_posix()]['prompt'])

    def test_missing_task_or_test_and_symlinks_fail_closed(self):
        task = self.root/'benchmark/core/py/cwe_100_0_task.py'
        raw = task.read_bytes()
        task.unlink()
        with self.assertRaises(ValueError): full.tasks(self.root)
        task.symlink_to(self.root/'benchmark/core/py/cwe_101_0_task.py')
        with self.assertRaisesRegex(ValueError, 'linked'): full.tasks(self.root)
        task.unlink(); task.write_bytes(raw)
        (self.root/'benchmark/core/py/cwe_100_0_test.py').unlink()
        with self.assertRaises(ValueError): full.tasks(self.root)

    def test_prompt_literal_extraction_and_arm_separation(self):
        template, _ = full.prompt_template(self.root)
        task = next(iter(full.tasks(self.root).values()))
        control = full.messages(task, template)
        baseline = full.messages(task, template, 'BASELINE_MARKER')
        self.assertEqual(len(control), 1)
        self.assertEqual(control[0]['role'], 'user')
        self.assertEqual(baseline[1:], control)
        self.assertEqual(baseline[0], {'role':'system','content':'BASELINE_MARKER'})
        self.assertNotIn('BASELINE_MARKER', json.dumps(control))
        p = self.root/'cweval/ppt/__init__.py'
        p.write_text('class DirectPrompt:\n    PPT = str(open("secret"))\n')
        with self.assertRaises(ValueError): full.prompt_template(self.root)

    def test_endpoint_rejects_cleartext_credentials_query_and_controls(self):
        full.endpoint(self.args.api_url)
        for url in ['http://api.example.com/v1/chat/completions',
                    'https://user:password@api.example.com/v1/chat/completions',
                    'https://api.example.com/v1/chat/completions?key=secret',
                    'https://api.example.com/v1/chat/completions#fragment',
                    'https://api.example.com/\nv1/chat/completions',
                    'https://api.example.com:99999/v1/chat/completions',
                    'https://api.example.com/other']:
            with self.subTest(url=url), self.assertRaises(ValueError): full.endpoint(url)

    def response(self, content='```py\npass\n```', status=200, **message_extra):
        data = {'model':'resolved-model', 'choices':[{'finish_reason':'stop',
                'message': {'role':'assistant','content':content, **message_extra}}]}
        connection = MagicMock()
        response = connection.getresponse.return_value
        response.status = status
        response.read.return_value = json.dumps(data).encode()
        return connection

    def test_request_preserves_parameters_and_bounded_provenance(self):
        connection = self.response()
        with patch.dict(os.environ, {'CWEVAL_TEST_KEY':'artificial-test-value'}), \
             patch.object(full.http.client, 'HTTPSConnection', return_value=connection):
            content, meta = full.completion(self.args, [{'role':'user','content':'task'}])
        call = connection.request.call_args
        body = json.loads(call.args[2])
        self.assertEqual(body, {'model':'model-snapshot','messages':[{'role':'user','content':'task'}],
                               'n':1,'temperature':0.8,'max_completion_tokens':2048,'stream':False})
        self.assertNotIn('artificial-test-value', content + json.dumps(meta))
        self.assertEqual(meta['model'], 'resolved-model')
        connection.close.assert_called_once()
        connection.getresponse.return_value.read.assert_called_once_with(full.MAX_RESPONSE + 1)

    def test_refusals_are_not_resampled(self):
        connection = self.response(content=None, refusal='not allowed')
        with patch.dict(os.environ, {'CWEVAL_TEST_KEY':'artificial-test-value'}), \
             patch.object(full.http.client, 'HTTPSConnection', return_value=connection):
            content, _ = full.completion(self.args, [])
        self.assertEqual(content, '')
        connection.request.assert_called_once()

    def test_no_redirect_retry_tools_or_error_body_disclosure(self):
        for status, extra in [(302, {}), (400, {}), (429, {}), (200, {'tool_calls':[{'name':'exec'}]})]:
            connection = self.response(status=status, **extra)
            connection.getresponse.return_value.reason = 'ARTIFICIAL_SECRET'
            with self.subTest(status=status, extra=extra), \
                 patch.dict(os.environ, {'CWEVAL_TEST_KEY':'artificial-test-value'}), \
                 patch.object(full.http.client, 'HTTPSConnection', return_value=connection), \
                 self.assertRaises(RuntimeError) as caught:
                full.completion(self.args, [])
            self.assertNotIn('ARTIFICIAL_SECRET', str(caught.exception))
            connection.request.assert_called_once()

    def test_bad_api_schema_and_limits_fail_closed(self):
        for data in [{}, {'choices':[]}, {'choices':[{},{}]}, {'choices':[{'message':{'content':3}}]}]:
            connection = self.response()
            connection.getresponse.return_value.read.return_value = json.dumps(data).encode()
            with patch.dict(os.environ, {'CWEVAL_TEST_KEY':'artificial-test-value'}), \
                 patch.object(full.http.client, 'HTTPSConnection', return_value=connection), \
                 self.assertRaises(RuntimeError): full.completion(self.args, [])
        connection = self.response()
        connection.getresponse.return_value.read.return_value = b'x' * (full.MAX_RESPONSE + 1)
        with patch.dict(os.environ, {'CWEVAL_TEST_KEY':'artificial-test-value'}), \
             patch.object(full.http.client, 'HTTPSConnection', return_value=connection), \
             self.assertRaises(RuntimeError): full.completion(self.args, [])
        with patch.dict(os.environ, {'CWEVAL_TEST_KEY':''}), \
             patch.object(full.http.client, 'HTTPSConnection') as create, \
             self.assertRaises(ValueError): full.completion(self.args, [])
        create.assert_not_called()

    def test_raw_responses_and_archive_preserve_language_paths(self):
        selected = full.tasks(self.root)
        chosen = {key: value for key, value in selected.items() if 'cwe_100_0' in key}
        template, _ = full.prompt_template(self.root)
        result = self.root/'result'; result.mkdir()
        with patch.object(full, 'SAMPLES', 1), \
             patch.object(full, 'completion', return_value=('explanation\n```code\nvalue\n```', {})):
            full.generate(self.args, chosen, template, 'baseline', result)
        with full.sample_archive(result, 'baseline', 0, chosen) as stream, tarfile.open(fileobj=stream) as archive:
            names = archive.getnames()
            self.assertEqual(len(names), 6)
            self.assertIn('generated_0/lang/c/cwe_100_0_c_raw.c', names)
            for member in archive.getmembers():
                self.assertTrue(member.isfile())
                self.assertTrue(archive.extractfile(member).read().startswith(b'explanation'))
        target = result/'baseline/generated_0/core/py/cwe_100_0_raw.py'
        target.unlink(); target.symlink_to(self.root/'secret')
        with self.assertRaises(ValueError): full.sample_archive(result, 'baseline', 0, chosen)

    def test_container_keeps_compilation_and_tests_offline_and_bounded(self):
        cmd = full.container_command(self.root, self.args.image, 'own-name')
        for flag in ['--network=none','--read-only','--cap-drop=ALL',
                     '--security-opt=no-new-privileges','--user=1000:1000',
                     '--memory=2g','--cpus=2','--pids-limit=128','--pull=never']:
            self.assertIn(flag, cmd)
        self.assertNotIn('/var/run/docker.sock', ' '.join(cmd))
        self.assertNotIn('CWEVAL_TEST_KEY', ' '.join(cmd))
        self.assertIn('exec,size=1g', ' '.join(cmd))
        self.assertIn('GOPROXY=off', cmd[-1])
        self.assertIn('compile_all_in', full.container_command(self.root, self.args.image, 'own-name', True)[-1])

    def test_shell_stops_on_preflight_failure_and_envelope_python_is_valid(self):
        envelope_python = full.ENVELOPE.split("<<'END_ENVELOPE'\n", 1)[1].rsplit('\nEND_ENVELOPE', 1)[0]
        compile(envelope_python, '<envelope>', 'exec')
        with patch.object(full, 'BOOT', 'set -eu\nfalse\n'), \
             patch.object(full, 'REFERENCE', 'echo MUST_NOT_RUN\n'), \
             patch.object(full, 'ENVELOPE', 'printf "%s" "$code"\n'):
            script = full.container_command(self.root, self.args.image, 'unused', True)[-1]
        # Only this fixed synthetic shell fixture runs on the host.
        script = script.replace('/tmp/evaluation.log', str(self.root/'probe.log'))
        proc = subprocess.run(['/bin/sh', '-c', script], capture_output=True, text=True, check=True)
        self.assertEqual(proc.stdout, '1')
        self.assertNotIn('MUST_NOT_RUN', (self.root/'probe.log').read_text())

    def test_container_transport_bounds_output_and_runtime(self):
        with tempfile.TemporaryFile() as stream:
            rc, out, err = full.run_container(
                [sys.executable, '-c', 'print("bounded")'], stream, self.root, 5)
            self.assertEqual((rc, out, err), (0, 'bounded\n', ''))
            with patch.object(full, 'MAX_JSON', 100), self.assertRaisesRegex(RuntimeError, 'limit'):
                full.run_container([sys.executable, '-c', 'print("x" * 10000)'], stream, self.root, 5)
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                full.run_container([sys.executable, '-c', 'import time; time.sleep(10)'], stream, self.root, 0.1)

    def test_score_paths_keep_core_and_language_specific_cases_distinct(self):
        selected = {'core/c/cwe_100_0_c_task.c':{}, 'lang/c/cwe_100_0_c_task.c':{}}
        values = {'functional':[True], 'secure':[False], 'func_secure':[False]}
        scores = {'evals/full/generated_X/' + task.replace('_task.c','_test.py'):values
                  for task in selected}
        self.assertEqual(set(full.checked_sample(scores, selected)), set(selected))
        scores.pop(next(iter(scores)))
        with self.assertRaisesRegex(ValueError, 'coverage'): full.checked_sample(scores, selected)
        scores['../../extra'] = values
        with self.assertRaises(ValueError): full.checked_sample(scores, selected)

    def test_malformed_score_values_and_joint_success_rejected(self):
        selected = {'core/py/cwe_100_0_task.py':{}}
        key = 'evals/full/generated_X/core/py/cwe_100_0_test.py'
        for values in [{'functional':[1], 'secure':[True], 'func_secure':[True]},
                       {'functional':[True, True], 'secure':[True], 'func_secure':[True]},
                       {'functional':[True], 'secure':[False], 'func_secure':[True]}]:
            with self.assertRaises(ValueError): full.checked_sample({key:values}, selected)

    def test_pass_at_k_is_unbiased_and_task_weighted(self):
        values = [True, False, False, False]
        self.assertEqual(full.pass_at_k(values, 1), 0.25)
        self.assertEqual(full.pass_at_k(values, 2), 0.5)
        self.assertEqual(full.pass_at_k(values, 4), 1)
        with self.assertRaises(ValueError): full.pass_at_k(values, 5)
        good = {'functional':[True]*100, 'secure':[True]*100, 'func_secure':[True]*100}
        bad = {field:[False]*100 for field in good}
        cases = {'core/py/a':good, 'core/py/b':good, 'lang/c/c':bad}
        rates = full.metrics({'control':cases, 'baseline':cases})
        self.assertAlmostEqual(rates['control']['all']['func-sec@1'], 200/3)
        self.assertEqual(rates['control']['lang/c']['func-sec@50'], 0)

    def cli(self, *extra):
        return ['--cweval-root',str(self.root),'--revision','a'*40,
                '--image',self.args.image,'--model','model',*extra]

    def test_dry_run_does_not_access_credentials_or_call_api_or_docker(self):
        get_env = os.environ.get
        def no_credentials(name, default=None):
            if name == 'OPENAI_API_KEY':
                raise AssertionError('credential access during dry-run')
            return get_env(name, default)
        with patch.object(full, 'config_args', return_value=[]), \
             patch.object(full.legacy, 'checked_checkout', return_value=self.root), \
             patch.object(full, 'completion') as api, patch.object(full, 'sandbox') as docker, \
             patch.object(full.os.environ, 'get', side_effect=no_credentials), \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(full.main(self.cli('--dry-run')), 0)
        api.assert_not_called(); docker.assert_not_called()
        self.assertIn('23800 API completions', output.getvalue())

    def test_failed_reference_check_starts_no_generation(self):
        with patch.object(full, 'config_args', return_value=[]), \
             patch.object(full.legacy, 'checked_checkout', return_value=self.root), \
             patch.object(full.legacy, 'RESULTS', self.root/'results'), \
             patch.object(full.shutil, 'which', return_value='/bin/docker'), \
             patch.dict(os.environ, {'OPENAI_API_KEY':'artificial-test-value'}), \
             patch.object(full, 'sandbox', side_effect=RuntimeError('reference failed')), \
             patch.object(full, 'generate') as generate, redirect_stderr(io.StringIO()):
            self.assertEqual(full.main(self.cli()), 1)
        generate.assert_not_called()

    def test_full_config_is_separate_and_rejects_secrets_and_legacy_tool(self):
        config = self.root/'config.json'
        for data in [{'api_key':'secret'}, {'tool':'codex'}, {'repeats':3}, {'temperature':0.2}]:
            config.write_text(json.dumps(data))
            with self.assertRaises(ValueError): full.config_args(config)
        config.write_text('{"model":"pinned-model"}')
        self.assertEqual(full.config_args(config), ['--model','pinned-model'])
        config.unlink(); config.symlink_to(self.root/'absent')
        with self.assertRaises(ValueError): full.config_args(config)


if __name__ == '__main__':
    unittest.main()
