#!/usr/bin/env python3
"""Exercise actual default entry points, migration and self-contained distribution."""

import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_baseline
import build_release
import install
import install_policy
import policy_setup


class ModularSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aiscb-modular-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.project = self.base / "project with spaces"
        self.home.mkdir()
        self.project.mkdir()
        self.env = {**os.environ, "HOME": str(self.home)}
        for tool, var in install.CONFIG_HOME_ENV.items():
            self.env[var] = str(self.home / ("." + tool))
        self.environ = patch.dict(os.environ, self.env)
        self.environ.start()
        self.addCleanup(self.environ.stop)

    def cli(self, *args, script=None):
        return subprocess.run([sys.executable, str(script or install.INSTALLER_SOURCE), *args],
                              cwd=self.project, env=self.env, capture_output=True,
                              text=True, timeout=20)

    def command(self, path):
        value = path.read_text()
        self.assertIn("On `aiscb?`", value)
        self.assertIn("Installation mode: modular.", value)
        catalog = json.loads(build_baseline.CATALOG.read_text())
        for entry in catalog["modules"]:
            self.assertIn(entry["id"], value)
            for rule in entry["rules"]:
                self.assertNotIn(f"[{rule}]", value)
        command = value.split("Load selected IDs with `", 1)[1].split(" MODULE_ID", 1)[0]
        result = subprocess.run([*shlex.split(command), "aiscb:llm-agents"],
                                cwd=self.base, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[aiscb-LLM-001]", result.stdout)
        self.assertIn("[aiscb-AGENCY-001]", result.stdout)
        self.assertNotIn("[aiscb-WEB-001]", result.stdout)
        bad = subprocess.run([*shlex.split(command), "aiscb:llm-agents", "../outside"],
                             capture_output=True, text=True, timeout=10)
        self.assertNotEqual(bad.returncode, 0)
        self.assertEqual(bad.stdout, "")
        return shlex.split(command)

    def test_default_project_all_clients_and_dependency_output(self):
        result = self.cli("--into", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        for rel in install_policy.ENTRY_POINTS.values():
            self.command(self.project / rel)
        self.assertFalse((self.project / ".claude/rules").exists())
        self.assertEqual(self.cli("--status").returncode, 0)
        self.assertEqual(self.cli("--uninstall").returncode, 0)

    def test_kiro_project_shares_one_agents_block_with_codex(self):
        result = self.cli("kiro", "--into", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Kiro:", result.stdout)
        self.command(self.project / "AGENTS.md")
        self.assertFalse((self.project / "CLAUDE.md").exists())
        result = self.cli("codex", "kiro", "--into", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.project / "AGENTS.md").read_text().count(install_policy.START), 1)
        record = json.loads((self.project / ".aiscb/installation.json").read_text())
        self.assertEqual(list(record["entries"]), ["AGENTS.md"])
        self.assertEqual(self.cli("--status").returncode, 0)
        self.assertEqual(self.cli("--uninstall").returncode, 0)
        self.assertNotIn(install_policy.START, (self.project / "AGENTS.md").read_text())

    def test_kiro_user_uses_global_steering(self):
        result = self.cli("kiro", "--user")
        self.assertEqual(result.returncode, 0, result.stderr)
        steering = self.home / ".kiro/steering/AGENTS.md"
        self.command(steering)
        self.assertFalse((self.home / ".codex/AGENTS.md").exists())
        self.assertEqual(self.cli("--status", "--user").returncode, 0)
        self.assertEqual(self.cli("--uninstall", "--user").returncode, 0)
        self.assertNotIn(install_policy.START, steering.read_text())

    def test_kiro_complete_steering_copy_refuses_before_writes(self):
        for user in (False, True):
            with self.subTest(user=user):
                directory = (self.home if user else self.project) / ".kiro/steering"
                directory.mkdir(parents=True)
                (directory / "old-policy.md").write_bytes(install.bundled_baseline().content)
                result = self.cli("kiro", *(["--user"] if user else []))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("complete", result.stderr)
                self.assertFalse((self.project / "AGENTS.md").exists())
                self.assertFalse((directory / "AGENTS.md").exists())
                (directory / "old-policy.md").unlink()

    def test_kiro_complete_uses_modern_setup_and_legacy_actions_refuse(self):
        result = self.cli("kiro", "--complete")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[aiscb-MCPAUTH-001]", (self.project / "AGENTS.md").read_text())
        result = self.cli("kiro", "--user", "--complete", "--session-switch")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("modular setup only", result.stderr)

    def test_refresh_preserves_scope_tools_mode_and_unrelated_prose(self):
        for user in (False, True):
            for complete in (False, True):
                with self.subTest(user=user, complete=complete):
                    scope = ["--user"] if user else ["--into", str(self.project)]
                    result = self.cli("claude", *scope)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if complete:
                        result = self.cli("claude", *scope, "--complete")
                        self.assertEqual(result.returncode, 0, result.stderr)
                    storage, points = policy_setup.layout(install, self.home, self.project, user)
                    carrier = Path(points["claude"]) if user else storage / points["claude"]
                    carrier.write_text("# Team instructions\n" + carrier.read_text())
                    before = carrier.read_bytes()
                    result = self.cli("--refresh-installed", *scope, "--dry-run")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(before, carrier.read_bytes())
                    result = self.cli("--refresh-installed", *scope)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(before, carrier.read_bytes())
                    record = install_policy.installation_record(storage, points)
                    self.assertEqual(set(record["entries"]), {points["claude"]})
                    self.assertEqual(record["modular"], not complete)
                    self.assertEqual(self.cli("--uninstall", *scope).returncode, 0)
                    carrier.unlink()

    def test_refresh_refuses_missing_modified_or_expanded_installation(self):
        self.assertNotEqual(self.cli("--refresh-installed").returncode, 0)
        self.assertEqual(self.cli("claude", "--into", str(self.project)).returncode, 0)
        for args in (("codex",), ("--migrate",), ("--complete",), ("--offline",),
                     ("--update",), ("--user", "--into", str(self.project))):
            self.assertNotEqual(self.cli("--refresh-installed", *args).returncode, 0)
        carrier = self.project / "CLAUDE.md"
        carrier.write_text(carrier.read_text().replace("Apply", "Changed", 1) + "\n")
        carrier.write_text(carrier.read_text().replace("AI Secure Coding Baseline", "Modified policy", 1))
        before = carrier.read_bytes()
        self.assertNotEqual(self.cli("--refresh-installed").returncode, 0)
        self.assertEqual(before, carrier.read_bytes())

    def test_refresh_refuses_a_downgrade_before_any_write(self):
        from types import SimpleNamespace

        self.assertEqual(self.cli("claude", "--into", str(self.project)).returncode, 0)
        carrier = self.project / "CLAUDE.md"
        before = carrier.read_bytes()
        older = install.parse_baseline(
            install.bundled_baseline().content.replace(build_baseline.BASELINE_ID.encode(), b"aiscb-0.0.1"),
            "test older release")
        args = SimpleNamespace(refresh_installed=True, user=False, into=self.project)
        with patch.object(install, "bundled_baseline", return_value=older):
            with self.assertRaisesRegex(ValueError, "downgrade"):
                policy_setup.run(install, args, home=self.home)
        self.assertEqual(before, carrier.read_bytes())

    def test_user_all_clients_and_installed_updater(self):
        result = self.cli("--user")
        self.assertEqual(result.returncode, 0, result.stderr)
        _, points = policy_setup.layout(install, self.home, self.project, True)
        for path in points.values():
            self.command(Path(path))
        copilot = Path(points["copilot"]).read_bytes()
        self.assertTrue(copilot.startswith(install.VSCODE_INSTRUCTIONS_HEADER))
        updater = self.home / ".aiscb/install.py"
        result = self.cli("--status", "--user", script=updater)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli("--user", script=updater)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cli("--uninstall", "--user").returncode, 0)

    def legacy(self, user):
        root, home = self.project, self.home if user else None
        if user:
            (self.home / ".claude").mkdir()
            (self.home / ".claude/CLAUDE.md").write_text("Keep my preferences.\n")
        result = install.install(list(install.TOOLS), root, home)
        self.assertFalse(result.incomplete, result.messages)
        # Exercise the old signed-source digest path, not only identical current bytes.
        source = install.user_source(self.home) if user else root / install.BASELINE
        source.write_bytes(source.read_bytes().replace(b"On `aiscb?`", b"On `baseline?`"))
        # Legacy Copilot uses a copy; update it to match the simulated old release.
        targets = install.user_targets(self.home) if user else install.project_targets(root)
        for kind, path in targets["copilot"]:
            if kind == "vscode_copy":
                path.write_bytes(install.VSCODE_INSTRUCTIONS_HEADER + source.read_bytes())
        registry = {"schema": 1, "user": None, "projects": {}}
        found = install.scan_user(self.home, {})[0] if user else install.scan_project(root, {})
        install.record_installation(registry, found, trusted=True)
        install.save_registry(install.registry_path(self.home), registry)
        return source

    def test_refresh_legacy_project_keeps_complete_loading(self):
        source = self.legacy(False)
        before = source.read_bytes()
        result = self.cli("--refresh-installed", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(source.read_bytes(), before)
        result = self.cli("--refresh-installed")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(source.read_bytes(), install.bundled_baseline().content)
        self.assertFalse((self.project / ".aiscb/installation.json").exists())

    def test_refresh_legacy_user_keeps_preferences_and_rejects_edits(self):
        source = self.legacy(True)
        result = self.cli("--refresh-installed", "--user")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(source.read_bytes(), install.bundled_baseline().content)
        self.assertIn("Keep my preferences.", (self.home / ".claude/CLAUDE.md").read_text())
        source.write_bytes(source.read_bytes() + b"\nModified rules.\n")
        before = source.read_bytes()
        result = self.cli("--refresh-installed", "--user")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(source.read_bytes(), before)

    def test_migrate_complete_project_all_clients(self):
        source = self.legacy(False)
        before = source.read_bytes()
        rejected = self.cli("--into", str(self.project))
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("--migrate", rejected.stderr)
        result = self.cli("--migrate", "--into", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        for rel in install_policy.ENTRY_POINTS.values():
            self.command(self.project / rel)
        self.assertEqual((self.project / ".claude/rules" / install.BASELINE).read_text(), "")
        self.assertEqual(source.read_bytes(), before)

    def test_migrate_complete_user_and_preserve_preferences(self):
        self.legacy(True)
        result = self.cli("--user", "--migrate")
        self.assertEqual(result.returncode, 0, result.stderr)
        _, points = policy_setup.layout(install, self.home, self.project, True)
        for path in points.values():
            self.command(Path(path))
        self.assertIn("Keep my preferences.", Path(points["claude"]).read_text())
        self.assertNotIn("@", Path(points["claude"]).read_text())

    def test_inherited_complete_policy_blocks_project_before_writes(self):
        self.legacy(True)
        result = self.cli("--into", str(self.project))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inherited complete", result.stderr)
        self.assertEqual(list(self.project.iterdir()), [])
        self.assertEqual(self.cli("--user", "--migrate").returncode, 0)
        result = self.cli("--into", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_additional_automatic_rule_cannot_keep_all_modules_loaded(self):
        directory = self.project / ".claude/rules"
        directory.mkdir(parents=True)
        rule = directory / "old-policy.md"
        rule.write_bytes(install.bundled_baseline().content)
        result = self.cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("additional complete policy", result.stderr)
        self.assertFalse((self.project / "AGENTS.md").exists())
        self.assertFalse((self.project / ".aiscb").exists())

    def test_modified_dynamic_hook_refuses_before_any_entry_is_replaced(self):
        self.legacy(True)
        install.install_session_switch(["codex"], self.project, self.home)
        hook = self.home / ".codex/hooks.json"
        hook.write_text(hook.read_text().replace("--session-context", "--changed-context"))
        before = (self.home / ".codex/AGENTS.md").read_bytes()
        result = self.cli("--user", "--migrate")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.home / ".codex/AGENTS.md").read_bytes(), before)

    def test_modified_legacy_source_refuses_without_side_effects(self):
        source = self.legacy(False)
        source.write_bytes(source.read_bytes() + b"\nUnrecorded modification.\n")
        before = (self.project / "AGENTS.md").read_bytes()
        result = self.cli("--migrate")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("modified or unrecorded", result.stderr)
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), before)
        self.assertFalse((self.project / "CLAUDE.md").exists())

    def test_dynamic_user_migration_removes_only_managed_injection_hooks(self):
        self.legacy(True)
        install.install_session_switch(["claude", "codex"], self.project, self.home)
        hook = self.home / ".claude/settings.json"
        config = json.loads(hook.read_text())
        own = {"hooks": [{"type": "command", "command": "echo own-hook"}]}
        config["hooks"]["SessionStart"].append(own)
        hook.write_text(json.dumps(config))
        result = self.cli("--user", "--migrate")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(hook.read_text())["hooks"]["SessionStart"], [own])
        self.assertNotIn("show-baseline-version", hook.read_text())
        self.assertNotIn("show-baseline-version", (self.home / ".codex/hooks.json").read_text())
        self.command(self.home / ".codex/AGENTS.md")

    def test_user_custom_roots_and_copilot_vscode_copy(self):
        for tool, var in install.CONFIG_HOME_ENV.items():
            self.env[var] = str(self.base / ("custom-" + tool))
        result = self.cli("--user")
        self.assertEqual(result.returncode, 0, result.stderr)
        for path in (self.base / "custom-claude/CLAUDE.md",
                     self.base / "custom-codex/AGENTS.md",
                     self.base / "custom-copilot/instructions/secure-coding.instructions.md",
                     self.home / ".copilot/instructions/secure-coding.instructions.md"):
            self.command(path)

    def test_symlink_parent_and_override_refuse(self):
        outside = self.base / "outside"
        outside.mkdir()
        (self.project / ".github").symlink_to(outside)
        result = self.cli("copilot")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])
        (self.project / "AGENTS.override.md").write_text("User override.\n")
        result = self.cli("codex")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("overrides", result.stderr)

    def test_user_updater_drift_or_foreign_file_refuses_before_instruction_writes(self):
        storage = self.home / ".aiscb"
        storage.mkdir()
        updater = storage / "install.py"
        updater.write_text("My unrelated script.\n")
        result = self.cli("--user")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unowned updater", result.stderr)
        self.assertFalse((self.home / ".codex/AGENTS.md").exists())
        self.assertEqual(updater.read_text(), "My unrelated script.\n")
        updater.unlink()
        self.assertEqual(self.cli("--user").returncode, 0)
        initial = (self.home / ".codex/AGENTS.md").read_bytes()
        updater.write_text("Changed updater.\n")
        self.assertNotEqual(self.cli("--user").returncode, 0)
        self.assertEqual((self.home / ".codex/AGENTS.md").read_bytes(), initial)

    def test_copilot_user_parent_symlink_refuses_without_outside_writes(self):
        outside = self.base / "outside"
        outside.mkdir()
        (self.home / ".copilot").symlink_to(outside)
        result = self.cli("copilot", "--user")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

    def test_interactive_modular_default_and_scope(self):
        import argparse
        args = argparse.Namespace(into=self.project, user=False, tools=[], interactive=True,
                                  status=False, uninstall=False, complete=False,
                                  organization=None, organization_sha256=None, migrate=False)
        answers = iter(("p", "", "claude codex copilot"))
        self.assertEqual(policy_setup.run(install, args, home=self.home,
                         input_fn=lambda _: next(answers), output=lambda _: None), 0)
        for rel in install_policy.ENTRY_POINTS.values():
            self.command(self.project / rel)

    def test_loader_missing_or_tampered_does_not_return_policy(self):
        self.assertEqual(self.cli("codex").returncode, 0)
        command = self.command(self.project / "AGENTS.md")
        release = Path(command[1]).parent
        module = release / "modules/aiscb-llm-agents.md"
        module.write_text(module.read_text() + "tampered")
        result = subprocess.run([*command, "aiscb:llm-agents"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        Path(command[1]).unlink()
        self.assertNotEqual(subprocess.run([*command, "aiscb:llm-agents"],
                                          capture_output=True).returncode, 0)

    def test_explicit_complete_and_return_to_modular(self):
        self.assertEqual(self.cli("--complete").returncode, 0)
        for actions in install.project_targets(self.project).values():
            self.assertIn("[aiscb-MCPAUTH-001]", actions[0][1].read_text())
        self.assertNotEqual(self.cli().returncode, 0)
        self.assertEqual(self.cli("--migrate").returncode, 0)
        for rel in install_policy.ENTRY_POINTS.values():
            self.command(self.project / rel)

    def test_managed_user_format_switch_and_appended_complete_conflict(self):
        self.assertEqual(self.cli("--user").returncode, 0)
        self.assertEqual(self.cli("--user", "--complete").returncode, 0)
        self.assertEqual(self.cli("--user").returncode, 0)
        target = self.home / ".codex/AGENTS.md"
        self.command(target)
        target.write_bytes(target.read_bytes() + install.bundled_baseline().content)
        before = target.read_bytes()
        result = self.cli("--user")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside managed block", result.stderr)
        self.assertEqual(target.read_bytes(), before)

    def test_release_installer_is_self_contained_after_staging_disappears(self):
        bundle = build_release.stage(build_baseline.VERSION, "1", self.source_copy())
        standalone = self.base / "download"
        (standalone / "scripts").mkdir(parents=True)
        for name in install.BUNDLE_FILES:
            (standalone / name).write_bytes((bundle / name).read_bytes())
        script = standalone / "scripts/install.py"
        result = self.cli("--user", script=script)
        self.assertEqual(result.returncode, 0, result.stderr)
        script.unlink()
        updater = self.home / ".aiscb/install.py"
        result = self.cli("--user", script=updater)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.command(self.home / ".codex/AGENTS.md")

    def source_copy(self):
        import shutil
        root = self.base / "source"
        shutil.copytree(build_baseline.ROOT / "baseline", root / "baseline")
        shutil.copytree(build_baseline.ROOT / "scripts", root / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        return root


if __name__ == "__main__":
    unittest.main()
