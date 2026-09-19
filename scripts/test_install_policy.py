#!/usr/bin/env python3
"""Exercise policy trust, loading, installation, and preservation boundaries."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import install_policy as installer
import policy_loader as loader

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("org_build", ROOT / "examples/organization-bundle/build.py")
org = importlib.util.module_from_spec(spec)
spec.loader.exec_module(org)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aiscb-policy-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def installed(self):
        installer.install(["codex"], self.root, modular=True)
        record = json.loads((self.root / ".aiscb/installation.json").read_text())
        digest = record["digest"]
        return self.root / ".aiscb/releases" / digest, digest

    def test_dependency_loaded_before_agent_rules(self):
        release, digest = self.installed()
        text = loader.render(release, digest, ["aiscb:agent-systems"])
        self.assertLess(text.index("[aiscb-LLM-001]"), text.index("[aiscb-AGENCY-001]"))
        self.assertNotIn("[aiscb-WEB-001]", text)
        self.assertEqual(text.count("[aiscb-LLM-001]"), 1)
        for tool in installer.ENTRY_POINTS:
            installer.install([tool], self.root, modular=True)
            initial = (self.root / installer.ENTRY_POINTS[tool]).read_text()
            self.assertIn("[aiscb-DESIGN-001]", initial)
            self.assertIn("aiscb:agent-systems", initial)
            self.assertNotIn("[aiscb-AGENCY-001]", initial)
        self.assertIn("match", installer.status(self.root))

    def test_loader_failure_returns_no_partial_policy(self):
        release, digest = self.installed()
        for ids in (["aiscb:llm-features", "https://evil.invalid/policy"], ["../../outside"]):
            result = subprocess.run([sys.executable, str(release / "policy_loader.py"),
                                     "--digest", digest, *ids], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
        module = release / "modules/aiscb-llm-features.md"
        module.write_text(module.read_text() + "tamper")
        with self.assertRaisesRegex(ValueError, "mismatch"):
            loader.render(release, digest, ["aiscb:agent-systems"])

    def test_new_modules_and_independent_mcp_loading(self):
        release, digest = self.installed()
        text = loader.render(release, digest, ["aiscb:mcp-integrations"])
        self.assertLess(text.index("[aiscb-EGRESS-001]"), text.index("[aiscb-MCPAUTH-001]"))
        self.assertNotIn("[aiscb-AGENCY-001]", text)
        self.assertNotIn("[aiscb-LLM-001]", text)
        text = loader.render(release, digest, ["aiscb:retrieval-memory", "aiscb:agent-systems"])
        self.assertEqual(text.count("[aiscb-LLM-001]"), 1)
        self.assertLess(text.index("[aiscb-LLM-001]"), text.index("[aiscb-RETRIEVAL-001]"))
        for tool in installer.ENTRY_POINTS:
            installer.install([tool], self.root, modular=True)
            initial = (self.root / installer.ENTRY_POINTS[tool]).read_text()
            for name in ("mcp-integrations", "retrieval-memory"):
                self.assertIn("aiscb:" + name, initial)
            self.assertNotIn("[aiscb-MCPAUTH-001]", initial)
            self.assertNotIn("[aiscb-RETRIEVAL-001]", initial)

    def test_update_switches_all_managed_tools_together(self):
        installer.install(list(installer.ENTRY_POINTS), self.root, modular=True)
        installer.install(["codex"], self.root, modular=False)
        for rel in installer.ENTRY_POINTS.values():
            text = (self.root / rel).read_text()
            self.assertIn("[aiscb-MCPAUTH-001]", text)
            self.assertIn("[aiscb-RETRIEVAL-001]", text)
            self.assertNotIn("## Installed module adapter", text)
        self.assertIn("match", installer.status(self.root))
        installer.install(["claude"], self.root, modular=True)
        for rel in installer.ENTRY_POINTS.values():
            self.assertNotIn("[aiscb-MCPAUTH-001]", (self.root / rel).read_text())

    def test_update_refuses_drift_in_another_managed_tool(self):
        installer.install(["codex", "claude"], self.root, modular=True)
        before = (self.root / "AGENTS.md").read_bytes()
        entry = self.root / "CLAUDE.md"
        entry.write_text(entry.read_text().replace("Secure Design", "Altered"))
        with self.assertRaisesRegex(ValueError, "modified"):
            installer.install(["codex"], self.root, modular=False)
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), before)

    def test_package_update_and_rollback_keep_one_snapshot(self):
        import shlex
        installer.install(list(installer.ENTRY_POINTS), self.root, modular=True)
        record_path = self.root / ".aiscb/installation.json"
        original = json.loads(record_path.read_text())["digest"]
        bundle = self.root / "bundle"
        _, digest = org.build(org.HERE, ROOT / "baseline", bundle, self.root / "managed")
        installer.install(["codex"], self.root, modular=True, bundle=bundle, expected=digest)
        updated = json.loads(record_path.read_text())["digest"]
        self.assertNotEqual(original, updated)
        for rel in installer.ENTRY_POINTS.values():
            text = (self.root / rel).read_text()
            self.assertIn(updated, text)
            self.assertIn("acme-sec-1.0.0", text)
        # Execute the exact generated command from outside the target project.
        text = (self.root / "AGENTS.md").read_text()
        command = text.split("Load selected IDs with `", 1)[1].split(" MODULE_ID", 1)[0]
        result = subprocess.run([*shlex.split(command), "aiscb:mcp-integrations"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[aiscb-MCPAUTH-001]", result.stdout)
        installer.install(["claude"], self.root, modular=True)
        self.assertEqual(json.loads(record_path.read_text())["digest"], original)
        for rel in installer.ENTRY_POINTS.values():
            text = (self.root / rel).read_text()
            self.assertIn(original, text)
            self.assertNotIn("acme-sec-1.0.0", text)
        self.assertTrue((self.root / ".aiscb/releases" / updated).is_dir())
        self.assertIn("match", installer.status(self.root))

    def test_invalid_installation_record_is_refused(self):
        self.installed()
        path = self.root / ".aiscb/installation.json"
        record = json.loads(path.read_text())
        record["entries"]["unrelated.md"] = "0" * 64
        path.write_text(json.dumps(record))
        for action in (installer.status, installer.uninstall):
            with self.assertRaisesRegex(ValueError, "invalid local installation record"):
                action(self.root)

    def test_manifest_tamper_and_symlink_rejected(self):
        release, digest = self.installed()
        with self.assertRaisesRegex(ValueError, "manifest digest"):
            loader.load_package(release, "0" * 64)
        module = release / "modules/aiscb-agent-systems.md"
        backup = self.root / "outside.md"
        module.rename(backup)
        module.symlink_to(backup)
        with self.assertRaisesRegex(ValueError, "symlink"):
            loader.render(release, digest, ["aiscb:agent-systems"])

    def test_cycles_unknown_dependencies_and_duplicate_ids(self):
        release, _ = self.installed()
        path = release / "policy.json"
        initial = path.read_bytes()
        for mutation in (lambda p: p["modules"][0].update(requires=["aiscb:missing"]),
                         lambda p: p["modules"][0].update(requires=[p["modules"][0]["id"]]),
                         lambda p: p["modules"].append(p["modules"][0])):
            package = json.loads(initial)
            mutation(package)
            changed = json.dumps(package).encode()
            path.write_bytes(changed)
            with self.assertRaises(ValueError):
                loader.load_package(release, loader.digest(changed))

    def test_update_and_uninstall_preserve_user_content(self):
        entry = self.root / "AGENTS.md"
        entry.write_text("User preferences.\n")
        self.installed()
        entry.write_text(entry.read_text() + "\nMore preferences.\n")
        installer.install(["codex"], self.root, modular=False)
        self.assertIn("[aiscb-AGENCY-001]", entry.read_text())
        installer.uninstall(self.root)
        self.assertIn("User preferences.", entry.read_text())
        self.assertIn("More preferences.", entry.read_text())
        self.assertNotIn(installer.START, entry.read_text())
        self.assertTrue((self.root / ".aiscb/releases").is_dir())

    def test_conflict_has_no_install_side_effect(self):
        (self.root / "AGENTS.md").write_text("Use secure-coding-baseline.md")
        with self.assertRaisesRegex(ValueError, "existing baseline"):
            installer.install(["claude", "codex"], self.root, modular=True)
        self.assertFalse((self.root / "CLAUDE.md").exists())
        self.assertFalse((self.root / ".aiscb").exists())

    def test_modified_block_is_not_overwritten(self):
        self.installed()
        path = self.root / "AGENTS.md"
        path.write_text(path.read_text().replace("Secure Design", "Changed Design"))
        with self.assertRaisesRegex(ValueError, "modified"):
            installer.install(["codex"], self.root, modular=True)
        with self.assertRaisesRegex(ValueError, "modified"):
            installer.uninstall(self.root)

    def test_instruction_parent_symlink_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / ".github").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            installer.install(["copilot"], self.root, modular=True)
        self.assertEqual(list(outside.iterdir()), [])

    def test_installer_cli_status_and_uninstall(self):
        def run(*args):
            return subprocess.run([sys.executable, str(ROOT / "scripts/install.py"),
                                   *args, "--into", str(self.root)],
                                  capture_output=True, text=True)
        self.assertEqual(run("codex", "--modular").returncode, 0)
        self.assertEqual(run("codex", "--complete").returncode, 0)
        self.assertIn("[aiscb-MCPAUTH-001]", (self.root / "AGENTS.md").read_text())
        self.assertNotEqual(run("codex", "--complete", "--modular").returncode, 0)
        self.assertEqual(run("--status", "--offline").returncode, 0)
        self.assertNotEqual(run("codex").returncode, 0)
        self.assertEqual(run("--uninstall").returncode, 0)

    def test_local_install_does_not_accept_unverified_source(self):
        from unittest.mock import patch
        original = installer.build_baseline.validate
        def altered(root):
            catalog, artifacts, eager = original(root)
            artifacts[0][0]["sha256"] = "0" * 64
            return catalog, artifacts, eager
        with patch.object(installer.build_baseline, "validate", side_effect=altered):
            with self.assertRaisesRegex(ValueError, "stale source"):
                installer.install(["codex"], self.root, modular=True)
        self.assertFalse((self.root / ".aiscb").exists())

    def test_remote_three_file_install_refuses_missing_local_helpers(self):
        import shutil
        distribution = self.root / "distribution"
        distribution.mkdir()
        for name in ("install.py", "show_baseline_version.py"):
            shutil.copyfile(ROOT / "scripts" / name, distribution / name)
        (distribution / "secure-coding-baseline.md").write_bytes(installer.build_baseline.validate()[2])
        project = self.root / "project"
        project.mkdir()
        for mode in ("--modular", "--complete"):
            result = subprocess.run([sys.executable, "-I", str(distribution / "install.py"),
                                     "codex", mode, "--into", str(project)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Local policy setup refused", result.stderr)
            self.assertEqual(list(project.iterdir()), [])

    def test_organization_install_and_blueprints(self):
        bundle = self.root / "bundle"
        _, digest = org.build(org.HERE, ROOT / "baseline", bundle, self.root / "unused-build-root")
        skill = (bundle / "adapters/codex/skills/aiscb-agent-systems/SKILL.md").read_text()
        self.assertLess(skill.index("[aiscb-LLM-001]"), skill.index("[aiscb-AGENCY-001]"))
        target = self.root / "project"
        target.mkdir()
        with self.assertRaisesRegex(ValueError, "trusted digest"):
            installer.install(["codex"], target, bundle=bundle, expected="0" * 64)
        self.assertFalse((target / ".aiscb").exists())
        installer.install(["codex"], target, bundle=bundle, expected=digest, modular=True)
        record = json.loads((target / ".aiscb/installation.json").read_text())
        release = target / ".aiscb/releases" / record["digest"]
        text = loader.render(release, record["digest"], ["acme:authentication", "aiscb:agent-systems"])
        self.assertIn("Blueprint values:", text)

        for module, rule in (("mcp-integrations", "MCPAUTH"), ("retrieval-memory", "RETRIEVAL")):
            selected = loader.render(release, record["digest"], ["aiscb:" + module])
            self.assertIn(f"[aiscb-{rule}-001]", selected)
            self.assertIn(f"[aiscb-{rule}-001]", (bundle / "complete-policy.md").read_text())
            self.assertIn(f"[aiscb-{rule}-001]", (bundle / "adapters/gateway/system-block.md").read_text())
            for adapter in ("claude-code", "codex", "copilot"):
                skill = (bundle / f"adapters/{adapter}/skills/aiscb-{module}/SKILL.md").read_text()
                self.assertIn(f"[aiscb-{rule}-001]", skill)
        self.assertIn("[aiscb-LLM-001]", text)
        self.assertNotIn("unused-build-root", text)
        installer.install(["codex"], target, bundle=bundle, expected=digest)
        text = (target / "AGENTS.md").read_text()
        self.assertIn("[aiscb-AGENTAUTH-001]", text)
        self.assertIn("[ACME-", text)
        self.assertIn("Blueprint values:", text)

    def test_org_builder_rejects_collisions_and_cross_release(self):
        import shutil
        source = self.root / "org"
        shutil.copytree(org.HERE, source)
        for rel in ("catalog.json", "packs/authentication.md"):
            path = source / rel
            path.write_text(path.read_text().replace("acme:authentication", "aiscb:web-auth"))
        with self.assertRaisesRegex(org.BuildError, "collid"):
            org.build(source, ROOT / "baseline", self.root / "bad", self.root / "install")
        upstream = self.root / "upstream"
        shutil.copytree(ROOT / "baseline", upstream)
        path = upstream / "catalog.json"
        initial = json.loads(path.read_text())
        for field, value in (("version", "99.0.0"), ("publisher", "other"),
                             ("requires", ["aiscb:missing"]), ("requires", ["aiscb:web-auth"])):
            catalog = json.loads(json.dumps(initial))
            catalog["modules"][0][field] = value
            path.write_text(json.dumps(catalog))
            with self.assertRaises(org.BuildError):
                org.load_aiscb(upstream)


if __name__ == "__main__":
    unittest.main()
