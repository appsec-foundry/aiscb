#!/usr/bin/env python3
"""Conservation, delivery and timing checks for the three-way split."""
from contextlib import nullcontext, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import install_policy
import policy_loader
import split_routing
from split_routing import assess


class SplitTests(unittest.TestCase):
    def test_reviewed_security_clauses_are_preserved(self):
        rules = {}
        for name in ('web', 'authentication', 'cryptography'):
            text = (ROOT/f'baseline/modules/aiscb-{name}.md').read_text()
            rules.update(re.findall(r'^- \*\*\[([^]]+)\] [^\n]*?:\*\* (.+)$', text, re.M))
        rules['aiscb-MECHANISMS-001'] += ' '+rules.pop('aiscb-AUTHMECHANISMS-001')
        rules['aiscb-WEBTESTS-001'] = rules.pop('aiscb-AUTHTESTS-001').removesuffix('.')+'; '+rules['aiscb-WEBTESTS-001'].removeprefix('Test ')
        # Canonical rule bodies from the pre-split aiscb-0.1.18 source, minus the
        # webhook clause removed from MECHANISMS-001 by
        # specs/archive/2026-09-24-trim-webhook-duplicate.
        # Includes the header validation and test additions approved in
        # specs/archive/2026-09-24-cweval-module-hardening; all other bodies
        # retain the previous conservation check's content.
        self.assertEqual(hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest(),
                         '89168ab0c20bfa942d52472cbf35af8945efe1172a5af411a6edcf8341ae3f55')

    def test_narrow_loads_and_auth_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); install_policy.install(['claude'], root)
            record = json.loads((root/'.aiscb/installation.json').read_text())
            release = root/'.aiscb/releases'/record['digest']
            web = policy_loader.render(release, record['digest'], ['aiscb:web'])
            self.assertIn('[aiscb-WEBTESTS-001]', web)
            self.assertNotIn('[aiscb-AUTH-001]', web)
            auth = policy_loader.render(release, record['digest'], ['aiscb:authentication', 'aiscb:cryptography'])
            self.assertLess(auth.index('[aiscb-MECHANISMS-001]'), auth.index('[aiscb-AUTH-001]'))
            self.assertEqual(auth.count('[aiscb-MECHANISMS-001]'), 1)
            self.assertIn('[aiscb-AUTHTESTS-001]', auth)
            self.assertIn('[aiscb-BOOTSTRAP-001]', auth)
            self.assertIn('[aiscb-LIMITS-001]', auth)
            self.assertNotIn('[aiscb-WEB-001]', auth)
            with self.assertRaises(ValueError):
                policy_loader.render(release, record['digest'], ['aiscb:web-auth-crypto'])

    def test_recorded_omissions_are_closed_by_verified_dependencies(self):
        # Successful module sets from the three failed planning runs. Replay
        # their deliveries, not the plans, against the corrected dependency graph.
        selections = [
            ['aiscb:authentication', 'aiscb:cryptography', 'aiscb:data-handling'],
            ['aiscb:cryptography'],
            ['aiscb:web', 'aiscb:authentication', 'aiscb:cryptography'],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); install_policy.install(['claude'], root)
            record = json.loads((root/'.aiscb/installation.json').read_text())
            release = root/'.aiscb/releases'/record['digest']
            for selected in selections:
                text = policy_loader.render(release, record['digest'], selected)
                self.assertEqual(text.count('[aiscb-BOOTSTRAP-001]'), 1)
                self.assertEqual(text.count('[aiscb-SECRETTESTS-001]'), 1)
                if 'aiscb:authentication' in selected:
                    self.assertEqual(text.count('[aiscb-LIMITS-001]'), 1)
            (release/'modules/aiscb-secrets-initialization.md').unlink()
            for selected in (['aiscb:cryptography'], ['aiscb:authentication']):
                with self.assertRaises((ValueError, OSError)):
                    policy_loader.render(release, record['digest'], selected)

    def test_missing_failed_and_late_loads_do_not_pass(self):
        write = {'tool': 'write_file', 'path': 'plan.md', 'error': False}
        load = {'tool': 'run_command', 'loaded': ['aiscb:web'], 'error': False}
        self.assertFalse(assess([], ['aiscb:web'])['written'])
        self.assertEqual(assess([write, load], ['aiscb:web'])['missing'], ['aiscb:web'])
        self.assertEqual(assess([{**load, 'error': True}, write], ['aiscb:web'])['missing'], ['aiscb:web'])
        self.assertEqual(assess([load, write], ['aiscb:web'])['missing'], [])


class SplitRoutingMainTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='aiscb-split-main-')
        self.addCleanup(self.tmp.cleanup)
        self.out=Path(self.tmp.name)/'evidence'
        harness=split_routing.harness
        # main() swaps the installer root and registers fixture cases.
        for patcher in (patch.object(harness.install_policy,'ROOT',harness.install_policy.ROOT),
                        patch.dict(harness.CASES)):
            patcher.start(); self.addCleanup(patcher.stop)
        self.baseline_id=json.loads((ROOT/'baseline/catalog.json').read_text())['baseline_id']
        self.prompts=[]

    def capture(self, skip_loads=()):
        def fake(cmd, cwd, path, timeout):
            prompt=cmd[cmd.index('-p')+1]
            if prompt==split_routing.harness.runner.PROBE_PROMPT:
                return {'complete':True,'reply':self.baseline_id,'events':[]}
            self.prompts.append(prompt)
            base=Path(cwd).parent; name=base.name
            loaded=[] if name in skip_loads else split_routing.CASES[name][1]
            events=[{'turn':1,'tool':'run_command','error':False,'loaded':loaded},
                    {'turn':1,'tool':'write_file','error':False,'path':'plan.md'}]
            with (base/'audit.jsonl').open('a') as audit:
                audit.write(''.join(json.dumps(e)+'\n' for e in events))
            (Path(cwd)/'plan.md').write_text(f'plan for {name}\n')
            return {'complete':True,'reply':'planned','events':[]}
        return fake

    def main(self, *argv, capture=None):
        out=io.StringIO()
        with patch.object(sys,'argv',['split_routing.py',*argv]), \
             patch.object(split_routing.harness,'isolated_profile',nullcontext), \
             patch.object(split_routing.harness,'capture',side_effect=capture), \
             redirect_stdout(out), patch.object(sys,'stderr',io.StringIO()):
            try: code=split_routing.main()
            except SystemExit as exit: code=exit.code
        return code,out.getvalue()

    def test_without_run_only_the_plan_is_printed(self):
        code,out=self.main()
        self.assertEqual(code,0)
        self.assertEqual(json.loads(out)['runs'],4)
        self.assertEqual(self.main('--run')[0],2)

    def test_run_records_loads_before_each_plan_write(self):
        code,out=self.main('--run','--output',str(self.out),capture=self.capture())
        self.assertEqual(code,0,out)
        results=json.loads((self.out/'results.json').read_text())
        self.assertEqual([r['case'] for r in results],list(split_routing.CASES))
        self.assertTrue(all(r['passed'] for r in results))
        self.assertEqual((self.out/'web-plan.md').read_text(),'plan for web\n')
        self.assertIn('Load selected IDs',(self.out/'web-initial.md').read_text())
        self.assertTrue(all('do not implement' in p for p in self.prompts))
        plan=json.loads((self.out/'plan.json').read_text())
        self.assertEqual(plan['catalog_sha256'],hashlib.sha256((ROOT/'baseline/catalog.json').read_bytes()).hexdigest())

    def test_missing_load_fails_the_run(self):
        code,out=self.main('--run','--output',str(self.out),capture=self.capture(skip_loads=('mixed',)))
        self.assertEqual(code,1)
        self.assertIn('mixed: passed=False, modules=[]',out)

    def test_failed_preflight_starts_no_task(self):
        def refuse(cmd, cwd, path, timeout):
            return {'complete':True,'reply':'no baseline here','events':[]}
        code,_=self.main('--run','--output',str(self.out),capture=refuse)
        self.assertEqual(code,'Preflight failed; no tasks started.')
        self.assertFalse((self.out/'results.json').exists())


if __name__ == '__main__': unittest.main()
