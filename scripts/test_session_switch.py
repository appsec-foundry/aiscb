#!/usr/bin/env python3
"""Exercise the opt-in loader without calling a model or touching real installs."""

import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import install
import show_baseline_version as helper


class SessionSwitchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="aiscb-session-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project with spaces"
        self.home = self.root / "home"
        self.project.mkdir()
        self.home.mkdir()

    def setup_switch(self, user=False, tools=None):
        home = self.home if user else None
        report = install.install_session_switch(tools or ["claude", "codex"], self.project, home)
        self.assertFalse(any(line.startswith("blocked") for line in report), report)
        return install.version_hook_path(self.project, home)

    def call(self, script, value=None, part=0):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home)}
        if value is not None:
            env["AISCB_DISABLE"] = value
        result = subprocess.run(
            [sys.executable, str(script), "--session-context", "--part", str(part)],
            env=env, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)

    def snapshot(self):
        return {str(p.relative_to(self.root)): ("link", str(p.readlink())) if p.is_symlink()
                else hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob("*") if p.is_symlink() or p.is_file()}

    def test_default_loads_every_byte_in_bounded_parts(self):
        self.assertEqual(install.SESSION_PARTS, helper.SESSION_PARTS)
        script = self.setup_switch()
        for value in (None, "0"):
            texts = [self.call(script, value, i)["hookSpecificOutput"]["additionalContext"]
                     for i in range(helper.SESSION_PARTS)]
            self.assertTrue(all(len(text) < 10000 for text in texts))
            content = "".join(text.split("\n\n", 1)[1] for text in texts)
            self.assertEqual(content, install.SOURCE.read_text())

    def test_disabled_excludes_rules_and_does_not_claim_active(self):
        script = self.setup_switch()
        for part in range(helper.SESSION_PARTS):
            result = self.call(script, "1", part)
            text = json.dumps(result)
            self.assertIn("aiscb-session-disabled", text)
            self.assertNotIn("aiscb-ACCESS-001", text)
            self.assertNotIn("Baseline active", text)

    def test_invalid_values_and_broken_baseline_stop(self):
        script = self.setup_switch()
        for value in ("", "true", "yes", "2", " 1", "1\n"):
            result = self.call(script, value)
            self.assertIs(result["continue"], False)
            self.assertNotIn("hookSpecificOutput", result)
        source = self.project / install.BASELINE
        for content in ("", "wrong", install.SOURCE.read_text() + "x" * 28000):
            source.write_text(content)
            for value in ("0", "1"):
                result = self.call(script, value)
                self.assertIs(result["continue"], False)
                self.assertNotIn(str(source), result["stopReason"])
        source.unlink()
        self.assertIs(self.call(script)["continue"], False)

    def test_parallel_sessions_have_no_shared_mutations(self):
        script = self.setup_switch()
        before = self.snapshot()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            on = pool.submit(self.call, script, "0")
            off = pool.submit(self.call, script, "1")
        self.assertIn("aiscb-session-part", json.dumps(on.result()))
        self.assertIn("aiscb-session-disabled", json.dumps(off.result()))
        self.assertEqual(self.snapshot(), before)

    def test_user_migration_preserves_other_settings_and_instructions(self):
        install.install(["claude", "codex", "copilot"], self.project, self.home)
        install.install_version_hooks(["claude", "codex"], self.project, self.home)
        claude = self.home / ".claude" / "CLAUDE.md"
        original_import = claude.read_text().strip()
        claude.write_bytes(("OTHER_USER_RULE\r\n" + original_import + "\r\n").encode())
        settings = self.home / ".claude" / "settings.json"
        config = json.loads(settings.read_text())
        config["permissions"] = {"deny": ["Bash(curl *)"]}
        other_hook = {"hooks": [{"type": "command", "command": "echo OTHER_HOOK"}]}
        config["hooks"]["SessionStart"].append(other_hook)
        settings.write_text(json.dumps(config))
        copilot_before = (self.home / ".copilot" / "copilot-instructions.md").readlink()
        self.setup_switch(user=True)
        self.assertIn(b"OTHER_USER_RULE\r\n", claude.read_bytes())
        self.assertNotIn(original_import.encode(), claude.read_bytes())
        config = json.loads(settings.read_text())
        self.assertEqual(config["permissions"], {"deny": ["Bash(curl *)"]})
        self.assertIn(other_hook, config["hooks"]["SessionStart"])
        self.assertEqual((self.home / ".copilot" / "copilot-instructions.md").readlink(), copilot_before)
        found = install.scan_user(self.home, {})
        self.assertEqual(found[0].tools, ("claude", "codex", "copilot"))
        before = self.snapshot()
        self.setup_switch(user=True)
        self.assertEqual(self.snapshot(), before)

    def test_user_migration_accepts_legacy_hook_at_previous_helper_path(self):
        install.install(["codex"], self.project, self.home)
        current = install.version_hook_path(self.project, self.home)
        previous = self.home / ".local" / "share" / "old-aiscb" / install.VERSION_HOOK_NAME
        path = self.home / ".codex" / "hooks.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "hooks": {
                "SessionStart": [install._codex_version_hook(previous, False)]
            }
        }))
        report = install.install_session_switch(["codex"], self.project, self.home)
        self.assertFalse(any(line.startswith("blocked") for line in report), report)
        config = json.loads(path.read_text())
        self.assertIn(
            install._session_hook("codex", current, False),
            config["hooks"]["SessionStart"],
        )
        self.assertNotIn(str(previous), path.read_text())

    def test_setup_status_and_uninstall_preserve_switch_mode(self):
        for user in (False, True):
            with self.subTest(user=user):
                home = self.home if user else None
                self.setup_switch(user=user)
                targets = install.user_targets(home) if user else install.project_targets(self.project)
                source = install.user_source(home) if user else self.project / install.BASELINE
                before = targets["codex"][0][1].readlink()
                install.install(["claude", "codex"], self.project, home)
                install.install_version_hooks(["claude", "codex"], self.project, home)
                self.assertEqual(targets["codex"][0][1].readlink(), before)
                for tool in ("claude", "codex"):
                    self.assertTrue(install._version_hook_is_installed(tool, self.project, home))
                found = install.scan_user(home, {})[0] if user else install.scan_project(self.project, {})
                self.assertEqual(found.tools, ("claude", "codex"))
                self.assertTrue(install.remove_installation(found, []))
                self.assertFalse(source.exists())
                self.assertFalse(targets["codex"][0][1].is_symlink())
                self.assertFalse(install.version_hook_path(self.project, home).exists())
                for tool in ("claude", "codex"):
                    self.assertFalse(install._session_hook_path(tool, self.project, home).exists())

    def test_foreign_instructions_or_hooks_block_before_mutation(self):
        target = self.project / "AGENTS.md"
        target.write_text("OTHER_PROJECT_RULE\n")
        before = self.snapshot()
        report = install.install_session_switch(["claude", "codex"], self.project, None)
        self.assertTrue(report[0].startswith("blocked"))
        self.assertEqual(self.snapshot(), before)
        target.unlink()
        path = self.project / ".claude" / "settings.json"
        path.parent.mkdir()
        for content in ("not json", '{"hooks":[]}', '{"disableAllHooks":true}',
                        json.dumps({"hooks": {"SessionStart": [{"hooks": [{"command": "custom show-baseline-version.py"}]}]}})):
            path.write_text(content)
            before = self.snapshot()
            report = install.install_session_switch(["claude", "codex"], self.project, None)
            self.assertTrue(report[0].startswith("blocked"))
            self.assertEqual(self.snapshot(), before)

    def test_static_installation_ignores_switch(self):
        install.install(["codex"], self.project, None)
        target = self.project / "AGENTS.md"
        self.assertEqual(target.read_text(), install.SOURCE.read_text())
        self.assertFalse(install._session_link(target, self.project / install.BASELINE))

    def test_missing_hook_has_explicit_loader_fallback(self):
        self.setup_switch()
        content = (self.project / "AGENTS.md").read_text()
        for part in range(4):
            self.assertIn(f"--session-context --part {part}", content)
        self.assertIn("stop and report the loader failure", content)
        self.assertIn("Never alter", content)

    def test_derived_baseline_and_separate_overlay(self):
        source = self.project / install.BASELINE
        derived = install.SOURCE.read_text().replace("aiscb-0.1.14", "acme-sec-1.0.0+team")
        source.write_text(derived)
        overlay = self.project / ".claude" / "rules" / "organization.md"
        overlay.parent.mkdir(parents=True)
        overlay.write_text("SEPARATE_OVERLAY_RULE\n")
        script = self.setup_switch()
        active = json.dumps(self.call(script))
        self.assertIn("acme-sec-1.0.0+team", active)
        self.assertNotIn("acme-sec-1.0.0+team", json.dumps(self.call(script, "1")))
        self.assertEqual(overlay.read_text(), "SEPARATE_OVERLAY_RULE\n")
        self.assertEqual(source.read_text(), derived)

    def test_customized_session_commands_are_not_overwritten(self):
        self.setup_switch()
        for event in ("SessionStart", "UserPromptSubmit"):
            path = self.project / ".codex" / "hooks.json"
            original = path.read_text()
            config = json.loads(original)
            config["hooks"][event][0]["hooks"][0]["command"] += " --custom-option"
            path.write_text(json.dumps(config))
            before = self.snapshot()
            report = install.install_session_switch(["codex"], self.project, None)
            self.assertTrue(report[0].startswith("blocked"))
            self.assertEqual(self.snapshot(), before)
            path.write_text(original)

    def test_session_check_blocks_invalid_or_missing_source(self):
        script = self.setup_switch()
        for value in ("0", "1", "invalid"):
            env = {"PATH": os.environ["PATH"], "HOME": str(self.home), "AISCB_DISABLE": value}
            result = subprocess.run([sys.executable, str(script), "--session-check"],
                                    env=env, capture_output=True, text=True, timeout=10)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("decision") == "block", value == "invalid")
        (self.project / install.BASELINE).unlink()
        result = subprocess.run([sys.executable, str(script), "--session-check"],
                                env={"PATH": os.environ["PATH"]}, capture_output=True, text=True, timeout=10)
        self.assertEqual(json.loads(result.stdout)["decision"], "block")

    def test_packaged_adapter_is_refused_without_changes(self):
        adapter = self.root / "org" / "AGENTS.md"
        adapter.parent.mkdir()
        adapter.write_text(install.SOURCE.read_text() + "\n`baseline-id: acme-sec-1.0.0`\nOVERLAY\n")
        (self.project / "AGENTS.md").symlink_to(adapter)
        before = self.snapshot()
        report = install.install_session_switch(["codex"], self.project, None)
        self.assertTrue(report[0].startswith("blocked"))
        self.assertIn("instruction file", report[0])
        self.assertEqual(self.snapshot(), before)

    def test_symlinked_settings_directory_is_not_written(self):
        outside = self.root / "other-config"
        outside.mkdir()
        (outside / "settings.json").write_text('{"permissions":{"deny":["Bash(*)"]}}')
        (self.project / ".claude").symlink_to(outside)
        before = self.snapshot()
        report = install.install_session_switch(["claude"], self.project, None)
        self.assertTrue(report[0].startswith("blocked"))
        self.assertEqual(self.snapshot(), before)

    def test_cli_setup_and_invalid_combinations(self):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home)}
        argv = [sys.executable, str(install.INSTALLER_SOURCE), "--session-switch"]
        # Without --user it would target the project, which loads statically.
        for flags in ([], ["--into", str(self.project)], ["copilot"], ["--status"],
                      ["--interactive"], ["--update"], ["--offline"]):
            before = self.snapshot()
            result = subprocess.run(argv + flags, cwd=self.project, env=env,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(self.snapshot(), before)
        result = subprocess.run(argv + ["--user"], cwd=self.project, env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("approve its hooks in Codex with /hooks", result.stdout)
        self.assertTrue(install.registry_path(self.home).is_file())
        self.assertEqual(install.scan_user(self.home, {})[0].tools, ("claude", "codex"))

    def test_status_rejects_malformed_hook_configuration(self):
        self.setup_switch()
        path = self.project / ".codex" / "hooks.json"
        for config in ({"hooks": []}, {"hooks": {"SessionStart": None}},
                       {"hooks": {"SessionStart": [], "UserPromptSubmit": "bad"}}):
            path.write_text(json.dumps(config))
            self.assertFalse(install._version_hook_is_installed("codex", self.project, None))

    def test_switch_never_adds_a_claude_import_setup_left_to_the_user(self):
        own = self.home / "dotfiles" / "CLAUDE.md"
        own.parent.mkdir()
        own.write_text("OWN_RULES\n")
        claude = self.home / ".claude" / "CLAUDE.md"
        claude.parent.mkdir()
        claude.symlink_to(own)
        report = install.install(["claude"], self.project, self.home)
        install._enable_session_switch(["claude"], self.project, self.home,
                                       install.user_source(self.home), report)
        self.assertTrue(any("add the line" in line for line in report), report)
        self.assertEqual(own.read_text(), "OWN_RULES\n")
        self.assertFalse((self.home / ".claude" / "settings.json").exists())

    def test_switch_moves_the_import_setup_appended_to_a_claude_md(self):
        claude = self.home / ".claude" / "CLAUDE.md"
        claude.parent.mkdir()
        claude.write_text("OWN_RULES\n")
        report = install.install(["claude"], self.project, self.home)
        install._enable_session_switch(["claude"], self.project, self.home,
                                       install.user_source(self.home), report)
        link = install.user_targets(self.home)["claude"][0][1]
        self.assertEqual(claude.read_text(), f"OWN_RULES\n@{link}\n", report)

    def test_static_loading_restores_links_import_and_notice(self):
        install.install(["claude", "codex", "copilot"], self.project, self.home)
        install.install_version_hooks(["claude", "codex"], self.project, self.home)
        claude = self.home / ".claude" / "CLAUDE.md"
        claude.write_bytes(b"OTHER_USER_RULE\r\n" + claude.read_bytes())
        static_import = claude.read_bytes()
        settings = self.home / ".claude" / "settings.json"
        config = json.loads(settings.read_text())
        config["permissions"] = {"deny": ["Bash(curl *)"]}
        other_hook = {"hooks": [{"type": "command", "command": "echo OTHER_HOOK"}]}
        config["hooks"]["SessionStart"].append(other_hook)
        settings.write_text(json.dumps(config))
        self.setup_switch(user=True)
        report = install.install_static_loading(["claude", "codex"], self.project, self.home)
        self.assertFalse(any(line.startswith("blocked") for line in report), report)
        self.assertIn("approve its hooks in Codex with /hooks", "\n".join(report))
        source = install.user_source(self.home)
        targets = install.user_targets(self.home)
        for tool in ("claude", "codex"):
            self.assertTrue(install._link_points_to(targets[tool][0][1], source))
            self.assertTrue(install._version_hook_is_installed(tool, self.project, self.home))
        self.assertEqual(claude.read_bytes(), static_import)
        config = json.loads(settings.read_text())
        self.assertEqual(config["permissions"], {"deny": ["Bash(curl *)"]})
        self.assertIn(other_hook, config["hooks"]["SessionStart"])
        self.assertNotIn("UserPromptSubmit", config["hooks"])
        self.assertNotIn("--session-context", settings.read_text())
        self.assertFalse((install.user_data_root(self.home) / install.SESSION_LOADER_NAME).exists())
        self.assertEqual(install.scan_user(self.home, {})[0].tools, ("claude", "codex", "copilot"))
        before = self.snapshot()
        report = install.install_static_loading(["claude", "codex"], self.project, self.home)
        self.assertTrue(all(line.startswith("in place") for line in report), report)
        self.assertEqual(self.snapshot(), before)

    def test_static_loading_per_tool_keeps_the_loader_for_the_other(self):
        self.setup_switch()
        source = self.project / install.BASELINE
        agents = self.project / "AGENTS.md"
        rule = self.project / ".claude" / "rules" / install.BASELINE
        loader = install.version_hook_path(self.project, None).parent / install.SESSION_LOADER_NAME
        report = install.install_static_loading(["codex"], self.project, None)
        self.assertFalse(any(line.startswith("blocked") for line in report), report)
        self.assertEqual(agents.readlink(), Path(install.BASELINE))
        self.assertTrue(install._session_link(rule, source))
        self.assertTrue(loader.is_file())
        # Without its loader hooks Claude showed no notice, so none is added.
        (self.project / ".claude" / "settings.json").unlink()
        report = install.install_static_loading(["claude"], self.project, None)
        self.assertFalse(any(line.startswith("blocked") for line in report), report)
        self.assertTrue(install._link_points_to(rule, source))
        self.assertFalse(Path(rule.readlink()).is_absolute())
        self.assertFalse(loader.exists())
        self.assertTrue(install._version_hook_is_installed("codex", self.project, None))
        self.assertFalse(install._version_hook_is_installed("claude", self.project, None))
        self.assertFalse((self.project / ".claude" / "settings.json").exists())
        self.setup_switch()

    def test_static_loading_blocks_foreign_links_and_customized_hooks(self):
        self.setup_switch()
        path = self.project / ".codex" / "hooks.json"
        config = json.loads(path.read_text())
        config["hooks"]["SessionStart"][0]["hooks"][0]["command"] += " --custom-option"
        path.write_text(json.dumps(config))
        before = self.snapshot()
        report = install.install_static_loading(["claude", "codex"], self.project, None)
        self.assertEqual(len(report), 1, report)
        self.assertTrue(report[0].startswith("blocked static loading"), report)
        self.assertEqual(self.snapshot(), before)
        agents = self.project / "AGENTS.md"
        agents.unlink()
        agents.write_text("OTHER_PROJECT_RULE\n")
        before = self.snapshot()
        report = install.install_static_loading(["codex"], self.project, None)
        self.assertIn("instruction file", report[0])
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
