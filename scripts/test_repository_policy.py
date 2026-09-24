#!/usr/bin/env python3
"""Source loading, generated release delivery, and cross-agent entry contracts."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import build_baseline as build
import build_release
import bundle_manifest
import install
import repository_policy as policy


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aiscb-source-tests-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def source_copy(self):
        shutil.copytree(build.ROOT / "baseline", self.root / "baseline")
        shutil.copytree(build.ROOT / "scripts", self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))

    def test_loader_works_in_clean_checkout_without_dist(self):
        self.source_copy()
        result = subprocess.run([sys.executable, str(self.root / "scripts/repository_policy.py"),
                                 "aiscb:llm-agents"], cwd=self.root / "baseline",
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(result.stdout.index("[aiscb-LLM-001]"), result.stdout.index("[aiscb-AGENCY-001]"))
        self.assertFalse((self.root / "dist").exists())
        catalog = json.loads((self.root / "baseline/catalog.json").read_text())
        for name in ("aiscb:llm-applications", "aiscb:llm-agents"):
            entry = next(m for m in catalog["modules"] if m["id"] == name)
            self.assertIn(f"Verified {name}; {catalog['baseline_id']}\n\n", result.stdout)
            self.assertIn((self.root / "baseline" / entry["file"]).read_text(), result.stdout)
        for ids in (["aiscb:llm-agents", "https://untrusted.invalid/rules"], ["../outside"]):
            result = subprocess.run([sys.executable, str(self.root / "scripts/repository_policy.py"), *ids],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")

    def test_stale_source_refuses_without_output(self):
        self.source_copy()
        target = self.root / "baseline/modules/aiscb-web.md"
        target.write_text(target.read_text() + "\nChanged\n")
        result = subprocess.run([sys.executable, str(self.root / "scripts/repository_policy.py"), "--catalog"],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_source_loader_rejects_obsolete_module_ids(self):
        for old in ("web-auth", "web-auth-crypto", "data-boundaries", "secrets-bootstrap",
                    "deployment-runtime", "agent-systems", "retrieval-memory",
                    "mcp-integrations"):
            result = subprocess.run(
                [sys.executable, str(build.ROOT / "scripts/repository_policy.py"),
                 "aiscb:llm-applications", "aiscb:" + old],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertIn("unknown module", result.stderr)

    def test_build_refuses_symlinked_dist(self):
        self.source_copy()
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / "dist").symlink_to(outside, target_is_directory=True)
        result = subprocess.run([sys.executable, str(self.root / "scripts/build_baseline.py"), "--write"],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

    def test_three_repository_entry_points(self):
        agents = (build.ROOT / "AGENTS.md").read_text()
        self.assertIn("baseline/catalog.json", agents)
        self.assertIn("scripts/repository_policy.py", agents)
        self.assertIn("obtain explicit approval", agents)
        claude = (build.ROOT / "CLAUDE.md").read_text().splitlines()
        self.assertEqual(claude, ["@AGENTS.md", "@baseline/aiscb-core.md"])
        copilot = (build.ROOT / ".github/copilot-instructions.md").read_text()
        for reference in ("AGENTS.md", "baseline/aiscb-core.md", "baseline/catalog.json", "scripts/repository_policy.py"):
            self.assertIn(reference, copilot)
        self.assertLess(len(copilot), 4000)
        self.assertNotIn("@secure-coding-baseline.md", copilot)
        for name in ("secure-coding-baseline.md", "bundle.json", "bundle.json.sig"):
            self.assertFalse((build.ROOT / name).exists())

    def test_staging_is_versioned_immutable_and_reproducible(self):
        self.source_copy()
        target = build_release.stage(build.VERSION, "1", self.root)
        self.assertEqual(target, self.root / "dist" / build.BASELINE_ID / "bundle-1")
        self.assertEqual((target / install.BASELINE).read_bytes(), build.validate()[2])
        self.assertFalse((target / "bundle.json.sig").exists())
        with self.assertRaisesRegex(ValueError, "already exists"):
            build_release.stage(build.VERSION, "1", self.root)
        for version, revision in (("99.0.0", "1"), (build.VERSION, "../2"), (build.VERSION, "0")):
            with self.assertRaises(ValueError):
                build_release.stage(version, revision, self.root)
        other = build_release.stage(build.VERSION, "2", self.root)
        self.assertEqual((target / "bundle.json").read_bytes(), (other / "bundle.json").read_bytes())
        with self.assertRaises((ValueError, OSError)):
            bundle_manifest.verify_release(target)

    def test_assets_are_bounded_and_bad_bytes_fail_manifest_check(self):
        files = {name: (build.validate()[2] if name == install.BASELINE else (build.ROOT / name).read_bytes())
                 for name in install.BUNDLE_FILES}
        files["bundle.json"] = install.manifest_document(files)
        files["bundle.json.sig"] = b"fixture signature"
        tag = build.BASELINE_ID
        prefix = f"https://github.com/{install.GITHUB_REPOSITORY}/releases/download/{tag}/"
        def fetch(url):
            if url.startswith(install.CONTENTS_ROOT_URL):
                raise urllib.error.HTTPError(url, 404, "absent", None, None)
            return {"tag_name": tag, "assets": [
                {"name": Path(name).name, "size": len(content), "browser_download_url": prefix + Path(name).name}
                for name, content in files.items()]}
        by_name = {Path(name).name: content for name, content in files.items()}
        with patch.object(install, "read_release_asset", side_effect=lambda url, limit: by_name[url.rsplit("/", 1)[-1]]):
            result = install.fetch_verified_bundle(fetch, tag, install.SemVer.parse(build.VERSION), verify=lambda a, b: None)
            self.assertEqual(set(result), set(install.BUNDLE_FILES))
            by_name[install.BASELINE] += b"tamper"
            with self.assertRaisesRegex(ValueError, "signed manifest"):
                install.fetch_verified_bundle(fetch, tag, install.SemVer.parse(build.VERSION), verify=lambda a, b: None)
        for url in ("http://github.com/x", "https://github.com.evil.test/x", "https://localhost/x"):
            with self.assertRaises(ValueError):
                install.validate_asset_url(url)

    def test_generated_bootstrap_hashes_match_manifest(self):
        self.source_copy()
        target = build_release.stage(build.VERSION, "1", self.root)
        script = (target / "setup.sh").read_text()
        manifest = json.loads((target / "bundle.json").read_text())
        for entry in manifest["files"].values():
            self.assertIn(entry["sha256"], script)
        self.assertNotIn("@BASELINE_SHA@", script)
        self.assertIn("--proto-redir '=https'", script)
        self.assertIn("--max-filesize", script)
        self.assertEqual(subprocess.run(["sh", "-n", str(target / "setup.sh")]).returncode, 0)

    def test_asset_bootstrap_executes_only_checked_files(self):
        self.source_copy()
        target = build_release.stage(build.VERSION, "1", self.root)
        commands = self.root / "bin"
        commands.mkdir()
        curl = commands / "curl"
        curl.write_text(f"#!{sys.executable}\n"
                        "import os, pathlib, sys\n"
                        "args=sys.argv[1:]\n"
                        "name=args[-1].rsplit('/', 1)[-1]\n"
                        "root=pathlib.Path(os.environ['AISCB_TEST_BUNDLE'])\n"
                        "path=root/name if name.endswith('.md') else root/'scripts'/name\n"
                        "data=path.read_bytes()\n"
                        "if os.environ.get('AISCB_TEST_TAMPER') == name: data += b'tamper'\n"
                        "if os.environ.get('AISCB_TEST_LARGE') == name: data += b'x' * 600000\n"
                        "pathlib.Path(args[args.index('--output')+1]).write_bytes(data)\n")
        curl.chmod(0o755)
        env = {**os.environ, "PATH": str(commands) + os.pathsep + os.environ["PATH"],
               "AISCB_TEST_BUNDLE": str(target)}
        for mode, expected in (({}, 0), ({"AISCB_TEST_TAMPER": "install.py"}, 2),
                               ({"AISCB_TEST_LARGE": "install.py"}, 2)):
            result = subprocess.run(["sh", str(target / "setup.sh"), "--help"],
                                    env={**env, **mode}, capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)
            if expected:
                self.assertNotIn("usage: install.py", result.stdout)
            else:
                self.assertIn("usage: install.py", result.stdout)

    def test_release_gate_requires_actual_signature(self):
        self.source_copy()
        target = build_release.stage(build.VERSION, "1", self.root)
        key = self.root / "test-only-key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
        signer = bundle_manifest.public_key_line(key)
        with patch.object(install, "ALLOWED_SIGNERS", (signer,)):
            bundle_manifest.sign_manifest(target, key)
            bundle_manifest.verify_release(target)
            baseline = target / install.BASELINE
            baseline.write_bytes(baseline.read_bytes() + b"tamper")
            with self.assertRaisesRegex(ValueError, "does not describe"):
                bundle_manifest.verify_release(target)

    def signed_bundle(self):
        self.source_copy()
        target = build_release.stage(build.VERSION, "1", self.root)
        key = self.root / "test-only-key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
        signers = patch.object(install, "ALLOWED_SIGNERS", (bundle_manifest.public_key_line(key),))
        signers.start()
        self.addCleanup(signers.stop)
        return target, key

    def test_signing_refuses_unknown_or_malformed_keys(self):
        self.source_copy()
        target = build_release.stage(build.VERSION, "1", self.root)
        key = self.root / "unknown-key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
        with self.assertRaisesRegex(ValueError, "does not carry this key"):
            bundle_manifest.sign_manifest(target, key)
        self.assertFalse((target / install.SIGNATURE_NAME).exists())
        broken = self.root / "broken-key"
        broken.with_name("broken-key.pub").write_text("ssh-ed25519\n")
        with self.assertRaisesRegex(ValueError, "not an OpenSSH public key"):
            bundle_manifest.public_key_line(broken)

    def test_release_gate_checks_directory_and_bootstrap(self):
        target, key = self.signed_bundle()
        bundle_manifest.sign_manifest(target, key)
        bundle_manifest.verify_release(target)
        renamed = target.with_name("staging")
        shutil.copytree(target, renamed)
        with self.assertRaisesRegex(ValueError, "dist/aiscb-VERSION/bundle-N"):
            bundle_manifest.verify_release(renamed)
        setup = target / "setup.sh"
        original = setup.read_text()
        setup.write_text(original.replace(f"aiscb-bundle-{build.VERSION}-1", f"aiscb-bundle-{build.VERSION}-7"))
        with self.assertRaisesRegex(ValueError, "bootstrap release mismatch"):
            bundle_manifest.verify_release(target)
        digest = json.loads((target / "bundle.json").read_text())["files"][install.BASELINE]["sha256"]
        setup.write_text(original.replace(digest, "0" * 64))
        with self.assertRaisesRegex(ValueError, "bootstrap hashes"):
            bundle_manifest.verify_release(target)

    def test_manifest_command_line_writes_signs_and_verifies(self):
        target, key = self.signed_bundle()
        (target / "bundle.json").unlink()
        quiet = patch("sys.stdout"), patch("sys.stderr")
        with quiet[0], quiet[1]:
            self.assertEqual(bundle_manifest.main(["--bundle-dir", str(target), "--write"]), 0)
            self.assertTrue((target / "bundle.json").is_file())
            self.assertEqual(bundle_manifest.main(["--bundle-dir", str(target), "--verify"]), 1)
            self.assertEqual(bundle_manifest.main(["--bundle-dir", str(target), "--sign", str(key)]), 0)
            self.assertEqual(bundle_manifest.main(["--bundle-dir", str(target), "--verify"]), 0)
            (target / install.BASELINE).write_bytes(b"tampered\n")
            self.assertEqual(bundle_manifest.main(["--bundle-dir", str(target), "--verify"]), 1)

    def test_staging_refuses_stale_catalog_and_symlinked_dist(self):
        self.source_copy()
        catalog = self.root / "baseline/catalog.json"
        original = catalog.read_bytes()
        catalog.write_bytes(original.replace(b'"size": ', b'"size": 1', 1))
        with self.assertRaisesRegex(ValueError, "stale catalog metadata"):
            build_release.stage(build.VERSION, "1", self.root)
        catalog.write_bytes(original)
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / "dist").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink in release staging path"):
            build_release.stage(build.VERSION, "1", self.root)
        self.assertEqual(list(outside.iterdir()), [])

    def test_staging_command_line_reports_refusal_and_target(self):
        self.source_copy()
        script = self.root / "scripts/build_release.py"
        refused = subprocess.run([sys.executable, str(script), "--version", "99.0.0", "--revision", "1"],
                                 capture_output=True, text=True, timeout=60)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("Release staging refused", refused.stderr)
        self.assertFalse((self.root / "dist").exists())
        staged = subprocess.run([sys.executable, str(script), "--version", build.VERSION, "--revision", "3"],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(staged.returncode, 0, staged.stderr)
        self.assertEqual(Path(staged.stdout.strip()),
                         self.root / "dist" / build.BASELINE_ID / "bundle-3")
        argv = ["build_release.py", "--version", build.VERSION, "--revision", "4"]
        with patch.object(sys, "argv", argv), patch("sys.stderr"), \
                patch.object(build_release, "stage", side_effect=ValueError("exists")):
            with self.assertRaises(SystemExit) as refused_in_process:
                build_release.main()
        self.assertEqual(refused_in_process.exception.code, 1)

    def test_embedded_installer_resources_fail_closed(self):
        import bundle_resources
        from types import SimpleNamespace
        self.source_copy()
        embedded = SimpleNamespace(EMBEDDED_POLICY="{}", INSTALLER_SOURCE=self.root / "scripts/install.py",
                                   MAX_INSTALLER_BYTES=install.MAX_INSTALLER_BYTES,
                                   read_limited=install.read_limited)
        # A signed release installer reproduces itself instead of re-embedding sources.
        self.assertEqual(bundle_resources.installer_bytes(embedded),
                         (self.root / "scripts/install.py").read_bytes())
        checkout = SimpleNamespace(EMBEDDED_POLICY=None, MAX_INSTALLER_BYTES=install.MAX_INSTALLER_BYTES)
        result = bundle_resources.installer_bytes(checkout, self.root)
        import ast
        slot = next(line for line in result.decode().splitlines() if line.startswith("EMBEDDED_POLICY = "))
        embedded_files = json.loads(ast.literal_eval(slot.split(" = ", 1)[1]))
        self.assertEqual(embedded_files["baseline/catalog.json"],
                         (self.root / "baseline/catalog.json").read_text())
        self.assertIn("scripts/policy_setup.py", embedded_files)
        with self.assertRaisesRegex(ValueError, "size limit"):
            bundle_resources.installer_bytes(SimpleNamespace(EMBEDDED_POLICY=None, MAX_INSTALLER_BYTES=1000), self.root)
        installer = self.root / "scripts/install.py"
        installer.write_text(installer.read_text().replace(bundle_resources.MARKER, "EMBEDDED_POLICY = None"))
        with self.assertRaisesRegex(ValueError, "exactly one release resource slot"):
            bundle_resources.installer_bytes(checkout, self.root)
        catalog = self.root / "baseline/catalog.json"
        catalog.write_bytes(catalog.read_bytes().replace(b'"size": ', b'"size": 1', 1))
        with self.assertRaisesRegex(ValueError, "stale catalog metadata"):
            bundle_resources.installer_bytes(checkout, self.root)


if __name__ == "__main__":
    unittest.main()
