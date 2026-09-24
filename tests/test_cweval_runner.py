#!/usr/bin/env python3
"""Boundary checks for the optional CWEval adapter; no model or Docker calls."""

import json
import io
import os
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import cweval_runner as runner


class CWEvalRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tasks = self.root / "benchmark/core/py"
        self.tasks.mkdir(parents=True)
        (self.tasks / "cwe_020_0_task.py").write_text(
            "def validate(value):\n    '''Validate value.'''\n"
            "# BEGIN SOLUTION\nSECRET_REFERENCE_ANSWER\n")
        (self.tasks / "cwe_020_0_test.py").write_text("SECRET_TEST_ASSERTION\n")

    def test_prompt_ends_at_solution_and_never_reads_tests(self):
        prompt = runner.task_prompt(self.root, "cwe_020_0")
        self.assertIn("def validate", prompt)
        self.assertNotIn("SECRET_REFERENCE_ANSWER", prompt)
        self.assertNotIn("SECRET_TEST_ASSERTION", prompt)
        with self.assertRaises(ValueError):
            runner.task_prompt(self.root, "../../secret")

    def test_linked_task_is_rejected(self):
        (self.tasks / "cwe_022_0_task.py").symlink_to("cwe_020_0_task.py")
        (self.tasks / "cwe_022_0_test.py").write_text("pass\n")
        with self.assertRaises(ValueError):
            runner.task_prompt(self.root, "cwe_022_0")

    def test_generation_requires_single_complete_code_block(self):
        self.assertEqual(runner.extract_code("```python\ndef safe():\n    return True\n```"),
                         "def safe():\n    return True\n")
        self.assertEqual(runner.extract_code("Explanation\n```python\npass\n```\nNote"),
                         "pass\n")
        for reply in ("no code", "```python\npass\n```\n```python\npass\n```"):
            with self.subTest(reply=reply), self.assertRaises(ValueError):
                runner.extract_code(reply)

    def test_generation_keeps_arms_separate_and_uses_only_task_prompt(self):
        prompts = []
        baseline_visible = []
        def fake_reply(_tool, _workdir, prompt, _model, _timeout):
            prompts.append(prompt)
            baseline_visible.append((_workdir / ".claude/rules" /
                                     runner.baseline_run.BASELINE.name).is_file())
            return "```python\ndef validate(value):\n    return bool(value)\n```"
        with patch.object(runner, "assistant_reply", side_effect=fake_reply):
            result = self.root / "result"
            result.mkdir()
            runs = runner.generate({"cwe_020_0": runner.task_prompt(
                self.root, "cwe_020_0")}, "claude", "model", 1, 10, result)
        self.assertEqual([run["status"] for run in runs], ["complete", "complete"])
        self.assertEqual(len(prompts), 2)
        self.assertEqual(prompts[0], prompts[1])
        self.assertEqual(baseline_visible, [False, True])
        self.assertNotIn("SECRET_REFERENCE_ANSWER", "".join(prompts))
        self.assertNotIn("SECRET_TEST_ASSERTION", "".join(prompts))
        for arm in ("control", "baseline"):
            self.assertTrue((result / arm / "generated_0/core/py/cwe_020_0_raw.py").is_file())

    def test_incomplete_response_does_not_create_evaluation_input(self):
        result = self.root / "result"
        result.mkdir()
        with patch.object(runner, "assistant_reply", return_value="No code"), \
             patch.dict(runner.baseline_run.ADAPTERS["claude"],
                        {"install": lambda workdir: None}):
            runs = runner.generate({"cwe_020_0": "def validate(value):"},
                                   "claude", "model", 1, 10, result)
        self.assertTrue(all(run["status"] == "incomplete" for run in runs))
        self.assertFalse((result / "baseline/generated_0").exists())

    def test_preflight_detects_control_contamination(self):
        result = self.root / "result"
        result.mkdir()
        baseline_id = runner.baseline_run.baseline_identifier()
        with patch.object(runner, "assistant_reply",
                          return_value=f"`baseline-id: {baseline_id}`"):
            probes = runner.preflight("claude", "model", 10, result)
        self.assertFalse(probes[0]["ok"])
        self.assertTrue(probes[1]["ok"])

    def test_generation_commands_disable_model_tools(self):
        (self.root / "_agent_reply.txt").write_text("```python\npass\n```\n")
        with patch.object(runner.baseline_run, "run_capture",
                          return_value=(0, "reply", "")) as capture:
            runner.assistant_reply("claude", self.root, "task", "model", 10)
            claude = capture.call_args.args[0]
            self.assertEqual(claude[claude.index("--tools") + 1], "")
            self.assertIn("--strict-mcp-config", claude)
            self.assertEqual(claude[claude.index("--setting-sources") + 1],
                             "project")
            runner.assistant_reply("codex", self.root, "task", "model", 10)
            codex = capture.call_args.args[0]
            self.assertIn("shell_tool", codex)
            self.assertIn("unified_exec", codex)
            self.assertIn('web_search="disabled"', codex)
            self.assertIn("read-only", codex)

    def test_codex_profile_isolated_without_copying_rules_or_credentials(self):
        source = self.root / "codex-home"
        source.mkdir()
        auth = source / "auth.json"
        auth.write_text("test credential placeholder")
        (source / "AGENTS.md").write_text("baseline-id: aiscb-0.1.18")
        (source / "config.toml").write_text("test setting")
        with patch.dict(os.environ, {"CODEX_HOME": str(source)}):
            with runner.isolated_codex_home("codex"):
                isolated = Path(os.environ["CODEX_HOME"])
                self.assertNotEqual(isolated, source)
                self.assertTrue((isolated / "auth.json").is_symlink())
                self.assertEqual((isolated / "auth.json").resolve(), auth)
                self.assertFalse((isolated / "AGENTS.md").exists())
                self.assertFalse((isolated / "config.toml").exists())
            self.assertEqual(os.environ["CODEX_HOME"], str(source))
            self.assertFalse(isolated.exists())

    def test_scoring_rejects_missing_samples_and_counts_joint_success(self):
        arm = self.root / "arm"
        arm.mkdir()
        path = arm / "res_all.json"
        key = "evals/aiscb/generated_X/core/py/cwe_020_0_test.py"
        path.write_text(json.dumps({key: {"functional": [True, True, False],
                                          "secure": [True, False, True]}}))
        score = runner.read_scores(arm, ["cwe_020_0"], 3)["cwe_020_0"]
        self.assertEqual((score["functional"], score["func_secure"]), (2, 1))
        with self.assertRaises(ValueError):
            runner.read_scores(arm, ["cwe_020_0"], 2)

    def test_report_compares_joint_success_across_all_cases(self):
        scores = {
            "control": {
                "cwe_020_0": {"functional": 2, "func_secure": 1, "samples": 3},
                "cwe_022_0": {"functional": 1, "func_secure": 1, "samples": 3},
            },
            "baseline": {
                "cwe_020_0": {"functional": 3, "func_secure": 2, "samples": 3},
                "cwe_022_0": {"functional": 2, "func_secure": 2, "samples": 3},
            },
        }
        overall = runner.write_report(self.root, scores, [], "codex", "model",
                                      "a" * 40,
                                      "co1lin/cweval@sha256:" + "b" * 64,
                                      "all-python-core")
        self.assertEqual(overall["control"]["func_secure_percent"], 33.3)
        self.assertEqual(overall["baseline"]["func_secure_percent"], 66.7)
        self.assertEqual(overall["delta_percentage_points"], 33.3)
        self.assertEqual(overall["baseline"]["functional_percent"], 83.3)
        document = json.loads((self.root / "report.json").read_text())
        self.assertEqual(document["overall"], overall)
        self.assertEqual(document["tool"], "codex")
        self.assertEqual(document["selection"], "all-python-core")
        self.assertEqual(document["metric"], "func-sec@1")
        self.assertEqual(document["repeats"], 3)
        self.assertEqual(document["cases"], ["cwe_020_0", "cwe_022_0"])
        report = (self.root / "report.md").read_text()
        self.assertIn("| control | 3/6 (50.0%) | 2/6 (33.3%) |", report)
        self.assertIn("| baseline | 5/6 (83.3%) | 4/6 (66.7%) |", report)
        self.assertIn("+33.3 percentage points", report)

    def test_local_config_runs_without_required_cli_args_and_allows_override(self):
        config = self.root / "cweval.local.json"
        config.write_text(json.dumps({
            "cweval_root": str(self.root), "revision": "a" * 40,
            "image": "co1lin/cweval@sha256:" + "b" * 64,
            "tool": "codex", "model": "model", "cases": "cwe_020_0",
            "repeats": 1,
        }))
        defaults = runner.local_config_args(config)
        output = io.StringIO()
        with patch.object(runner, "local_config_args", return_value=defaults), \
             patch.object(runner, "checked_checkout", return_value=self.root), \
             patch.object(runner, "task_prompt", return_value="def validate(value):"), \
             redirect_stdout(output):
            self.assertEqual(runner.main(["--dry-run", "--repeats", "2"]), 0)
        self.assertIn("1 cases × 2 repeats × 2 arms = 4 assistant runs",
                      output.getvalue())

    def test_full_python_selection_ignores_local_case_and_repeat_settings(self):
        (self.tasks / "cwe_022_0_task.py").write_text(
            "def safe(path):\n    pass\n# BEGIN SOLUTION\nreturn path\n")
        (self.tasks / "cwe_022_0_test.py").write_text("pass\n")
        defaults = ["--cweval-root", str(self.root), "--revision", "a" * 40,
                    "--image", "co1lin/cweval@sha256:" + "b" * 64,
                    "--model", "model", "--cases", "cwe_020_0",
                    "--repeats", "1"]
        output = io.StringIO()
        with patch.object(runner, "local_config_args", return_value=defaults), \
             patch.object(runner, "checked_checkout", return_value=self.root), \
             redirect_stdout(output):
            self.assertEqual(runner.main(["--dry-run", "--all-python",
                                          "--repeats", "3"]), 0)
        self.assertIn("2 cases × 3 repeats × 2 arms = 12 assistant runs",
                      output.getvalue())
        self.assertIn("cwe_020_0, cwe_022_0", output.getvalue())

    def test_full_python_selection_rejects_missing_test_and_linked_directory(self):
        (self.tasks / "cwe_022_0_task.py").write_text(
            "def safe(path):\n    pass\n# BEGIN SOLUTION\nreturn path\n")
        names = runner.python_core_cases(self.root)
        self.assertEqual(names, ["cwe_020_0", "cwe_022_0"])
        with self.assertRaisesRegex(ValueError, "missing or linked"):
            runner.task_prompt(self.root, names[1])
        other_root = self.root / "linked-root"
        (other_root / "benchmark/core").mkdir(parents=True)
        (other_root / "benchmark/core/py").symlink_to(self.tasks,
                                                       target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "must not be linked"):
            runner.python_core_cases(other_root)

    def test_full_python_selection_caps_case_count(self):
        for index in range(30):
            (self.tasks / f"cwe_{100 + index}_0_task.py").write_text("pass\n")
        with self.assertRaisesRegex(ValueError, "1..30"):
            runner.python_core_cases(self.root)

    def test_local_config_rejects_unknown_options_and_links(self):
        config = self.root / "cweval.local.json"
        config.write_text('{"unexpected": "value"}')
        with self.assertRaisesRegex(ValueError, "supported options"):
            runner.local_config_args(config)
        link = self.root / "linked.json"
        link.symlink_to(config)
        with self.assertRaisesRegex(ValueError, "regular file"):
            runner.local_config_args(link)

    def test_overall_comparison_refuses_mismatched_sample_counts(self):
        with self.assertRaisesRegex(ValueError, "different sample counts"):
            runner.overall_scores({
                "control": {"case": {"functional": 1, "func_secure": 1, "samples": 1}},
                "baseline": {"case": {"functional": 1, "func_secure": 1, "samples": 2}},
            })

    def test_container_has_explicit_execution_limits(self):
        image = "co1lin/cweval@sha256:" + "a" * 64
        cmd = runner.docker_command(self.root, self.root, image, "own-container")
        self.assertIn("--network=none", cmd)
        self.assertIn("--read-only", cmd)
        self.assertIn("--cap-drop=ALL", cmd)
        self.assertIn("--memory=2g", cmd)
        self.assertIn("--cpus=2", cmd)
        self.assertIn("--pull=never", cmd)
        self.assertEqual(cmd[cmd.index("--user") + 1], "1000:1000")
        self.assertIn("-i", cmd)
        self.assertTrue(any("evals/aiscb:rw,nosuid,noexec" in value
                            for value in cmd))
        self.assertFalse(any("src=" + str(self.root) + ",dst=" in value
                             for value in cmd))
        self.assertIn("/usr/local/go/bin", " ".join(cmd))
        with self.assertRaises(ValueError):
            runner.docker_command(self.root, self.root, "co1lin/cweval:latest", "own-container")

    def test_archive_contains_only_expected_regular_generated_files(self):
        arm = self.root / "arm"
        generated = arm / "generated_0/core/py"
        generated.mkdir(parents=True)
        code = generated / "cwe_020_0_raw.py"
        code.write_text("def validate(value):\n    return True\n")
        (arm / "unrelated.txt").write_text("do not send")
        with tempfile.TemporaryFile() as stream:
            runner.evaluation_archive(stream, arm, ["cwe_020_0"], 1)
            with tarfile.open(fileobj=stream, mode="r") as archive:
                self.assertEqual(archive.getnames(),
                                 ["generated_0/core/py/cwe_020_0_raw.py"])
                self.assertEqual(archive.extractfile(archive.getmembers()[0]).read(),
                                 code.read_bytes())
        code.unlink()
        code.symlink_to(arm / "unrelated.txt")
        with tempfile.TemporaryFile() as stream:
            with self.assertRaisesRegex(ValueError, "linked generated file"):
                runner.evaluation_archive(stream, arm, ["cwe_020_0"], 1)


if __name__ == "__main__":
    unittest.main()
