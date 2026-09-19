#!/usr/bin/env python3
"""Upgrade real historical sources, and refuse unsafe or ambiguous input."""

import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest

import upgrade_organization as upgrade

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'scripts/upgrade_organization.py'
FIXTURE = ROOT / 'tests/fixtures/organization-0.1.15'


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'org'
        shutil.copytree(FIXTURE, self.source)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.source,
                              capture_output=True, text=True, timeout=20)

    def test_no_arguments_upgrades_historical_example_without_changing_source(self):
        before = upgrade.inventory(self.source)
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(before, upgrade.inventory(self.source))
        out = self.source / '.aiscb-upgrade'
        report = json.loads((out / 'upgrade-report.json').read_text())
        self.assertTrue(report['structurally_valid'])
        self.assertTrue(report['ready_for_policy_review'])
        self.assertEqual(report['organization_id'], 'acme-sec-1.0.1')
        self.assertEqual(report['target_baseline'], upgrade.build_baseline.BASELINE_ID)
        self.assertIn('not assessed', report['policy_compatibility'])
        overlay = (out / 'overlay.md').read_text()
        self.assertIn('verified `acme:*` namespace', overlay)
        self.assertNotIn('ACME-REQ-ROUTING-001', overlay)
        self.assertIn('[ACME-TENANT-001]', overlay)
        for rel in ('packs/authentication.md', 'packs/deployment.md'):
            old = before[rel].decode()
            new = (out / rel).read_text()
            self.assertEqual(old[old.index('- **['):], new[new.index('- **['):])
        self.assertEqual(before['blueprints/spa/1.0.0.json'],
                         (out / 'blueprints/spa/1.0.0.json').read_bytes())
        self.assertIn('secure-coding-baseline.md', (out / 'upgrade.diff').read_text())
        self.assertEqual(os.stat(out).st_mode & 0o777, 0o700)
        self.assertFalse((self.source / 'AGENTS.md').exists())

    def test_repeat_does_not_overwrite_output(self):
        self.assertEqual(self.cli().returncode, 0)
        path = self.source / '.aiscb-upgrade/overlay.md'
        path.write_text('retain review edits')
        self.assertEqual(self.cli().returncode, 1)
        self.assertEqual(path.read_text(), 'retain review edits')

    def test_check_has_no_persistent_side_effects(self):
        before = sorted(p.relative_to(self.source) for p in self.source.rglob('*'))
        result = self.cli('--check')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, sorted(p.relative_to(self.source) for p in self.source.rglob('*')))

    def test_custom_routing_is_preserved_and_marked_for_review(self):
        path = self.source / 'overlay.md'
        path.write_text(path.read_text().replace('select\n  every pack', 'select\n  only approved packs from every pack'))
        files, report, _ = upgrade.prepare(self.source)
        self.assertIn(b'only approved packs', files['overlay.md'])
        self.assertFalse(report['ready_for_policy_review'])
        self.assertTrue(any('legacy-loading' in x for x in report['issues']))
        self.assertEqual(self.cli().returncode, 2)
        self.assertTrue((self.source / '.aiscb-upgrade/upgrade-report.json').exists())

    def test_current_bundle_keeps_own_rules(self):
        current = self.root / 'current'
        shutil.copytree(ROOT / 'examples/organization-bundle', current)
        files, report, _ = upgrade.prepare(current)
        self.assertTrue(report['ready_for_policy_review'], report['issues'])
        self.assertEqual(files['packs/authentication.md'], (current / 'packs/authentication.md').read_bytes())
        self.assertIn(b'[ACME-WORKFLOW-001]', files['overlay.md'])
        self.assertNotIn('build.py', files)

    def test_overlay_only_builds_and_installs(self):
        plain = self.root / 'overlay.md'
        text = ('# Team\n\n`baseline-id: team-sec-2.3.4`. Extends aiscb (`aiscb-0.1.15`).\n'
                '- **[TEAM-REVIEW-001]** Obtain a policy owner review before deployment.\n')
        plain.write_text(text)
        files, report, _ = upgrade.prepare(plain)
        self.assertTrue(report['ready_for_policy_review'], report['issues'])
        self.assertEqual(json.loads(files['catalog.json']), {'packs': []})
        self.assertIn(text.split('- **')[1].encode(), files['overlay.md'])

    def test_unknown_rule_is_not_rewritten(self):
        p = self.source / 'packs/authentication.md'
        p.write_text(p.read_text().replace('aiscb-AUTH-001', 'aiscb-NONEXISTENT-001'))
        files, report, _ = upgrade.prepare(self.source)
        self.assertIn(b'aiscb-NONEXISTENT-001', files['packs/authentication.md'])
        self.assertFalse(report['ready_for_policy_review'])
        # The builder checks mappings; prose references are an additional upgrade check.
        self.assertTrue(report['structurally_valid'])

    def test_unknown_catalog_mapping_is_rejected(self):
        path = self.source / 'catalog.json'
        path.write_text(path.read_text().replace('aiscb-AUTH-001', 'aiscb-NONEXISTENT-001'))
        _, report, _ = upgrade.prepare(self.source)
        self.assertFalse(report['structurally_valid'])
        self.assertFalse(report['ready_for_policy_review'])

    def test_generated_bundle_all_client_entries_and_selective_loader(self):
        files, report, _ = upgrade.prepare(self.source)
        candidate = self.root / 'candidate'
        candidate.mkdir()
        upgrade.write_files(candidate, files)
        bundle = self.root / 'bundle'
        _, digest = upgrade.builder().build(candidate, ROOT / 'baseline', bundle, self.root / 'managed')
        project = self.root / 'project'
        project.mkdir()
        upgrade.install_policy.install(['claude', 'codex', 'copilot'], project,
                                       bundle=bundle, expected=digest)
        for rel in upgrade.install_policy.ENTRY_POINTS.values():
            text = (project / rel).read_text()
            self.assertIn('[ACME-TENANT-001]', text)
            self.assertIn(upgrade.build_baseline.BASELINE_ID, text)
            self.assertNotIn('[ACME-SSO-001]', text)
            self.assertNotIn('[aiscb-WEB-001]', text)
            command = text.split('Load selected IDs with `', 1)[1].split(' MODULE_ID', 1)[0]
            result = subprocess.run([*shlex.split(command), 'acme:authentication'],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('[ACME-SSO-001]', result.stdout)
            self.assertIn('Blueprint', result.stdout)
            self.assertNotIn('[ACME-EXPOSE-001]', result.stdout)

    def test_embedded_official_rules_require_review(self):
        p = self.source / 'overlay.md'
        p.write_text(p.read_text() + '\n- **[aiscb-ACCESS-001]** customized legacy rule\n')
        files, report, _ = upgrade.prepare(self.source)
        self.assertIn(b'customized legacy rule', files['overlay.md'])
        self.assertTrue(any('embedded-upstream' in x for x in report['issues']))

    def test_explicit_version_must_increase_and_keep_identity(self):
        for value in ('acme-sec-1.0.0', 'acme-sec-0.9.9', 'other-1.0.1', 'aiscb-1.0.1'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                upgrade.prepare(self.source, value)
        self.assertEqual(upgrade.prepare(self.source, 'acme-sec-2.0.0')[1]['organization_id'], 'acme-sec-2.0.0')

    def test_traversal_and_absolute_catalog_paths_refused(self):
        path = self.source / 'catalog.json'
        original = json.loads(path.read_text())
        for value in ('../outside.md', '/tmp/outside.md', 'packs/../../outside.md'):
            original['packs'][0]['file'] = value
            path.write_text(json.dumps(original))
            with self.subTest(value=value), self.assertRaises(ValueError):
                upgrade.prepare(self.source)

    def test_symlinks_in_source_and_output_refused(self):
        link = self.root / 'link'
        link.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ValueError):
            upgrade.prepare(link)
        (self.source / 'packs/link.md').symlink_to(self.root / 'missing')
        with self.assertRaises(ValueError):
            upgrade.prepare(self.source)
        (self.source / 'packs/link.md').unlink()
        (self.source / '.aiscb-upgrade').symlink_to(self.root / 'missing')
        self.assertEqual(self.cli().returncode, 1)
        self.assertFalse((self.root / 'missing').exists())

    def test_limits_and_non_utf8_are_refused(self):
        path = self.source / 'overlay.md'
        for raw in (b'x' * (upgrade.MAX_BYTES + 1), b'\xff'):
            path.write_bytes(raw)
            self.assertEqual(self.cli().returncode, 1)
            self.assertFalse((self.source / '.aiscb-upgrade').exists())

    def test_duplicate_json_keys_refused(self):
        (self.source / 'catalog.json').write_text('{"packs":[],"packs":[]}')
        self.assertEqual(self.cli().returncode, 1)
        self.assertFalse((self.source / '.aiscb-upgrade').exists())

    def test_newer_upstream_is_not_downgraded(self):
        path = self.source / 'overlay.md'
        path.write_text(path.read_text().replace('aiscb-0.1.15', 'aiscb-99.0.0'))
        self.assertEqual(self.cli().returncode, 1)
        self.assertFalse((self.source / '.aiscb-upgrade').exists())

    def test_empty_catalog_does_not_hide_unlisted_modules(self):
        (self.source / 'catalog.json').write_text('{"packs": []}')
        _, report, _ = upgrade.prepare(self.source)
        self.assertFalse(report['structurally_valid'])

    def test_ambiguous_namespace_is_reported_without_renaming(self):
        path = self.source / 'catalog.json'
        path.write_text(path.read_text().replace('acme-authentication', 'other-authentication'))
        files, report, _ = upgrade.prepare(self.source)
        self.assertIn('other-authentication', files['catalog.json'].decode())
        self.assertFalse(report['ready_for_policy_review'])
        self.assertTrue(any('module-namespace' in issue for issue in report['issues']))

    def test_input_python_never_executed(self):
        (self.source / 'build.py').write_text('raise RuntimeError("UNTRUSTED SCRIPT")')
        self.assertEqual(self.cli().returncode, 0)
        self.assertFalse((self.source / '.aiscb-upgrade/build.py').exists())


if __name__ == '__main__':
    unittest.main()
