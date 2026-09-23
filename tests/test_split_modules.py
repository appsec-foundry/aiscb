#!/usr/bin/env python3
"""Conservation, delivery and timing checks for the three-way split."""
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import install_policy
import policy_loader
from split_routing import assess


class SplitTests(unittest.TestCase):
    def test_original_security_clauses_are_preserved(self):
        rules = {}
        for name in ('web', 'authentication', 'cryptography'):
            text = (ROOT/f'baseline/modules/aiscb-{name}.md').read_text()
            rules.update(re.findall(r'^- \*\*\[([^]]+)\] [^\n]*?:\*\* (.+)$', text, re.M))
        rules['aiscb-MECHANISMS-001'] += ' '+rules.pop('aiscb-AUTHMECHANISMS-001')
        rules['aiscb-WEBTESTS-001'] = rules.pop('aiscb-AUTHTESTS-001').removesuffix('.')+'; '+rules['aiscb-WEBTESTS-001'].removeprefix('Test ')
        # Canonical rule bodies from the pre-split aiscb-0.1.18 source.
        self.assertEqual(hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest(),
                         'a8bdde767aff9dc93a4d3e0849933aa72801783c9d4e740929acafc7cfaa611a')

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


if __name__ == '__main__': unittest.main()
