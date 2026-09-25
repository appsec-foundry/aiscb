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

    def test_invalid_format_is_counted_without_creating_evaluation_input(self):
        result = self.root / "result"
        result.mkdir()
        with patch.object(runner, "assistant_reply", return_value="No code"), \
             patch.dict(runner.baseline_run.ADAPTERS["claude"],
                        {"install": lambda workdir: None}):
            runs = runner.generate({"cwe_020_0": "def validate(value):"},
                                   "claude", "model", 1, 10, result)
        self.assertTrue(all(run["status"] == "invalid_format" for run in runs))
        _, invalid = runner.checked_runs(runs, ["cwe_020_0"], 1)
        self.assertEqual(invalid, {"control": {("cwe_020_0", 0)},
                                   "baseline": {("cwe_020_0", 0)}})
        self.assertFalse((result / "baseline/generated_0").exists())

    def test_empty_response_and_cli_failure_still_stop_evaluation(self):
        result = self.root / "result"
        result.mkdir()
        with patch.dict(runner.baseline_run.ADAPTERS["claude"],
                        {"install": lambda workdir: None}):
            for reply in ("", RuntimeError("assistant exited 1")):
                with self.subTest(reply=reply), \
                     patch.object(runner, "assistant_reply",
                                  side_effect=reply if isinstance(reply, Exception)
                                  else None, return_value=reply):
                    runs = runner.generate({"cwe_020_0": "def validate(value):"},
                                           "claude", "model", 1, 10, result)
                    self.assertTrue(all(row["status"] == "incomplete"
                                        for row in runs))
                    with self.assertRaisesRegex(ValueError, "generation incomplete"):
                        runner.checked_runs(runs, ["cwe_020_0"], 1)

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

    def test_scoring_counts_invalid_format_as_zero_and_rejects_other_gaps(self):
        arm = self.root / "arm"
        arm.mkdir()
        key = "evals/aiscb/generated_X/core/py/cwe_020_0_test.py"
        (arm / "res_all.json").write_text(json.dumps({key: {
            "functional": [True, True], "secure": [True, False]}}))
        score = runner.read_scores(arm, ["cwe_020_0"], 3,
                                   {("cwe_020_0", 2)})["cwe_020_0"]
        self.assertEqual(score, {"functional": 2, "func_secure": 1, "samples": 3})
        with self.assertRaisesRegex(ValueError, "invalid evaluation data"):
            runner.read_scores(arm, ["cwe_020_0"], 3)
        (arm / "res_all.json").write_text("{}")
        score = runner.read_scores(arm, ["cwe_020_0"], 2,
                                   {("cwe_020_0", 0), ("cwe_020_0", 1)})
        self.assertEqual(score["cwe_020_0"]["func_secure"], 0)

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
        self.assertEqual(document["invalid_format_samples"], 0)
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
        self.assertIn("--num_proc 2", cmd[-1])
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

    def test_archive_omits_only_recorded_invalid_format_samples(self):
        arm = self.root / "arm"
        arm.mkdir()
        with tempfile.TemporaryFile() as stream:
            runner.evaluation_archive(stream, arm, ["cwe_020_0"], 1,
                                      {("cwe_020_0", 0)})
            with tarfile.open(fileobj=stream, mode="r") as archive:
                self.assertEqual(archive.getnames(), [])
        with tempfile.TemporaryFile() as stream:
            with self.assertRaisesRegex(ValueError, "missing or linked"):
                runner.evaluation_archive(stream, arm, ["cwe_020_0"], 1)

    def test_recovery_preserves_source_and_rejects_other_incomplete_runs(self):
        results = self.root / "results"
        source = results / "run-old"
        target = results / "run-new"
        source.mkdir(parents=True)
        target.mkdir()
        baseline_id = runner.baseline_run.baseline_identifier()
        probes = [{"arm": "control", "tool": "codex", "ok": True,
                   "found": [], "expected": None},
                  {"arm": "baseline", "tool": "codex", "ok": True,
                   "found": [baseline_id], "expected": baseline_id}]
        (source / "preflight.json").write_text(json.dumps(probes))
        rows = []
        for index in range(2):
            for arm in ("control", "baseline"):
                row = {"arm": arm, "case": "cwe_020_0", "sample": index,
                       "status": "complete"}
                if arm == "baseline" and index == 1:
                    row.update(status="incomplete", reason=(
                        "response must contain exactly one Python code block"))
                else:
                    output = (source / arm / f"generated_{index}" / "core" /
                              "py/cwe_020_0_raw.py")
                    output.parent.mkdir(parents=True)
                    output.write_text("def validate(value):\n    return True\n")
                rows.append(row)
        (source / "runs.json").write_text(json.dumps(rows))
        with patch.object(runner, "RESULTS", results):
            recovered, invalid, origin = runner.recover_run(
                source, target, ["cwe_020_0"], 2, "codex")
            self.assertEqual(origin, source)
            self.assertEqual(invalid["baseline"], {("cwe_020_0", 1)})
            self.assertEqual(recovered[-1]["status"], "invalid_format")
            self.assertEqual(json.loads((source / "runs.json").read_text())[-1]
                             ["status"], "incomplete")
            self.assertEqual(len(list(target.glob("*/generated_*/*/py/*_raw.py"))), 3)
            extra = source / "control/generated_0/core/py/cwe_999_0_raw.py"
            extra.write_text("pass\n")
            with self.assertRaisesRegex(ValueError, "unexpected generated files"):
                runner.recover_run(source, target, ["cwe_020_0"], 2, "codex")
            extra.unlink()
            rows[-1].update(status="incomplete", reason="assistant exited 1")
            (source / "runs.json").write_text(json.dumps(rows))
            with self.assertRaisesRegex(ValueError, "generation incomplete"):
                runner.recover_run(source, target, ["cwe_020_0"], 2, "codex")


IMAGE = "co1lin/cweval@sha256:" + "b" * 64
QUIET = io.StringIO


class CWEvalBoundaryTests(unittest.TestCase):
    """Refusals and fixed flows that need no assistant, network or Docker."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tasks = self.root / "benchmark/core/py"
        self.tasks.mkdir(parents=True)
        (self.tasks / "cwe_020_0_task.py").write_text(
            "def validate(value):\n# BEGIN SOLUTION\nreturn value\n")
        (self.tasks / "cwe_020_0_test.py").write_text("pass\n")

    def generated(self, arm, index=0, content="x = 1\n"):
        path = self.root / arm / f"generated_{index}/core/py/cwe_020_0_raw.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_local_config_absent_is_empty_and_malformed_config_is_refused(self):
        self.assertEqual(runner.local_config_args(self.root / "absent.json"), [])
        directory = self.root / "config-dir"
        directory.mkdir()
        large = self.root / "large.json"
        large.write_text(json.dumps({"model": "m" * 5000}))
        broken = self.root / "broken.json"
        broken.write_text("{not json")
        wrong_type = self.root / "wrong.json"
        wrong_type.write_text(json.dumps({"repeats": "3"}))
        for path, message in ((directory, "regular file"), (large, "4096 bytes"),
                              (broken, "not valid JSON"), (wrong_type, "invalid repeats")):
            with self.assertRaisesRegex(ValueError, message):
                runner.local_config_args(path)

    def test_checkout_must_be_the_pinned_clean_revision(self):
        with self.assertRaisesRegex(ValueError, "full lowercase"):
            runner.checked_checkout(self.root, "HEAD")
        with self.assertRaisesRegex(ValueError, "lacks cweval/evaluate.py"):
            runner.checked_checkout(self.root, "a" * 40)
        (self.root / "cweval").mkdir()
        (self.root / "cweval/evaluate.py").write_text("pass\n")
        git = ["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@t",
               "-c", "commit.gpgsign=false"]
        for step in (["init", "-q"], ["add", "."], ["commit", "-q", "-m", "fixture"]):
            runner.subprocess.run(git + step, check=True, capture_output=True)
        head = runner.subprocess.run(git + ["rev-parse", "HEAD"], check=True,
                                     capture_output=True, text=True).stdout.strip()
        self.assertEqual(runner.checked_checkout(self.root, head), self.root.resolve())
        with self.assertRaisesRegex(ValueError, "expected " + "c" * 40):
            runner.checked_checkout(self.root, "c" * 40)
        (self.root / "cweval/evaluate.py").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "must be clean"):
            runner.checked_checkout(self.root, head)

    def test_task_prompt_and_case_listing_refuse_unusable_tasks(self):
        task = self.tasks / "cwe_020_0_task.py"
        for content, message in (("x" * (runner.MAX_TASK_BYTES + 1), "size limit"),
                                 ("def f():\n    pass\n", "solution boundary"),
                                 ("x BEGIN PROMPT\n# BEGIN SOLUTION\n", "empty task prompt")):
            task.write_text(content)
            with self.assertRaisesRegex(ValueError, message):
                runner.task_prompt(self.root, "cwe_020_0")
        task.unlink()
        with self.assertRaisesRegex(ValueError, "1..30 valid"):
            runner.python_core_cases(self.root)

    def test_empty_code_block_is_a_format_failure(self):
        with self.assertRaisesRegex(ValueError, "empty or exceeds"):
            runner.extract_code("```python\n\n```\n")

    def test_assistant_failures_are_classified_and_codex_reads_its_reply_file(self):
        cases = (((1, "Rate limit reached", ""), runner.baseline_run.QuotaExhausted, "quota"),
                 ((-1, "", ""), RuntimeError, "timed out"),
                 ((2, "", "boom"), RuntimeError, "exited 2"))
        for result, error, message in cases:
            with patch.object(runner.baseline_run, "run_capture", return_value=result):
                with self.assertRaisesRegex(error, message):
                    runner.assistant_reply("claude", self.root, "p", "m", 5)
        with patch.object(runner.baseline_run, "run_capture", return_value=(0, "", "")) as run:
            with self.assertRaisesRegex(RuntimeError, "no final response file"):
                runner.assistant_reply("codex", self.root, "p", "m", 5)
            (self.root / "_agent_reply.txt").write_text("final answer")
            self.assertEqual(runner.assistant_reply("codex", self.root, "p", "m", 5),
                             "final answer")
        command = run.call_args.args[0]
        self.assertIn("read-only", command)
        self.assertIn("shell_tool", command)

    def test_codex_home_is_restored_when_it_was_unset(self):
        with runner.isolated_codex_home("claude"):
            pass
        with patch.dict(os.environ, {"HOME": str(self.root)}):
            os.environ.pop("CODEX_HOME", None)
            with runner.isolated_codex_home("codex"):
                inside = os.environ["CODEX_HOME"]
                self.assertEqual(list(Path(inside).iterdir()), [])
            self.assertNotIn("CODEX_HOME", os.environ)

    def test_generation_records_must_match_the_selection_exactly(self):
        good = [{"arm": arm, "case": "cwe_020_0", "sample": 0, "status": "complete"}
                for arm in ("control", "baseline")]
        bad_sets = ([good[0]],
                    [good[0], "row"],
                    [good[0], {**good[1], "extra": 1}],
                    [good[0], {**good[1], "sample": "0"}],
                    [good[0], {**good[1], "reason": "r" * 201}],
                    [good[0], dict(good[0])])
        for rows in bad_sets:
            with self.assertRaises(ValueError):
                runner.checked_runs(rows, ["cwe_020_0"], 1)
        unknown = [good[0], {**good[1], "status": "invalid_format", "reason": "other"}]
        with self.assertRaisesRegex(ValueError, "unrecognized format failure"):
            runner.checked_runs(unknown, ["cwe_020_0"], 1)

    def test_archive_refuses_empty_generated_file(self):
        self.generated("control", content="")
        with tempfile.TemporaryFile() as stream:
            with self.assertRaisesRegex(ValueError, "invalid generated file size"):
                runner.evaluation_archive(stream, self.root / "control", ["cwe_020_0"], 1)

    def test_docker_stream_runner_returns_output_and_kills_on_timeout(self):
        with tempfile.TemporaryFile() as stream:
            stream.write(b"payload")
            stream.seek(0)
            rc, out, _ = runner.run_docker_with_archive(
                [runner.sys.executable, "-c", "import sys; print(sys.stdin.read())"],
                stream, self.root, 10)
        self.assertEqual((rc, out.strip()), (0, "payload"))
        with tempfile.TemporaryFile() as stream:
            rc, _, _ = runner.run_docker_with_archive(
                [runner.sys.executable, "-c", "import time; time.sleep(30)"],
                stream, self.root, 0.3)
        self.assertEqual(rc, -1)

    def test_evaluation_needs_docker_skips_all_invalid_arms_and_checks_results(self):
        with patch.object(runner.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Docker is required"):
                runner.evaluate(self.root, self.root, IMAGE, 5, ["cwe_020_0"], 1)
        self.generated("baseline")
        invalid = {"control": {("cwe_020_0", 0)}, "baseline": set()}
        score = '{"cwe_020_0_test.py": {"functional": [true], "secure": [true]}}'
        with patch.object(runner.shutil, "which", return_value="/usr/bin/docker"), \
             patch.object(runner.subprocess, "run") as cleanup, \
             patch.object(runner, "run_docker_with_archive", return_value=(0, score, "")):
            runner.evaluate(self.root, self.root, IMAGE, 5, ["cwe_020_0"], 1, invalid)
        self.assertEqual((self.root / "control/res_all.json").read_text(), "{}\n")
        self.assertEqual((self.root / "baseline/res_all.json").read_text(), score)
        self.assertEqual(cleanup.call_args.args[0][:3], ["docker", "rm", "-f"])
        for result, error, message in (((-1, "", ""), RuntimeError, "timed out"),
                                       ((1, "", "trace"), RuntimeError, "exited 1: trace"),
                                       ((0, "x" * (runner.MAX_SCORE_BYTES + 1), ""),
                                        ValueError, "exceeds size limit")):
            with patch.object(runner.shutil, "which", return_value="/usr/bin/docker"), \
                 patch.object(runner.subprocess, "run") as cleanup, \
                 patch.object(runner, "run_docker_with_archive", return_value=result):
                with self.assertRaisesRegex(error, message):
                    runner.evaluate(self.root, self.root, IMAGE, 5, ["cwe_020_0"], 1, invalid)
            cleanup.assert_called_once()

    def test_scores_refuse_malformed_results_and_empty_comparisons(self):
        arm = self.root / "arm"
        arm.mkdir()
        for content in ('[]', '{"a": 1}', '{"other_test.py": {}}'):
            (arm / "res_all.json").write_text(content)
            with self.assertRaises(ValueError):
                runner.read_scores(arm, ["cwe_020_0"], 1)
        empty = {"control": {}, "baseline": {}}
        with self.assertRaisesRegex(ValueError, "no samples"):
            runner.overall_scores(empty)

    def recovery_source(self, results):
        source = results / "run-old"
        source.mkdir(parents=True)
        baseline_id = runner.baseline_run.baseline_identifier()
        probes = [{"arm": "control", "tool": "codex", "ok": True, "found": [],
                   "expected": None},
                  {"arm": "baseline", "tool": "codex", "ok": True,
                   "found": [baseline_id], "expected": baseline_id}]
        rows = [{"arm": "control", "case": "cwe_020_0", "sample": 0, "status": "complete"},
                {"arm": "baseline", "case": "cwe_020_0", "sample": 0,
                 "status": "invalid_format",
                 "reason": "response must contain exactly one Python code block"}]
        (source / "preflight.json").write_text(json.dumps(probes))
        (source / "runs.json").write_text(json.dumps(rows))
        output = source / "control/generated_0/core/py/cwe_020_0_raw.py"
        output.parent.mkdir(parents=True)
        output.write_text("x = 1\n")
        return source, probes, rows, output

    def test_recovery_refuses_unproven_or_inconsistent_sources(self):
        results = self.root / "results"
        source, probes, rows, output = self.recovery_source(results)
        target = self.root / "target"
        target.mkdir()

        def refused(message, tool="codex", path=source):
            with patch.object(runner, "RESULTS", results):
                with self.assertRaisesRegex(ValueError, message):
                    runner.recover_run(path, target, ["cwe_020_0"], 1, tool)

        link = results / "run-link"
        link.symlink_to(source)
        refused("must not be linked", path=link)
        other = self.root / "run-elsewhere"
        other.mkdir()
        refused("one CWEval result directory", path=other)
        refused("does not match the selected tool", tool="claude")
        (source / "preflight.json").write_text(json.dumps(probes[:1]))
        refused("invalid recovery preflight")
        swapped = [dict(probes[0], found=["aiscb-0.0.1"]), probes[1]]
        (source / "preflight.json").write_text(json.dumps(swapped))
        refused("arm separation")
        (source / "preflight.json").write_text("x" * (runner.MAX_RUN_METADATA_BYTES + 1))
        refused("exceeds size limit")
        (source / "preflight.json").unlink()
        refused("missing or linked recovery metadata")
        (source / "preflight.json").write_text(json.dumps(probes))
        complete = [rows[0], {**rows[1], "status": "complete"}]
        (source / "runs.json").write_text(json.dumps(complete))
        refused("no invalid-format samples")
        (source / "runs.json").write_text(json.dumps(rows))
        stray = source / "baseline/generated_0/core/py/cwe_020_0_raw.py"
        stray.parent.mkdir(parents=True)
        stray.write_text("x = 2\n")
        refused("unexpected recovery output")
        stray.unlink()
        output.write_text("")
        refused("invalid recovery output size")
        output.unlink()
        refused("missing or linked recovery output")

    def test_report_names_recovery_source_and_its_unverifiable_fields(self):
        scores = {arm: {"cwe_020_0": {"functional": 1, "func_secure": 1, "samples": 1}}
                  for arm in ("control", "baseline")}
        runs = [{"status": "invalid_format"}]
        runner.write_report(self.root, scores, runs, "codex", "m", "a" * 40, IMAGE,
                            "selected-cases", self.root / "run-old")
        report = (self.root / "report.md").read_text()
        self.assertIn("Recovered from:", report)
        self.assertIn("cannot be verified", report)
        document = json.loads((self.root / "report.json").read_text())
        self.assertEqual(document["invalid_format_samples"], 1)

    def run_main(self, argv, config=None):
        stdout, stderr = QUIET(), QUIET()
        side = config if isinstance(config, Exception) else None
        with patch.object(runner, "local_config_args", return_value=[] if side is None else None,
                          side_effect=side), \
             patch.object(runner, "checked_checkout", return_value=self.root), \
             redirect_stdout(stdout), patch.object(runner.sys, "stderr", stderr):
            try:
                code = runner.main(argv)
            except SystemExit as exit:
                code = exit.code
        return code, stdout.getvalue(), stderr.getvalue()

    def base_args(self, **overrides):
        values = {"--cweval-root": str(self.root), "--revision": "a" * 40,
                  "--image": IMAGE, "--model": "model", "--cases": "cwe_020_0",
                  "--repeats": "1", **overrides}
        return [part for key, value in values.items() for part in (key, value)]

    def test_main_refuses_invalid_arguments_before_any_run(self):
        self.assertEqual(self.run_main(self.base_args(), ValueError("bad config"))[0], 2)
        refusals = (self.base_args() + ["--dry-run", "--recover-run", "x"],
                    self.base_args(**{"--repeats": "0"}),
                    self.base_args(**{"--model": "bad model"}),
                    self.base_args(**{"--image": "cweval:latest"}),
                    self.base_args(**{"--cases": "cwe_020_0,cwe_020_0"}))
        for argv in refusals:
            code, _, error = self.run_main(argv)
            self.assertEqual(code, 2, argv)
            self.assertTrue(error, argv)
        with patch.object(runner.shutil, "which", return_value=None):
            code, _, error = self.run_main(self.base_args())
        self.assertEqual(code, 2)
        self.assertIn("claude is not on PATH", error)
        with patch.object(runner.shutil, "which", side_effect=lambda n: None if n == "docker" else n):
            code, _, error = self.run_main(self.base_args())
        self.assertIn("Docker is required", error)
        results = self.root / "results-link"
        results.symlink_to(self.root)
        with patch.object(runner.shutil, "which", return_value="/usr/bin/x"), \
             patch.object(runner, "RESULTS", results):
            code, _, error = self.run_main(self.base_args())
        self.assertIn("must not be linked", error)

    def test_main_runs_preflight_generation_scoring_and_report(self):
        results = self.root / "results"
        probes = [{"tool": "claude", "arm": "control", "ok": True},
                  {"tool": "claude", "arm": "baseline", "ok": True}]
        runs = [{"arm": arm, "case": "cwe_020_0", "sample": 0, "status": "complete"}
                for arm in ("control", "baseline")]
        scores = {"cwe_020_0": {"functional": 1, "func_secure": 1, "samples": 1}}
        with patch.object(runner.shutil, "which", return_value="/usr/bin/x"), \
             patch.object(runner, "RESULTS", results), \
             patch.object(runner, "preflight", return_value=probes), \
             patch.object(runner, "generate", return_value=runs) as generate, \
             patch.object(runner, "evaluate") as evaluate, \
             patch.object(runner, "read_scores", return_value=scores):
            code, out, _ = self.run_main(self.base_args())
        self.assertEqual(code, 0)
        self.assertIn("control 100.0%, baseline 100.0%", out)
        self.assertEqual(generate.call_args.args[0], {"cwe_020_0": "def validate(value):"})
        evaluate.assert_called_once()
        run_dir = next(results.glob("run-*"))
        self.assertTrue((run_dir / "report.md").is_file())
        self.assertEqual(json.loads((run_dir / "runs.json").read_text()), runs)
        failed = [dict(probes[0], ok=False, found=["aiscb-0.1.0"]), probes[1]]
        with patch.object(runner.shutil, "which", return_value="/usr/bin/x"), \
             patch.object(runner, "RESULTS", results), \
             patch.object(runner, "preflight", return_value=failed), \
             patch.object(runner, "generate") as generate:
            code, _, error = self.run_main(self.base_args())
        self.assertEqual(code, 1)
        self.assertIn("Incomplete CWEval run", error)
        generate.assert_not_called()

    def test_main_recovers_a_previous_run_without_calling_the_assistant(self):
        results = self.root / "results"
        source, _, _, _ = self.recovery_source(results)
        scores = {"cwe_020_0": {"functional": 0, "func_secure": 0, "samples": 1}}
        with patch.object(runner.shutil, "which",
                          side_effect=lambda n: "/usr/bin/docker" if n == "docker" else None), \
             patch.object(runner, "RESULTS", results), \
             patch.object(runner, "preflight") as preflight, \
             patch.object(runner, "evaluate") as evaluate, \
             patch.object(runner, "read_scores", return_value=scores):
            code, out, _ = self.run_main(self.base_args(**{"--tool": "codex"})
                                         + ["--recover-run", str(source)])
        self.assertEqual(code, 0, out)
        preflight.assert_not_called()
        self.assertEqual(evaluate.call_args.args[-1]["baseline"], {("cwe_020_0", 0)})
        self.assertIn("Invalid-format answers counted as failed samples: 1", out)


if __name__ == "__main__":
    unittest.main()
