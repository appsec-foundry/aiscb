#!/usr/bin/env python3
"""Check that install.py links where it should and leaves everything else alone.

An installer that quietly overwrites a project's own AGENTS.md destroys work
that is not its own, and one that is not idempotent cannot be run twice. Both
are checked here against a throwaway directory.
"""

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402

failures = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global failures
    print(f"{'ok  ' if condition else 'FAIL'} {name}")
    if not condition:
        failures += 1
        if detail:
            print(f"     {detail}")


def run(root: Path, *tools: str) -> list[str]:
    return install.install(list(tools) or list(install.TOOLS), root, None)


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    report = run(root)

    baseline = root / install.BASELINE
    check("the project gets the real baseline", baseline.is_file())
    check("Claude reads it from .claude/rules",
          (root / ".claude" / "rules" / install.BASELINE).is_symlink())
    check("the AGENTS.md tools read it from the root",
          (root / "AGENTS.md").is_symlink())
    check("Copilot reads it from .github",
          (root / ".github" / "copilot-instructions.md").is_symlink())
    check("links resolve to the project's own file",
          (root / "AGENTS.md").resolve() == baseline.resolve())
    check("links stay relative, so a clone keeps working",
          not Path((root / "AGENTS.md").readlink()).is_absolute(),
          str((root / "AGENTS.md").readlink()))
    check("every step is reported", len(report) >= 4, str(report))

    again = run(root)
    check("a second run changes nothing",
          all(line.startswith("in place") for line in again), str(again))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    own = root / "AGENTS.md"
    own.write_text("# our own instructions\n")
    report = run(root, "codex")

    check("an existing AGENTS.md survives untouched",
          own.read_text() == "# our own instructions\n")
    check("and the manual step is named",
          any("append" in line for line in report), str(report))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    stale = root / "AGENTS.md"
    stale.symlink_to("somewhere-else.md")
    report = run(root, "codex")
    check("a foreign symlink is refused, not replaced",
          stale.readlink() == Path("somewhere-else.md")
          and any("points elsewhere" in line for line in report), str(report))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    occupied = root / install.BASELINE
    occupied.write_text("not a baseline\n")
    report = run(root, "codex")
    check("an unrelated baseline filename survives untouched",
          occupied.read_text() == "not a baseline\n")
    check("invalid baseline content blocks tool links",
          not (root / "AGENTS.md").exists()
          and any("not a valid baseline" in line for line in report), str(report))

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    report = install.install(list(install.TOOLS), home, home)
    source = install.user_source(home)
    check("user installs keep a managed baseline outside the checkout",
          source.is_file() and source.resolve() != install.SOURCE.resolve())
    check("Claude's user link reads the managed baseline",
          (home / ".claude" / install.BASELINE).resolve() == source.resolve())
    check("Claude imports the managed baseline",
          f"@{source}" in (home / ".claude" / "CLAUDE.md").read_text().splitlines())
    check("Codex's user instructions read the managed baseline",
          (home / ".codex" / "AGENTS.md").resolve() == source.resolve(), str(report))
    check("Copilot's user instructions read the managed baseline",
          (home / ".copilot" / "copilot-instructions.md").resolve()
          == source.resolve(), str(report))

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    manual = home / ".codex" / "AGENTS.md"
    manual.parent.mkdir()
    manual.write_bytes(install.bundled_baseline().content)
    found = install.scan_user(home)
    check("known user locations reveal manually copied baselines",
          len(found) == 1
          and found[0].kind == "unmanaged"
          and found[0].tools == ("codex",))

with tempfile.TemporaryDirectory() as tmp:
    state = Path(tmp) / "installations.json"
    state.write_text("not json\n")
    _registry, writable, note = install.load_registry(state)
    check("an invalid installation registry is never overwritten",
          not writable and note is not None and state.read_text() == "not json\n")

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    project = sandbox / "project"
    home.mkdir()
    project.mkdir()
    install.install(["codex"], project, None)
    previous = install.empty_registry()
    install.record_installation(
        previous, install.scan_project(project, {}), trusted=True
    )
    old_state = install.previous_registry_path(home)
    install.save_registry(old_state, previous)
    current_state = install.registry_path(home)
    imported, writable, note = install.load_registry_with_previous(
        home, current_state
    )
    projects = imported.get("projects")
    archived_states = list(old_state.parent.glob("installations.json.migrated*"))
    check("the previous registry path is imported and archived",
          writable
          and isinstance(projects, dict)
          and str(project.resolve()) in projects
          and current_state.is_file()
          and not old_state.exists()
          and len(archived_states) == 1
          and note is not None
          and "Imported installation records" in note,
          str(note))

check("stable SemVer sorts after its prerelease",
      install.SemVer.parse("1.0.0-rc.1") < install.SemVer.parse("1.0.0"))
check("numeric SemVer prereleases sort numerically",
      install.SemVer.parse("1.0.0-2") < install.SemVer.parse("1.0.0-10"))
try:
    install.SemVer.parse("1.0.0-01")
except ValueError:
    invalid_semver_rejected = True
else:
    invalid_semver_rejected = False
check("invalid SemVer numeric prereleases are rejected", invalid_semver_rejected)

original_origin = install.LOCAL_ORIGIN
try:
    install.LOCAL_ORIGIN = "installed copy"
    installed_copy_checks_online = install._interactive_check_online(False)
finally:
    install.LOCAL_ORIGIN = original_origin
check("an installed copy cannot replace its verified bundle from the network",
      not installed_copy_checks_online
      and not install._interactive_check_online(True)
      and install._interactive_check_online(False))

tool_prompts: list[str] = []
tool_output: list[str] = []
chosen_tools = install.choose_tools(
    lambda prompt: tool_prompts.append(prompt) or "1,2",
    tool_output.append,
    ("claude", "codex"),
)
check("guided tool selection clearly supports multiple tools",
      chosen_tools == ["claude", "codex"]
      and any("one or more" in line for line in tool_output)
      and any("comma-separated" in prompt and "Enter = all" in prompt
              for prompt in tool_prompts),
      f"prompts={tool_prompts!r}, output={tool_output!r}")
all_tools = install.choose_tools(lambda _prompt: "", lambda _line: None, install.TOOLS)
check("guided setup defaults to all three tools", all_tools == list(install.TOOLS))
existing_tool_prompts: list[str] = []
existing_tool_output: list[str] = []
existing_tools = install.choose_tools(
    lambda prompt: existing_tool_prompts.append(prompt) or "",
    existing_tool_output.append,
    install.TOOLS,
    ["codex"],
)
check("existing scopes default to their installed tools",
      existing_tools == ["codex"]
      and "  2. Codex (installed)" in existing_tool_output
      and not any("Claude Code (installed)" in line
                  or "GitHub Copilot (installed)" in line
                  for line in existing_tool_output)
      and any("Enter = keep installed (Codex)" in prompt
              for prompt in existing_tool_prompts),
      f"prompts={existing_tool_prompts!r}, output={existing_tool_output!r}")
hook_output: list[str] = []
hook_prompts: list[str] = []
hook_tools = install.choose_hook_tools(
    lambda prompt: hook_prompts.append(prompt) or "1,3",
    hook_output.append,
    list(install.TOOLS),
)
check("startup hooks can target a subset of the installed tools",
      hook_tools == ["claude", "copilot"]
      and any("Enter = all shown" in prompt for prompt in hook_prompts),
      f"prompts={hook_prompts!r}, output={hook_output!r}")
default_hook_tools = install.choose_hook_tools(
    lambda _prompt: "", lambda _line: None, list(install.TOOLS)
)
check("startup hooks default to all selected tools",
      default_hook_tools == list(install.TOOLS))
no_hook_tools = install.choose_hook_tools(
    lambda _prompt: "none", lambda _line: None, list(install.TOOLS)
)
check("startup hooks can be skipped explicitly", no_hook_tools == [])

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    install.install(list(install.TOOLS), root, None)
    claude_settings = root / ".claude" / "settings.json"
    claude_settings.write_text(
        '{"permissions":{"ask":["Edit(/specs/**)"]}}\n', encoding="utf-8"
    )
    hook_report = install.install_version_hooks(list(install.TOOLS), root, None)
    helper = install.version_hook_path(root, None)
    claude_config = json.loads(claude_settings.read_text(encoding="utf-8"))
    codex_config = json.loads(
        (root / ".codex" / "hooks.json").read_text(encoding="utf-8")
    )
    copilot_config = json.loads(
        (root / ".github" / "hooks" / install.COPILOT_VERSION_HOOK_NAME).read_text(
            encoding="utf-8"
        )
    )
    check("version hooks are installed for all three project tools",
          helper.is_file()
          and "SessionStart" in claude_config["hooks"]
          and "SessionStart" in codex_config["hooks"]
          and "sessionStart" in copilot_config["hooks"], str(hook_report))
    check("the Claude hook merge preserves existing settings",
          claude_config.get("permissions")
          == {"ask": ["Edit(/specs/**)"]}, str(claude_config))
    json_banner = subprocess.run(
        [sys.executable, str(helper), "--output", "json"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    plain_banner = subprocess.run(
        [sys.executable, str(helper), "--output", "message"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    check("the shared hook helper reports the installed baseline ID",
          json_banner.returncode == 0
          and "Baseline active:" in json.loads(json_banner.stdout)["systemMessage"]
          and json.loads(json_banner.stdout)["systemMessage"].endswith(
              install.bundled_baseline().baseline_id
          )
          and plain_banner.stdout.strip().endswith(
              install.bundled_baseline().baseline_id
          ), json_banner.stderr or plain_banner.stderr)
    again = install.install_version_hooks(list(install.TOOLS), root, None)
    check("installing the version hooks twice is idempotent",
          all(line.startswith("in place") for line in again), str(again))

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    install.install(list(install.TOOLS), home, home)
    elsewhere = home / "previous-location" / install.VERSION_HOOK_NAME
    elsewhere.parent.mkdir(parents=True)
    elsewhere.write_bytes(install.VERSION_HOOK_SOURCE.read_bytes())
    for path, maker in (
        (home / ".claude" / "settings.json", install._claude_version_hook),
        (home / ".codex" / "hooks.json", install._codex_version_hook),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(
            {"hooks": {"SessionStart": [maker(elsewhere, False)]}}), encoding="utf-8")
    copilot = (
        home
        / ".copilot"
        / "hooks"
        / install.PREVIOUS_COPILOT_VERSION_HOOK_NAME
    )
    copilot.parent.mkdir(parents=True, exist_ok=True)
    copilot.write_text(json.dumps(
        install._copilot_version_config(elsewhere, False)), encoding="utf-8")
    report = install.install_version_hooks(list(install.TOOLS), home, home)
    entries = json.loads(
        (home / ".claude" / "settings.json").read_text(encoding="utf-8")
    )["hooks"]["SessionStart"]
    check("a hook left behind by an earlier helper location is repointed",
          all(install._version_hook_is_installed(tool, home, home)
              for tool in install.TOOLS)
          and len(entries) == 1
          and not copilot.exists()
          and any("migrated to" in line for line in report), str(report))

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    install.install(["copilot"], home, home)
    previous = (
        home
        / ".copilot"
        / "hooks"
        / install.PREVIOUS_COPILOT_VERSION_HOOK_NAME
    )
    previous.parent.mkdir(parents=True, exist_ok=True)
    foreign = {"version": 1, "hooks": {"sessionStart": []}}
    previous.write_text(json.dumps(foreign), encoding="utf-8")
    report = install.install_version_hooks(["copilot"], home, home)
    current = previous.with_name(install.COPILOT_VERSION_HOOK_NAME)
    check("a foreign hook under the previous Copilot name is not migrated",
          json.loads(previous.read_text(encoding="utf-8")) == foreign
          and not current.exists()
          and any("blocked" in line and str(previous) in line for line in report),
          str(report))

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    install.install(["claude"], home, home)
    hand_written = install._claude_version_hook(
        install.version_hook_path(home, home), False
    )
    hand_written["hooks"][0]["args"][-1] = "message"
    settings = home / ".claude" / "settings.json"
    settings.write_text(json.dumps(
        {"hooks": {"SessionStart": [hand_written]}}), encoding="utf-8")
    report = install.install_version_hooks(["claude"], home, home)
    check("a version hook of another shape is refused and says what to do",
          any("blocked" in line and "remove it to let setup write" in line
              for line in report)
          and json.loads(settings.read_text(encoding="utf-8"))["hooks"]["SessionStart"]
              == [hand_written], str(report))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    install.install(["claude"], root, None)
    settings = root / ".claude" / "settings.json"
    invalid = b'{"hooks": {"SessionStart": []}, "hooks": {}}\n'
    settings.write_bytes(invalid)
    report = install.install_version_hooks(["claude"], root, None)
    check("ambiguous existing hook settings are not overwritten",
          settings.read_bytes() == invalid
          and any(line.startswith("blocked") for line in report), str(report))

bundled = install.bundled_baseline()
check("the checkout installer uses the canonical upstream",
      install.GITHUB_REPOSITORY == "appsec-foundry/aiscb")
new_content = bundled.content.replace(
    bundled.baseline_id.encode(), b"aiscb-9.8.7", 1
)

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    project = sandbox / "project"
    home.mkdir()
    project.mkdir()
    old_content = bundled.content.replace(
        bundled.baseline_id.encode(), b"aiscb-0.0.1", 1
    )
    install.install(["codex"], project, None, content=bundled.content)
    install.install(["codex"], home, home, content=old_content)
    state = sandbox / "installations.json"
    status_output: list[str] = []
    status_result = install.installation_status(
        home=home,
        output=status_output.append,
        check_online=False,
        state_path=state,
        current_root=project,
    )
    check("status check marks current and outdated installations",
          status_result == 0
          and any(line.startswith("  ✓") and " project " in line
                  for line in status_output)
          and any(line.startswith("  ↻") and " user " in line
                  for line in status_output),
          str(status_output))
    check("status check is read-only", not state.exists(), str(state))


def fake_release(url: str) -> object:
    if url == install.LATEST_RELEASE_URL:
        return {"tag_name": "v9.8.7", "draft": False, "prerelease": False}
    return {
        "type": "file",
        "encoding": "base64",
        "content": base64.b64encode(new_content).decode(),
    }


release = install.fetch_release_baseline(fake_release)
check("a tagged release baseline is parsed and version-matched",
      str(release.version) == "9.8.7")


def mismatched_release(url: str) -> object:
    if url == install.LATEST_RELEASE_URL:
        return {"tag_name": "v9.8.6", "draft": False, "prerelease": False}
    return fake_release(url)


try:
    install.fetch_release_baseline(mismatched_release)
except ValueError:
    mismatch_rejected = True
else:
    mismatch_rejected = False
check("a release tag cannot supply a different baseline version", mismatch_rejected)

try:
    install._GitHubRedirectHandler().redirect_request(
        None, None, 302, "redirect", {}, "https://example.com/baseline"
    )
except urllib.error.HTTPError:
    redirect_rejected = True
else:
    redirect_rejected = False
check("the updater rejects cross-host redirects", redirect_rejected)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    old_content = bundled.content.replace(
        bundled.baseline_id.encode(), b"aiscb-0.0.1", 1
    )
    install.install(["codex"], root, None, content=old_content)
    first = install.scan_project(root, {})
    tracked = install.Installation(
        first.kind, first.root, first.source, first.baseline, first.tools,
        first.baseline.digest,
    )
    report, updated = install.update_installation(
        tracked, bundled, lambda _question, _default: False
    )
    check("a tracked baseline updates without a second overwrite prompt",
          updated is not None and updated.baseline.digest == bundled.digest, str(report))
    check("a tracked update does not create a backup",
          not (root / f"{install.BASELINE}.bak").exists())

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    old_content = bundled.content.replace(
        bundled.baseline_id.encode(), b"aiscb-0.0.1", 1
    )
    install.install(["codex"], root, None, content=old_content)
    first = install.scan_project(root, {})
    changed_content = old_content + b"\nlocal note\n"
    (root / install.BASELINE).write_bytes(changed_content)
    changed = install.scan_project(root, {"sha256": first.baseline.digest})
    report, updated = install.update_installation(
        changed, bundled, lambda _question, _default: False
    )
    check("a locally changed baseline is not replaced by default",
          updated is None and (root / install.BASELINE).read_bytes() == changed_content,
          str(report))
    report, updated = install.update_installation(
        changed, bundled, lambda _question, _default: True
    )
    check("an explicitly approved local replacement keeps a backup",
          updated is not None
          and (root / f"{install.BASELINE}.bak").read_bytes() == changed_content,
          str(report))

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    old_checkout = home / "old-checkout"
    old_checkout.mkdir()
    old_source = old_checkout / install.BASELINE
    old_source.write_bytes(bundled.content)
    target = home / ".codex" / "AGENTS.md"
    target.parent.mkdir()
    target.symlink_to(old_source)
    legacy = install.scan_user(home)
    report, migrated = install.migrate_legacy_user(legacy[0], bundled)
    check("checkout-linked user installs migrate to managed storage",
          migrated is not None
          and target.resolve() == install.user_source(home).resolve(), str(report))
    check("migration does not modify the old checkout",
          old_source.read_bytes() == bundled.content)

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    old_checkout = home / "old-checkout"
    old_checkout.mkdir()
    old_source = old_checkout / install.BASELINE
    old_source.write_bytes(bundled.content)
    claude_link = home / ".claude" / install.BASELINE
    claude_link.parent.mkdir()
    claude_link.symlink_to(old_source)
    claude_instructions = home / ".claude" / "CLAUDE.md"
    claude_instructions.write_text(f"@{claude_link}\n", encoding="utf-8")
    matches = [
        item for item in install.scan_user(home) if item.kind == "legacy-user"
    ]
    report, migrated = install.migrate_legacy_user(matches[0], bundled)
    install_report = install.install(["claude"], home, home)
    hook_report = install.install_version_hooks(["claude"], home, home)
    managed = [item for item in install.scan_user(home) if item.kind == "user"]
    check("Claude legacy links migrate to managed user storage",
          migrated is not None
          and migrated.tools == ("claude",)
          and claude_link.resolve() == install.user_source(home).resolve()
          and claude_instructions.read_text(encoding="utf-8")
              == f"@{claude_link}\n"
          and managed and managed[0].tools == ("claude",),
          f"migration={report!r}, install={install_report!r}, hook={hook_report!r}")
    check("Claude's stable import link is accepted after migration",
          not any(line.startswith("blocked") for line in install_report),
          str(install_report))
    check("Claude's startup hook works after legacy migration",
          install._version_hook_is_installed("claude", home, home),
          str(hook_report))

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    project = sandbox / "project"
    home.mkdir()
    project.mkdir()
    state = home / "state.json"
    answers = iter(["1", "", "", "y"])
    output: list[str] = []
    result = install.interactive_setup(
        home=home,
        input_fn=lambda _prompt: next(answers),
        output=output.append,
        check_online=False,
        state_path=state,
        current_root=project,
    )
    check("guided setup can install all supported user tools",
          result == 0
          and install.user_source(home).is_file()
          and (home / ".codex" / "AGENTS.md").is_symlink()
          and (home / ".copilot" / "copilot-instructions.md").is_symlink(),
          str(output))
    check("guided setup can add user-wide startup hooks for all three tools",
          (home / ".claude" / "settings.json").is_file()
          and (home / ".codex" / "hooks.json").is_file()
          and (home / ".copilot" / "hooks"
               / install.COPILOT_VERSION_HOOK_NAME).is_file(), str(output))
    check("guided setup records the answer about background release checks",
          json.loads(state.read_text())["update_check"]["enabled"] is True,
          state.read_text())
    check("guided setup explains its purpose and progress",
          output[:4] == [
              "AI Secure Coding Baseline setup",
              "Install or update the baseline for Claude Code, Codex, and Copilot.",
              "Existing instruction files are preserved; conflicts are reported.",
              "\nChecking the available baseline...",
          ]
          and "\nInstallations" in output
          and "\nApplying user-wide setup:" in output
          and "\nVerifying baseline setup:" in output
          and "\nVerifying startup hooks:" in output
          and output[-1] == "\nSetup complete.", str(output))
    state_mode = os.stat(state).st_mode & 0o777 if state.exists() else None
    check("guided setup records known installation locations",
          state.is_file() and state_mode == 0o600, str(state_mode))

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    plain = sandbox / "plain-directory"
    home.mkdir()
    plain.mkdir()
    previous_cwd = Path.cwd()
    output = []
    try:
        os.chdir(plain)
        result = install.interactive_setup(
            home=home,
            input_fn=lambda _prompt: "2",
            output=output.append,
            check_online=False,
            state_path=sandbox / "state.json",
        )
    finally:
        os.chdir(previous_cwd)
    check("project setup is hidden outside a detected project",
          result == 0
          and "Project    none detected" in output
          and "  1. install for user" in output
          and "  2. exit" in output
          and not any("in project" in line for line in output),
          str(output))

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    plain = sandbox / "plain-directory"
    previous_data = install.previous_user_data_root(home)
    home.mkdir()
    plain.mkdir()
    previous_data.mkdir(parents=True)
    previous_source = previous_data / install.BASELINE
    previous_source.write_bytes(
        bundled.content.replace(
            bundled.baseline_id.encode(), b"aisec-0.1.9", 1
        )
    )
    previous_helper = previous_data / install.VERSION_HOOK_NAME
    previous_helper.write_bytes(install.VERSION_HOOK_SOURCE.read_bytes())

    claude_link = home / ".claude" / install.BASELINE
    claude_link.parent.mkdir()
    claude_link.symlink_to(previous_source)
    (home / ".claude" / "CLAUDE.md").write_text(
        f"@{claude_link}\n", encoding="utf-8"
    )
    codex_link = home / ".codex" / "AGENTS.md"
    codex_link.parent.mkdir()
    codex_link.symlink_to(previous_source)
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": {"SessionStart": [
            install._claude_version_hook(previous_helper, False)
        ]}}),
        encoding="utf-8",
    )
    (home / ".codex" / "hooks.json").write_text(
        json.dumps({"hooks": {"SessionStart": [
            install._codex_version_hook(previous_helper, False)
        ]}}),
        encoding="utf-8",
    )

    prompts = []
    output = []

    def accept_aiscb_migration(prompt: str) -> str:
        prompts.append(prompt)
        return ""

    previous_cwd = Path.cwd()
    try:
        os.chdir(plain)
        result = install.interactive_setup(
            home=home,
            input_fn=accept_aiscb_migration,
            output=output.append,
            check_online=False,
            state_path=sandbox / "state.json",
        )
    finally:
        os.chdir(previous_cwd)

    managed_source = install.user_source(home)
    check("the guided default migrates the released aisec user install to aiscb",
          result == 0
          and any(prompt == "Choice [1]: " for prompt in prompts)
          and any("migration" in line and bundled.baseline_id in line
                  for line in output)
          and any("previous managed location" in line for line in output)
          and install.read_baseline(managed_source).baseline_id
              == bundled.baseline_id
          and claude_link.resolve() == managed_source.resolve()
          and codex_link.resolve() == managed_source.resolve()
          and install._version_hook_is_installed("claude", home, home)
          and install._version_hook_is_installed("codex", home, home),
          f"output={output!r}, prompts={prompts!r}")

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    project = sandbox / "project"
    foreign = sandbox / "foreign"
    home.mkdir()
    project.mkdir()
    foreign.mkdir()
    install.install(["codex"], home, home)
    foreign_source = foreign / install.BASELINE
    foreign_source.write_bytes(bundled.content)
    claude_link = home / ".claude" / install.BASELINE
    claude_link.parent.mkdir()
    claude_link.symlink_to(foreign_source)
    (home / ".claude" / "CLAUDE.md").write_text(
        "Existing Claude instructions.\n", encoding="utf-8"
    )
    answers = iter(["1", "1"])
    output = []
    result = install.interactive_setup(
        home=home,
        input_fn=lambda _prompt: next(answers),
        output=output.append,
        check_online=False,
        state_path=sandbox / "state.json",
        current_root=project,
    )
    check("guided setup reports incomplete tool installation as an error",
          result == 2
          and "  ! Claude Code incomplete" in output
          and output[-1] == "\nSetup finished with unresolved items."
          and not (home / ".claude" / "settings.json").exists(),
          str(output))

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    project = sandbox / "project"
    home.mkdir()
    project.mkdir()
    install.install(list(install.TOOLS), home, home)
    older = bundled.content.replace(bundled.baseline_id.encode(), b"aiscb-0.1.1", 1)
    install.install(["codex"], project, None, content=older)
    prompts = []
    output = []
    install.interactive_setup(
        home=home,
        input_fn=lambda prompt: prompts.append(prompt) or "n",
        output=output.append,
        check_online=False,
        state_path=sandbox / "state.json",
        current_root=project,
    )
    legend = [line for line in output if line.startswith("  ✓ up to date")]
    check("a mixed table explains only the symbols it uses",
          legend == ["  ✓ up to date  ↻ update available"], str(output[:12]))

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    project = sandbox / "project"
    home.mkdir()
    project.mkdir()
    install.install(list(install.TOOLS), home, home)
    registry = install.empty_registry()
    for item in install.scan_user(home, {}):
        if item.kind == "user":
            install.record_installation(registry, item, trusted=True)
    state = sandbox / "state.json"
    install.save_registry(state, registry)
    prompts = []
    install.interactive_setup(
        home=home,
        input_fn=lambda prompt: prompts.append(prompt) or "",
        output=lambda _line: None,
        check_online=False,
        state_path=state,
        current_root=project,
    )
    check("a complete user scope defaults to leaving, not to writing a project",
          prompts == ["Choice [4]: "], str(prompts))

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    project = sandbox / "project"
    home.mkdir()
    project.mkdir()
    install.install(list(install.TOOLS), home, home)
    install.install(list(install.TOOLS), project, None)
    registry = install.empty_registry()
    for item in install.scan_user(home, {}):
        if item.kind == "user":
            install.record_installation(registry, item, trusted=True)
    install.record_installation(
        registry, install.scan_project(project, {}), trusted=True
    )
    state = sandbox / "state.json"
    install.save_registry(state, registry)
    prompts = []
    output = []
    result = install.interactive_setup(
        home=home,
        input_fn=lambda prompt: prompts.append(prompt) or "",
        output=output.append,
        check_online=False,
        state_path=state,
        current_root=project,
    )
    check("a table of one condition needs no legend",
          not any("up to date" in line and "not installed" in line
                  for line in output), str(output[:12]))
    check("a setup with nothing left to do defaults to leaving",
          result == 0
          and prompts == ["Choice [4]: "]
          and output[-1] == "No changes made.",
          f"prompts={prompts!r}, last={output[-1]!r}")

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    project = sandbox / "project"
    home.mkdir()
    project.mkdir()
    old_content = bundled.content.replace(
        bundled.baseline_id.encode(), b"aiscb-0.0.1", 1
    )
    install.install(["codex"], home, home, content=old_content)
    previous = [item for item in install.scan_user(home, {}) if item.kind == "user"][0]
    registry = install.empty_registry()
    install.record_installation(registry, previous, trusted=True)
    state = sandbox / "state.json"
    install.save_registry(state, registry)
    prompts: list[str] = []
    result = install.interactive_setup(
        home=home,
        input_fn=lambda prompt: prompts.append(prompt) or (
            "1" if prompt.startswith("Choice") else ""
        ),
        output=lambda _line: None,
        check_online=False,
        state_path=state,
        current_root=project,
    )
    check("an update runs first, and the user scope keeps its tools",
          result == 0
          and any(prompt == "Choice [4]: " for prompt in prompts)
          and any("keep installed (Codex)" in prompt for prompt in prompts)
          and (home / ".codex" / "AGENTS.md").is_symlink()
          and not (home / ".claude" / "rules").exists()
          and not (home / ".copilot" / "copilot-instructions.md").exists(),
          str(prompts))

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    project = sandbox / "project"
    checkout = sandbox / "checkout"
    home.mkdir()
    project.mkdir()
    checkout.mkdir()
    source = checkout / install.BASELINE
    source.write_bytes(bundled.content)
    claude_link = home / ".claude" / install.BASELINE
    claude_link.parent.mkdir()
    claude_link.symlink_to(source)
    (home / ".claude" / "CLAUDE.md").write_text(
        f"@{claude_link}\n", encoding="utf-8"
    )
    prompts = []
    migration_output = []
    answers = iter(["1", "n", "1"])

    def decline_migration(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    result = install.interactive_setup(
        home=home,
        input_fn=decline_migration,
        output=migration_output.append,
        check_online=False,
        state_path=sandbox / "state.json",
        current_root=project,
    )
    check("the migration prompt names the file, the benefit, and stays short",
          result == 2
          and any(prompt == "Choice [4]: " for prompt in prompts)
          and any("Claude Code reads the baseline from a file this setup does not "
                  "manage" in line for line in migration_output)
          and any(str(source) in line for line in migration_output)
          and any(prompt.startswith(
              "Switch to a managed copy of aiscb-0.1.14, so updates reach it?")
              for prompt in prompts),
          f"output={migration_output!r}, prompts={prompts!r}")

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    project = sandbox / "project"
    home.mkdir()
    project.mkdir()
    old_content = bundled.content.replace(
        bundled.baseline_id.encode(), b"aiscb-0.0.1", 1
    )
    install.install(["codex"], project, None, content=old_content)
    previous = install.scan_project(project, {})
    registry = install.empty_registry()
    install.record_installation(registry, previous, trusted=True)
    state = sandbox / "state.json"
    install.save_registry(state, registry)
    current = sandbox / "current"
    current.mkdir()
    output = []
    prompts: list[str] = []

    def update_answers(prompt: str) -> str:
        prompts.append(prompt)
        return ""

    result = install.interactive_setup(
        home=home,
        input_fn=update_answers,
        output=output.append,
        check_online=False,
        state_path=state,
        current_root=current,
    )
    check("guided setup ignores projects outside the current scope",
          result == 0
          and install.read_baseline(project / install.BASELINE).digest
              != bundled.digest
          and not any("Update project" in prompt for prompt in prompts)
          and "\nWhat would you like to do?" in output
          and "  1. install for user" in output
          and any(line.startswith("  2. install in project ") for line in output),
          f"prompts={prompts!r}, output={output!r}")

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    project = sandbox / "project"
    home.mkdir()
    project.mkdir()
    old_content = bundled.content.replace(
        bundled.baseline_id.encode(), b"aiscb-0.0.1", 1
    )
    install.install(["codex"], home, home, content=old_content)
    previous = [item for item in install.scan_user(home, {}) if item.kind == "user"][0]
    registry = install.empty_registry()
    install.record_installation(registry, previous, trusted=True)
    state = sandbox / "state.json"
    install.save_registry(state, registry)
    answers = iter(["", "2", "2", "n"])
    prompts = []
    output = []

    def update_user_then_project(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    result = install.interactive_setup(
        home=home,
        input_fn=update_user_then_project,
        output=output.append,
        check_online=False,
        state_path=state,
        current_root=project,
    )
    check("the user-first menu clearly offers the current project",
          result == 0
          and any(line.startswith("  -") and "project" in line
                  and "not installed" in line for line in output)
          and "  1. change tools for user" in output
          and any(line.startswith("  2. install in project ")
                  and str(project) in line for line in output),
          str(output))
    check("a user update can be followed by a project install",
          install.read_baseline(install.user_source(home)).digest == bundled.digest
          and (project / "AGENTS.md").is_symlink()
          and any("Update user-wide" in prompt for prompt in prompts),
          f"prompts={prompts!r}, output={output!r}")

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    current = sandbox / "current"
    project = sandbox / "known-project"
    home.mkdir()
    current.mkdir()
    project.mkdir()
    old_content = bundled.content.replace(
        bundled.baseline_id.encode(), b"aiscb-0.0.1", 1
    )
    install.install(["codex"], home, home, content=old_content)
    install.install(["codex"], project, None, content=old_content)
    registry = install.empty_registry()
    user_installation = [
        item for item in install.scan_user(home, {}) if item.kind == "user"
    ][0]
    install.record_installation(registry, user_installation, trusted=True)
    install.record_installation(
        registry, install.scan_project(project, {}), trusted=True
    )
    state = sandbox / "state.json"
    install.save_registry(state, registry)
    answers = iter(["n", ""])
    prompts = []

    def decline_separate_updates(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    install.interactive_setup(
        home=home,
        input_fn=decline_separate_updates,
        output=lambda _line: None,
        check_online=False,
        state_path=state,
        current_root=current,
    )
    update_prompts = [
        prompt for prompt in prompts if prompt.lstrip().startswith("Update ")
    ]
    check("only the active scopes receive update decisions",
          len(update_prompts) == 1
          and "user-wide" in update_prompts[0]
          and install.read_baseline(project / install.BASELINE).digest
              != bundled.digest,
          str(prompts))

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    current = sandbox / "current"
    target = sandbox / "target"
    home.mkdir()
    current.mkdir()
    target.mkdir()
    old_content = bundled.content.replace(
        bundled.baseline_id.encode(), b"aiscb-0.0.1", 1
    )
    (target / install.BASELINE).write_bytes(old_content)
    answers = iter(["", "y", "2", "2", "n"])
    output = []
    result = install.interactive_setup(
        home=home,
        input_fn=lambda _prompt: next(answers),
        output=output.append,
        check_online=False,
        state_path=sandbox / "state.json",
        current_root=target,
    )
    check("an unlinked project baseline is checked before tools are added",
          result == 0
          and install.read_baseline(target / install.BASELINE).digest == bundled.digest
          and (target / f"{install.BASELINE}.bak").read_bytes() == old_content
          and (target / "AGENTS.md").is_symlink(),
          str(output))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    same_version_content = bundled.content + b"\nlocal variation\n"
    install.install(["codex"], root, None, content=same_version_content)
    found = install.scan_project(root, {})
    check("same-version content differences are not reported as current",
          found is not None and found.has_update(bundled))

setup_script = install.REPO / "setup.sh"
setup_content = setup_script.read_text(encoding="utf-8")
setup_digest = hashlib.sha256(setup_script.read_bytes()).hexdigest()
readme = (install.REPO / "README.md").read_text(encoding="utf-8")
quick_start = readme.split("## Quick start", 1)[1].split("\n## ", 1)[0]
normalized_quick_start = " ".join(quick_start.split())
check("the quick start pins the exact remote bootstrap content",
      f"echo '{setup_digest} aiscb-setup.sh' | sha256sum --check"
      in normalized_quick_start)
bundle_hashes = {
    install.BASELINE: hashlib.sha256(install.SOURCE.read_bytes()).hexdigest(),
    "scripts/install.py": hashlib.sha256(
        install.INSTALLER_SOURCE.read_bytes()
    ).hexdigest(),
    "scripts/show_baseline_version.py": hashlib.sha256(
        install.VERSION_HOOK_SOURCE.read_bytes()
    ).hexdigest(),
}
check("the remote bootstrap pins and hashes one coherent bundle",
      "bundle_ref=\"aiscb-bundle-0.1.14-1\"" in setup_content
      and "/branches/main" not in setup_content
      and all(digest in setup_content for digest in bundle_hashes.values())
      and "--interactive --offline" in setup_content
      and setup_content.count("--max-filesize") == 1,
      setup_content)
completed = subprocess.run(
    ["bash", str(setup_script), "--help"],
    capture_output=True,
    text=True,
    cwd=tempfile.gettempdir(),
)
check("setup.sh is executable and reaches the installer",
      os.access(setup_script, os.X_OK)
      and completed.returncode == 0
      and "usage: install.py" in completed.stdout,
      completed.stderr or completed.stdout)

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    remote_setup = sandbox / "remote-setup.sh"
    remote_setup.write_bytes(setup_script.read_bytes())
    remote_setup.chmod(0o755)
    mock_bin = sandbox / "bin"
    mock_bin.mkdir()
    mock_curl = mock_bin / "curl"
    mock_curl.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "output=\n"
        "url=\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    --output) output=$2; shift 2 ;;\n"
        "    --proto|--max-time|--max-filesize) shift 2 ;;\n"
        "    --fail|--silent|--show-error) shift ;;\n"
        "    *) url=$1; shift ;;\n"
        "  esac\n"
        "done\n"
        "case \"$url\" in\n"
        "  */\"$aiscb_test_ref\"/*)\n"
        "    path=${url#*\"$aiscb_test_ref\"/}\n"
        "    cp \"$aiscb_test_repo/$path\" \"$output\"\n"
        "    if [ \"${aiscb_test_tamper:-}\" = \"$path\" ]; then\n"
        "      printf '\\nchanged\\n' >> \"$output\"\n"
        "    fi\n"
        "    if [ \"${aiscb_test_oversize:-}\" = \"$path\" ]; then\n"
        "      dd if=/dev/zero bs=1024 count=513 >> \"$output\" 2>/dev/null\n"
        "    fi ;;\n"
        "  *)\n"
        "    echo \"unexpected URL: $url\" >&2; exit 1 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    mock_curl.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{mock_bin}{os.pathsep}{environment['PATH']}"
    environment["aiscb_test_ref"] = "aiscb-bundle-0.1.14-1"
    environment["aiscb_test_repo"] = str(install.REPO)
    remote = subprocess.run(
        ["sh", str(remote_setup), "--help"],
        capture_output=True,
        text=True,
        cwd=sandbox,
        env=environment,
    )
    check("setup.sh bootstraps a hash-pinned bundle without a checkout",
          remote.returncode == 0 and "usage: install.py" in remote.stdout,
          remote.stderr or remote.stdout)
    tampered_environment = environment.copy()
    tampered_environment["aiscb_test_tamper"] = "scripts/install.py"
    tampered = subprocess.run(
        ["sh", str(remote_setup), "--help"],
        capture_output=True,
        text=True,
        cwd=sandbox,
        env=tampered_environment,
    )
    check("setup.sh refuses a bundle file whose hash changed",
          tampered.returncode == 2
          and "Integrity check failed for scripts/install.py" in tampered.stderr,
          tampered.stderr or tampered.stdout)
    oversized_environment = environment.copy()
    oversized_environment["aiscb_test_oversize"] = "scripts/install.py"
    oversized = subprocess.run(
        ["sh", str(remote_setup), "--help"],
        capture_output=True,
        text=True,
        cwd=sandbox,
        env=oversized_environment,
    )
    check("setup.sh refuses a bundle file over its size limit",
          oversized.returncode == 2
          and "exceeds its size limit" in oversized.stderr,
          oversized.stderr or oversized.stdout)

# --- update server ---------------------------------------------------------
#
# The updater fetches over the network, so the checks below stand in for a
# hostile or broken server: a redirect off GitHub, an oversized body, a release
# that does not match its tag. None of them touch the network.


class FakeResponse:
    def __init__(self, url: str, payload: bytes, headers: dict | None = None):
        self._url = url
        self._payload = payload
        self.headers = headers or {}

    def geturl(self) -> str:
        return self._url

    def read(self, size: int = -1) -> bytes:
        return self._payload if size < 0 else self._payload[:size]

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


class FakeOpener:
    def __init__(self, response: FakeResponse):
        self.response = response

    def open(self, _request: object, timeout: object = None) -> FakeResponse:
        return self.response


def read_json_with(response: FakeResponse, url: str = install.LATEST_RELEASE_URL):
    original = install.urllib.request.build_opener
    install.urllib.request.build_opener = lambda *_handlers: FakeOpener(response)
    try:
        return install._read_json_url(url)
    finally:
        install.urllib.request.build_opener = original


def rejected(call, because: str | None = None) -> bool:
    """True when the call refuses its input.

    json.JSONDecodeError is a ValueError, so a check that only catches the
    class passes even when the guard under test is gone and the payload merely
    fails to parse. Pass `because` wherever that confusion is possible.
    """
    try:
        call()
    except ValueError as error:
        return because is None or because in str(error)
    return False


good_url = install.LATEST_RELEASE_URL
check("plain HTTP is refused before any request",
      rejected(lambda: install._read_json_url(good_url.replace("https://", "http://")),
               "unexpected update server"))
check("a foreign update host is refused before any request",
      rejected(lambda: install._read_json_url("https://example.invalid/releases"),
               "unexpected update server"))
check("a valid response is parsed",
      read_json_with(FakeResponse(good_url, b'{"tag_name": "v1.2.3"}'))
      == {"tag_name": "v1.2.3"})
check("a redirect that lands off GitHub is refused",
      rejected(lambda: read_json_with(
          FakeResponse("https://example.invalid/releases", b'{}')),
          "unexpected update server"))
check("an announced oversized body is refused before reading",
      rejected(lambda: read_json_with(FakeResponse(
          good_url, b'{}', {"Content-Length": str(install.MAX_API_BYTES + 1)})),
          "too large"))
check("an oversized body is refused after reading",
      rejected(lambda: read_json_with(
          FakeResponse(good_url, b'{"padding": "' + b"y" * install.MAX_API_BYTES + b'"}')),
          "too large"))

valid_file = {
    "type": "file",
    "encoding": "base64",
    "content": base64.b64encode(new_content).decode(),
}


def release_feed(release: object, contents: object = None):
    def fetch(url: str) -> object:
        return release if url == install.LATEST_RELEASE_URL else (
            valid_file if contents is None else contents
        )
    return fetch


BAD_RELEASES = [
    ("a non-object release response", release_feed([])),
    ("a draft release", release_feed({"tag_name": "v9.8.7", "draft": True})),
    ("a prerelease", release_feed({"tag_name": "v9.8.7", "prerelease": True})),
    ("a release without a tag", release_feed({})),
    ("an over-long tag", release_feed({"tag_name": "v" + "9" * 200})),
    ("an unparsable tag", release_feed({"tag_name": "release-candidate"})),
    ("a baseline that is not a file",
     release_feed({"tag_name": "v9.8.7"}, {"type": "dir"})),
    ("an unsupported encoding",
     release_feed({"tag_name": "v9.8.7"}, {"type": "file", "encoding": "hex",
                                           "content": "00"})),
    ("content that is not base64",
     release_feed({"tag_name": "v9.8.7"}, {"type": "file", "encoding": "base64",
                                           "content": "not base64!"})),
    ("a baseline with an unexpected heading",
     release_feed({"tag_name": "v9.8.7"},
                  {"type": "file", "encoding": "base64",
                   "content": base64.b64encode(
                       b"# Something else\n\n`baseline-id: aiscb-9.8.7`\n").decode()})),
]
for label, feed in BAD_RELEASES:
    check(f"the updater rejects {label}",
          rejected(lambda feed=feed: install.fetch_release_baseline(feed)))


class FakeHTTPError(urllib.error.HTTPError):
    def __init__(self, code: int):
        super().__init__(good_url, code, "error", {}, None)


def available_with(error: Exception | None):
    original = install.fetch_release_baseline

    def failing(*_args, **_kwargs):
        raise error

    install.fetch_release_baseline = original if error is None else failing
    try:
        return install.latest_available(True)
    finally:
        install.fetch_release_baseline = original


offline_baseline, offline_note, _released = install.latest_available(False)
check("an offline check uses the bundled baseline",
      offline_baseline.digest == bundled.digest and "skipped" in offline_note)
_, missing_note, _released = available_with(FakeHTTPError(404))
check("a repository without releases falls back to the bundled baseline",
      "no published release" in missing_note, missing_note)
for label, error in (("a server error", FakeHTTPError(500)),
                     ("an unreachable host", OSError("no route")),
                     ("an invalid payload", ValueError("bad json"))):
    _, note, _released = available_with(error)
    check(f"{label} falls back to the bundled baseline",
          "online check unavailable" in note, note)


def newer_release(*_args, **_kwargs):
    older = bundled.content.replace(bundled.baseline_id.encode(), b"aiscb-0.0.1", 1)
    return install.parse_baseline(older, "test release")


original_fetch = install.fetch_release_baseline
install.fetch_release_baseline = newer_release
try:
    kept, newer_note, published = install.latest_available(True)
finally:
    install.fetch_release_baseline = original_fetch
check("a bundled baseline newer than the release wins",
      kept.digest == bundled.digest and "newer than published" in newer_note,
      newer_note)

# --- the release cache the startup hook reads ------------------------------

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    state = home / "state.json"
    original_fetch = install.fetch_release_baseline


    def unreachable(*_args, **_kwargs):
        raise OSError("no route")


    install.fetch_release_baseline = lambda *_args, **_kwargs: bundled
    try:
        without_consent = install.refresh_update_cache(home=home, state_path=state)
        untouched = not state.exists()
        install.save_registry(
            state, {**install.empty_registry(), "update_check": {"enabled": True}}
        )
        with_consent = install.refresh_update_cache(home=home, state_path=state)
        cached = json.loads(state.read_text())["update_check"]
        install.fetch_release_baseline = unreachable
        offline = install.refresh_update_cache(home=home, state_path=state)
    finally:
        install.fetch_release_baseline = original_fetch
    check("a background refresh runs only after the setup question was answered",
          without_consent == 1 and untouched and with_consent == 0
          and cached.get("latest") == bundled.baseline_id
          and isinstance(cached.get("checked"), int)
          and cached.get("enabled") is True,
          state.read_text())
    check("an unreachable update server leaves the cache alone",
          offline == 1
          and json.loads(state.read_text())["update_check"] == cached,
          state.read_text())

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    state = home / "state.json"
    original_fetch = install.fetch_release_baseline
    install.fetch_release_baseline = lambda *_args, **_kwargs: bundled
    try:
        install.installation_status(
            home=home,
            output=lambda _line: None,
            state_path=state,
            current_root=home,
        )
    finally:
        install.fetch_release_baseline = original_fetch
    check("a status run caches what the release check found",
          json.loads(state.read_text())["update_check"]["latest"]
          == bundled.baseline_id, state.read_text())

# --- placement refusals ----------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    link = root / install.BASELINE
    link.symlink_to(root / "elsewhere.md")
    report = []
    check("a symlinked baseline is never written through",
          install.place_baseline(root, report) is None
          and any("is a symlink" in line for line in report), str(report))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / install.BASELINE).mkdir()
    report = []
    check("a directory in the baseline's place is refused",
          install.place_baseline(root, report) is None
          and any("not a regular file" in line for line in report), str(report))

with tempfile.TemporaryDirectory() as tmp:
    missing = Path(tmp) / "absent"
    report = []
    check("a missing project directory is refused by default",
          install.place_baseline(missing, report) is None
          and any("does not exist" in line for line in report), str(report))
    created = install.place_baseline(missing, report, create_root=True)
    check("a missing directory is created only when asked",
          created is not None and created.is_file())

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    hook = install.version_hook_path(root, None)
    hook.parent.mkdir(parents=True)
    hook.write_text("print('something else')\n", encoding="utf-8")
    report = []
    check("a foreign hook helper is never overwritten",
          install._place_version_hook(root, None, report) is None
          and any("different hook helper" in line for line in report), str(report))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    hook = install.version_hook_path(root, None)
    hook.parent.mkdir(parents=True)
    hook.symlink_to(root / "elsewhere.py")
    report = []
    check("a symlinked hook helper is refused",
          install._place_version_hook(root, None, report) is None
          and any("is a symlink" in line for line in report), str(report))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    hook = install.version_hook_path(root, None)
    hook.mkdir(parents=True)
    report = []
    check("a directory in the hook helper's place is refused",
          install._place_version_hook(root, None, report) is None
          and any("not a regular file" in line for line in report), str(report))

check("the current hook helper is listed as shipped",
      hashlib.sha256(install.VERSION_HOOK_SOURCE.read_bytes()).hexdigest()
      in install.KNOWN_HOOK_DIGESTS,
      "append the new digest to KNOWN_HOOK_DIGESTS after changing the helper")

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    hook = install.version_hook_path(root, None)
    hook.parent.mkdir(parents=True)
    earlier = b"print('an earlier shipped hook helper')\n"
    hook.write_bytes(earlier)
    shipped = install.KNOWN_HOOK_DIGESTS
    install.KNOWN_HOOK_DIGESTS = shipped + (hashlib.sha256(earlier).hexdigest(),)
    report = []
    placed = install._place_version_hook(root, None, report)
    install.KNOWN_HOOK_DIGESTS = shipped
    check("an unchanged earlier hook helper is replaced",
          placed is not None
          and hook.read_bytes() == install.VERSION_HOOK_SOURCE.read_bytes()
          and any("updated" in line for line in report), str(report))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    shipped_source = install.VERSION_HOOK_SOURCE
    install.VERSION_HOOK_SOURCE = root / "absent.py"
    report = []
    placed = install._place_version_hook(root, None, report)
    install.VERSION_HOOK_SOURCE = shipped_source
    check("a missing hook helper source is reported, not raised",
          placed is None
          and any("hook helper source is missing" in line for line in report),
          str(report))

# --- the installer copy that makes updates work without a checkout ---------

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    report = install.install(["claude"], home, home)
    placed = install.user_data_root(home) / install.INSTALLER_NAME
    check("a user install places the installer beside the baseline",
          placed.is_file()
          and placed.read_bytes() == install.INSTALLER_SOURCE.read_bytes(),
          str(report))
    environment = dict(os.environ, HOME=str(home))
    environment.pop("XDG_CONFIG_HOME", None)
    standalone = subprocess.run(
        [sys.executable, str(placed), "--status", "--offline"],
        capture_output=True, text=True, timeout=60, env=environment,
        cwd=str(home), stdin=subprocess.DEVNULL,
    )
    check("the placed installer reports status without a checkout",
          standalone.returncode == 0 and "installed copy" in standalone.stdout,
          standalone.stderr or standalone.stdout)
    placed.write_bytes(b"# an outdated installer copy\n")
    again = install.install(["claude"], home, home)
    check("an outdated installer copy is replaced",
          placed.read_bytes() == install.INSTALLER_SOURCE.read_bytes()
          and any(line.startswith("updated") and install.INSTALLER_NAME in line
                  for line in again), str(again))

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    placed = install.user_data_root(home) / install.INSTALLER_NAME
    placed.parent.mkdir(parents=True)
    placed.symlink_to(home / "elsewhere.py")
    report = install.install(["claude"], home, home)
    check("a symlinked installer copy is refused",
          any("is a symlink" in line and install.INSTALLER_NAME in line
              for line in report), str(report))

# --- taking an installation back out ---------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    install.install(list(install.TOOLS), home, home)
    install.install_version_hooks(list(install.TOOLS), home, home)
    instructions = home / ".claude" / "CLAUDE.md"
    instructions.write_text(
        instructions.read_text(encoding="utf-8") + "my own line\n", encoding="utf-8"
    )
    settings = home / ".claude" / "settings.json"
    config = json.loads(settings.read_text(encoding="utf-8"))
    config["permissions"] = {"ask": ["Edit(/specs/**)"]}
    settings.write_text(json.dumps(config), encoding="utf-8")
    item = [i for i in install.scan_user(home, {}) if i.kind == "user"][0]
    report = []
    removed = install.remove_installation(item, report)
    leftovers = sorted(
        str(path.relative_to(home))
        for path in home.rglob("*")
        if path.is_file() or path.is_symlink()
    )
    check("removing an installation takes back every place it wrote",
          removed and leftovers == [".claude/CLAUDE.md", ".claude/settings.json"],
          f"{leftovers} / {report}")
    check("what the user wrote themselves stays",
          instructions.read_text(encoding="utf-8") == "my own line\n"
          and json.loads(settings.read_text(encoding="utf-8"))
              == {"permissions": {"ask": ["Edit(/specs/**)"]}},
          instructions.read_text(encoding="utf-8"))

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    install.install(["claude"], home, home)
    source = install.user_source(home)
    foreign = home / ".codex" / "AGENTS.md"
    foreign.parent.mkdir(parents=True, exist_ok=True)
    foreign.symlink_to(home / "somewhere-else.md")
    item = [i for i in install.scan_user(home, {}) if i.kind == "user"][0]
    report = []
    install.remove_installation(item, report)
    check("a link that points somewhere else is left alone",
          foreign.is_symlink()
          and foreign.readlink() == home / "somewhere-else.md"
          and not source.exists(), str(report))

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    manual = home / ".codex" / "AGENTS.md"
    manual.parent.mkdir(parents=True)
    manual.write_bytes(bundled.content)
    item = install.scan_user(home)[0]
    report = []
    removed = install.remove_installation(item, report)
    check("a file the installer never placed is reported, not deleted",
          not removed and manual.is_file()
          and any("not placed by the installer" in line for line in report),
          str(report))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    placeholder = install.Installation(
        "project", root, root / install.BASELINE, bundled, ("codex",)
    )
    output: list[str] = []
    cancelled = install._remove_interactively(
        install.empty_registry(), [placeholder], lambda _prompt: "", output.append
    )
    check("interactive removal can be cancelled without changing anything",
          not cancelled and output[-1] == "Nothing removed.", str(output))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    placeholder = install.Installation(
        "project", root, root / install.BASELINE, bundled, ("codex",)
    )
    answers = iter(["invalid", "0", "2"])
    output = []
    removed = install._remove_interactively(
        install.empty_registry(), [placeholder],
        lambda _prompt: next(answers), output.append,
    )
    check("interactive removal gives up after three invalid selections",
          not removed
          and sum("Invalid selection" in line for line in output) == 3
          and output[-1] == "Nothing removed.", str(output))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    placeholder = install.Installation(
        "project", root, root / install.BASELINE, bundled, ("codex",)
    )
    answers = iter(["all", "n"])
    output = []
    removed = install._remove_interactively(
        install.empty_registry(), [placeholder],
        lambda _prompt: next(answers), output.append,
    )
    check("interactive removal requires confirmation",
          not removed
          and any("This removes" in line for line in output)
          and output[-1] == "Nothing removed.", str(output))

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    install.install(["codex"], home, home)
    item = [entry for entry in install.scan_user(home, {})
            if entry.kind == "user"][0]
    registry = install.empty_registry()
    install.record_installation(registry, item, trusted=True)
    answers = iter(["1", "y"])
    output = []
    removed = install._remove_interactively(
        registry, [item], lambda _prompt: next(answers), output.append
    )
    check("interactive removal deletes the selected managed installation",
          removed
          and registry["user"] is None
          and not install.user_source(home).exists()
          and any(line.startswith("  removed") for line in output), str(output))

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    output: list[str] = []
    cancelled = install._install_project_interactively(
        home, install.empty_registry(), bundled, set(),
        lambda _prompt: "", output.append,
    )
    missing = install._install_project_interactively(
        home, install.empty_registry(), bundled, set(),
        lambda _prompt: str(home / "missing"), output.append,
    )
    check("guided project setup rejects an empty or missing directory",
          cancelled == (False, False)
          and missing == (False, False)
          and output == ["Project directory must be an existing non-root directory."],
          str(output))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    symlinked = root / "symlink.json"
    symlinked.symlink_to(root / "elsewhere.json")
    directory = root / "directory.json"
    directory.mkdir()
    non_object = root / "list.json"
    non_object.write_text("[]\n", encoding="utf-8")
    rejects_symlink = rejected(lambda: install._read_hook_config(symlinked))
    rejects_directory = rejected(lambda: install._read_hook_config(directory))
    rejects_non_object = rejected(lambda: install._read_hook_config(non_object))
    check("hook configuration rejects symlinks, directories, and non-objects",
          rejects_symlink and rejects_directory and rejects_non_object)

# --- import rewriting ------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    old, new = root / "old.md", root / "new.md"
    target = root / "CLAUDE.md"
    target.write_text(f"# notes\n@{old}\nkeep this\n", encoding="utf-8")
    check("an import line is rewritten in place",
          install._replace_import(target, old, new)
          and target.read_text(encoding="utf-8") == f"# notes\n@{new}\nkeep this\n",
          target.read_text(encoding="utf-8"))
    check("rewriting again is a no-op that still reports success",
          install._replace_import(target, old, new))
    unrelated = root / "OTHER.md"
    unrelated.write_text("# no import here\n", encoding="utf-8")
    check("a file without the old import is left alone",
          not install._replace_import(unrelated, old, new)
          and unrelated.read_text(encoding="utf-8") == "# no import here\n")
    missing = root / "absent.md"
    check("a missing import target is refused",
          not install._replace_import(missing, old, new))
    symlinked = root / "linked.md"
    symlinked.symlink_to(target)
    check("a symlinked import target is refused",
          not install._replace_import(symlinked, old, new))
    binary = root / "binary.md"
    binary.write_bytes(b"\xff\xfe\n")
    check("an unreadable import target is refused",
          not install._replace_import(binary, old, new))

# --- discovery edge cases --------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / ".github").mkdir()
    manual = root / ".github" / "copilot-instructions.md"
    manual.write_bytes(bundled.content)
    found = install.scan_unmanaged_project_files(root)
    check("a manually copied project instruction file is discovered",
          len(found) == 1 and found[0].kind == "unmanaged"
          and found[0].tools == ("copilot",), str(found))
    check("an unmanaged file is never offered for automatic updates",
          not found[0].has_update(bundled))
    (root / "AGENTS.md").write_text("not a baseline\n", encoding="utf-8")
    check("an unrelated instruction file is not mistaken for a baseline",
          len(install.scan_unmanaged_project_files(root)) == 1)

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    install.install(["claude"], home, home)
    broken = home / ".codex" / "AGENTS.md"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.symlink_to(home / "gone.md")
    found = install.scan_user(home, {})
    check("a dangling user link is skipped rather than reported",
          all(item.source.is_file() for item in found), str(found))

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    copied = claude_dir / install.BASELINE
    copied.write_bytes(bundled.content)
    (claude_dir / "CLAUDE.md").write_text(f"@{copied}\n", encoding="utf-8")
    found = [item for item in install.scan_user(home) if item.kind == "unmanaged"]
    check("a copied Claude baseline is reported as an unmanaged file",
          len(found) == 1 and found[0].tools == ("claude",), str(found))

# --- update refusals -------------------------------------------------------

customized = install.parse_baseline(
    bundled.content.replace(b"`baseline-id: aiscb-", b"`baseline-id: acme-", 1),
    "custom",
)
custom_installation = install.Installation(
    "project", Path("/nonexistent"), Path("/nonexistent/x.md"), customized, ("codex",)
)
report, updated = install.update_installation(
    custom_installation, bundled, lambda _q, _d: True
)
check("a customized baseline is never replaced",
      updated is None and any("customized" in line for line in report), str(report))

unmanaged_installation = install.Installation(
    "unmanaged", Path("/nonexistent"), Path("/nonexistent/x.md"), bundled, ("codex",)
)
report, updated = install.update_installation(
    unmanaged_installation, bundled, lambda _q, _d: True
)
check("an unmanaged file is not updated in place",
      updated is None and any("not managed" in line for line in report), str(report))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    install.install(["codex"], root, None, content=old_content)
    found = install.scan_project(root, {})
    (root / install.BASELINE).write_bytes(bundled.content)
    report, updated = install.update_installation(found, bundled, lambda _q, _d: True)
    check("a source that changed since discovery is not overwritten",
          updated is None
          and any("changed since discovery" in line for line in report), str(report))

# --- guided selection refusals ---------------------------------------------

invalid_output: list[str] = []
check("a repeatedly invalid tool selection cancels instead of guessing",
      install.choose_tools(lambda _p: "nonsense", invalid_output.append,
                           install.TOOLS) is None
      and sum("Invalid selection" in line for line in invalid_output) == 3,
      str(invalid_output))
check("tools can be chosen by name",
      install.choose_tools(lambda _p: "codex, claude", lambda _l: None,
                           install.TOOLS) == ["codex", "claude"])
check("the all keyword selects every tool",
      install.choose_tools(lambda _p: "all", lambda _l: None,
                           install.TOOLS) == list(install.TOOLS))
hook_invalid: list[str] = []
check("a repeatedly invalid hook selection skips the hooks",
      install.choose_hook_tools(lambda _p: "nonsense", hook_invalid.append,
                                list(install.TOOLS)) == []
      and sum("Invalid selection" in line for line in hook_invalid) == 3,
      str(hook_invalid))
check("an over-long answer is refused",
      rejected(lambda: install._read_answer(lambda _p: "x" * 4097, "? ")))
check("yes/no falls back to the default after three invalid answers",
      install.ask_yes_no(lambda _p: "maybe", "?", True) is True
      and install.ask_yes_no(lambda _p: "maybe", "?", False) is False)

# --- the command line ------------------------------------------------------
#
# main() reads Path.home() and writes a registry there, so every case below
# runs as its own process with HOME pointing into a throwaway directory. That
# also exercises the module's __main__ entry point.


def cli(args: list[str], home: Path, cwd: Path | None = None):
    environment = dict(os.environ, HOME=str(home))
    environment.pop("XDG_CONFIG_HOME", None)
    return subprocess.run(
        [sys.executable, str(install.REPO / "scripts" / "install.py"), *args],
        capture_output=True, text=True, timeout=60, env=environment,
        cwd=str(cwd) if cwd else None, stdin=subprocess.DEVNULL,
    )


REJECTED_ARGUMENTS = [
    ("an unknown tool", ["nonexistent-tool"]),
    ("--offline without a mode", ["--offline"]),
    ("--interactive with tools", ["--interactive", "codex"]),
    ("--interactive with --user", ["--interactive", "--user"]),
    ("--interactive with --status", ["--interactive", "--status"]),
    ("--status with tools", ["--status", "codex"]),
    ("--status with --user", ["--status", "--user"]),
    ("--into on the filesystem root", ["codex", "--into", "/"]),
    ("--refresh-update-cache with another mode",
     ["--refresh-update-cache", "--status"]),
    ("--uninstall with tools", ["--uninstall", "codex"]),
]

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    project = sandbox / "project"
    home.mkdir()
    project.mkdir()

    for label, args in REJECTED_ARGUMENTS:
        completed = cli(args, home)
        check(f"the command line refuses {label}",
              completed.returncode == 2, completed.stderr[:200])

    completed = cli(["codex", "--into", str(sandbox / "absent")], home)
    check("the command line refuses a missing project directory",
          completed.returncode == 2, completed.stderr[:200])

    cli(["--user"], home)
    completed = cli(["--uninstall", "--user"], home)
    check("the command line removes a user installation and says what it took",
          completed.returncode == 0
          and not install.user_source(home).exists()
          and "removed" in completed.stdout, completed.stdout[:300])
    completed = cli(["--uninstall", "--user"], home)
    check("removing nothing is reported as such",
          completed.returncode == 1 and "Nothing installed here." in completed.stdout,
          completed.stdout[:200])

    completed = cli(["--interactive"], home)
    check("guided setup refuses to run without a terminal",
          completed.returncode == 2 and "needs a terminal" in completed.stderr,
          completed.stderr[:200])

    completed = cli(["codex", "--into", str(project)], home)
    check("a project install from the command line succeeds",
          completed.returncode == 0 and (project / "AGENTS.md").is_symlink(),
          completed.stderr[:200])
    check("the command line records the installation for later updates",
          install.registry_path(home).is_file(),
          str(install.registry_path(home)))

    completed = cli(["--status", "--offline", "--into", str(project)], home)
    check("the status mode reports without changing anything",
          completed.returncode == 0 and "status" in completed.stdout.lower(),
          completed.stderr[:200])

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    completed = cli(["--user", "codex"], home)
    check("a user install from the command line succeeds",
          completed.returncode == 0
          and (home / ".codex" / "AGENTS.md").is_symlink(),
          completed.stderr[:200])

with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    home = sandbox / "home"
    project = sandbox / "project"
    home.mkdir()
    project.mkdir()
    state = install.registry_path(home)
    state.parent.mkdir(parents=True)
    state.write_text("not json\n", encoding="utf-8")
    completed = cli(["codex", "--into", str(project)], home)
    check("an invalid registry is reported but never overwritten",
          completed.returncode == 0
          and "registry is invalid" in completed.stderr
          and state.read_text(encoding="utf-8") == "not json\n",
          completed.stderr[:200])

# --- version comparison ----------------------------------------------------

check("prereleases sort before their stable release",
      install.SemVer.parse("1.0.0-alpha") < install.SemVer.parse("1.0.0-beta")
      < install.SemVer.parse("1.0.0"))
check("a longer prerelease sorts after its prefix",
      install.SemVer.parse("1.0.0-rc") < install.SemVer.parse("1.0.0-rc.1"))
check("numeric prerelease parts sort before alphanumeric ones",
      install.SemVer.parse("1.0.0-1") < install.SemVer.parse("1.0.0-alpha"))
check("build metadata does not affect ordering or equality",
      install.SemVer.parse("1.0.0+build.1") == install.SemVer.parse("1.0.0+build.2"))
check("versions are not comparable to other types",
      install.SemVer.parse("1.0.0").__lt__("1.0.0") is NotImplemented
      and install.SemVer.parse("1.0.0").__eq__("1.0.0") is NotImplemented)

# --- answers to path questions ---------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp).resolve()
    check("a bare tilde means the home directory",
          install._path_from_answer("~", home) == home)
    check("a tilde path is expanded below the home directory",
          install._path_from_answer("~/projects", home) == home / "projects")
    check("an absolute path is used as given",
          install._path_from_answer(str(home / "x"), home) == home / "x")

# --- instruction files that cannot be joined safely ------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    source = root / install.BASELINE
    source.write_bytes(bundled.content)
    unreadable = root / "CLAUDE.md"
    unreadable.write_bytes(b"\xff\xfe\n")
    report = []
    install.install_import_line(unreadable, source, report)
    check("an instruction file that is not UTF-8 is never appended to",
          any("cannot safely read" in line for line in report)
          and unreadable.read_bytes() == b"\xff\xfe\n", str(report))

    broken = root / "BROKEN.md"
    broken.symlink_to(root / "gone.md")
    report = []
    install.install_import_line(broken, source, report)
    check("a broken instruction symlink is refused, not replaced",
          any("broken symlink" in line for line in report)
          and broken.is_symlink(), str(report))

    foreign = root / "FOREIGN.md"
    foreign.write_text("# someone else's instructions\n", encoding="utf-8")
    report = []
    install.install_import_line(foreign, source, report)
    check("an existing instruction file keeps its content and names the manual step",
          any("add the line" in line for line in report)
          and foreign.read_text(encoding="utf-8") == "# someone else's instructions\n",
          str(report))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    target = root / "partial.md"


    class Unwritable:
        """Not bytes-like, so the write fails once the file already exists."""

    try:
        install._write_new(target, Unwritable())
    except TypeError:
        pass
    check("a write interrupted midway leaves no partial file behind",
          not target.exists(), str(target))


# The signed release bundle: an installed copy may apply a later release only
# when a key it carries signed the manifest and every file matches it.
def generate_key(path: Path) -> str:
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", path.name, "-f", str(path)],
        check=True,
        capture_output=True,
    )
    fields = path.with_name(path.name + ".pub").read_text().split()
    return f"{install.SIGNER_PRINCIPAL} {fields[0]} {fields[1]}"


def sign(sandbox: Path, key: Path, manifest: bytes, namespace: str | None = None) -> bytes:
    document = sandbox / f"manifest-{len(list(sandbox.iterdir()))}.json"
    document.write_bytes(manifest)
    subprocess.run(
        ["ssh-keygen", "-Y", "sign", "-f", str(key),
         "-n", namespace or install.SIGNATURE_NAMESPACE, str(document)],
        check=True,
        capture_output=True,
    )
    return document.with_name(document.name + ".sig").read_bytes()


def verification_error(
    manifest: bytes, signature: bytes, signers: tuple[str, ...]
) -> str | None:
    try:
        install.verify_manifest_signature(manifest, signature, signers)
    except ValueError as error:
        return str(error)
    return None


def contents_payload(content: bytes) -> dict[str, object]:
    return {
        "type": "file",
        "encoding": "base64",
        "content": base64.b64encode(content).decode(),
    }


def release_tree_fetcher(
    release: object, tag: str, tree: dict[str, bytes], calls: list[str]
):
    def fetch_json(url: str) -> object:
        calls.append(url)
        if url == install.LATEST_RELEASE_URL:
            return release
        prefix = install.CONTENTS_ROOT_URL + "/"
        if not url.startswith(prefix):
            raise AssertionError(f"unexpected update URL {url}")
        path, _, query = url[len(prefix):].partition("?")
        if query != f"ref={tag}":
            raise AssertionError(f"unexpected ref in {url}")
        if path not in tree:
            raise urllib.error.HTTPError(url, 404, "missing", None, None)  # type: ignore[arg-type]
        return contents_payload(tree[path])
    return fetch_json


with tempfile.TemporaryDirectory() as tmp:
    sandbox = Path(tmp)
    release_key = sandbox / "release-key"
    release_signer = generate_key(release_key)
    other_key = sandbox / "other-key"
    other_signer = generate_key(other_key)
    trusted = (release_signer,)

    current_files = {
        name: (install.REPO / name).read_bytes() for name in install.BUNDLE_FILES
    }
    current_manifest = install.manifest_document(current_files)
    parsed = install.parse_manifest(current_manifest)
    check("the manifest names the bundled baseline and pins every bundled file",
          parsed.baseline_id == bundled.baseline_id
          and set(parsed.files) == set(install.BUNDLE_FILES)
          and all(
              parsed.files[name]
              == (len(content), hashlib.sha256(content).hexdigest())
              for name, content in current_files.items()
          ))
    check("the manifest is canonical, so signing and checking see the same bytes",
          current_manifest == install.manifest_document(dict(reversed(
              list(current_files.items()))))
          and current_manifest.endswith(b"}\n"))

    signature = sign(sandbox, release_key, current_manifest)
    check("a manifest signed by the release key verifies",
          verification_error(current_manifest, signature, trusted) is None)
    check("a manifest changed after signing is refused",
          verification_error(current_manifest + b"\n", signature, trusted) is not None)
    check("a signature from a key the installer does not carry is refused",
          verification_error(current_manifest, signature, (other_signer,)) is not None)
    check("a signature made for another purpose is refused",
          verification_error(
              current_manifest, sign(sandbox, release_key, current_manifest, "file"),
              trusted,
          ) is not None)
    check("an installer without a release key verifies nothing",
          "no release signing key"
          in (verification_error(current_manifest, signature, ()) or ""))
    check("a signature that is not an OpenSSH signature is refused before ssh-keygen runs",
          "unexpected format"
          in (verification_error(current_manifest, b"garbage", trusted) or ""))
    original_which = install.shutil.which
    try:
        install.shutil.which = lambda _name: None
        without_tool = verification_error(current_manifest, signature, trusted)
    finally:
        install.shutil.which = original_which
    check("a missing ssh-keygen is a refusal, not a pass",
          "ssh-keygen" in (without_tool or ""))

    document = json.loads(current_manifest)
    helper_name = "scripts/show_baseline_version.py"
    rejected_manifests = {
        "an unknown top-level field": {**document, "note": "x"},
        "a missing field": {key: value for key, value in document.items()
                            if key != "files"},
        "another schema": {**document, "schema": 2},
        "another baseline's name": {**document, "baseline_id": "acme-1.0.0"},
        "a derived baseline": {**document, "baseline_id": "aiscb-1.0.0+acme"},
        "a baseline id that is not a string": {**document, "baseline_id": 1},
        "a missing bundled file": {**document, "files": {
            name: entry for name, entry in document["files"].items()
            if name != helper_name}},
        "an extra file": {**document, "files": {
            **document["files"], "scripts/extra.py": document["files"][helper_name]}},
        "an entry with an unknown field": {**document, "files": {
            **document["files"],
            helper_name: {**document["files"][helper_name], "mode": "755"}}},
        "a size of zero": {**document, "files": {
            **document["files"],
            helper_name: {**document["files"][helper_name], "size": 0}}},
        "a size over the file's limit": {**document, "files": {
            **document["files"],
            helper_name: {**document["files"][helper_name],
                          "size": install.MAX_BASELINE_BYTES + 1}}},
        "a boolean size": {**document, "files": {
            **document["files"],
            helper_name: {**document["files"][helper_name], "size": True}}},
        "a digest that is not SHA-256 hex": {**document, "files": {
            **document["files"],
            helper_name: {**document["files"][helper_name], "sha256": "abc"}}},
    }
    for label, variant in rejected_manifests.items():
        try:
            install.parse_manifest(json.dumps(variant).encode())
        except ValueError:
            continue
        check(f"a manifest with {label} is refused", False)
    try:
        install.parse_manifest(b"[]")
        install.parse_manifest(b"")
    except ValueError:
        shape_refused = True
    else:
        shape_refused = False
    check("a manifest that is not an object is refused", shape_refused)

    newer_baseline = bundled.content.replace(
        bundled.baseline_id.encode(), b"aiscb-9.8.7", 1
    )
    newer_files = {**current_files, install.BASELINE: newer_baseline}
    newer_manifest = install.manifest_document(newer_files)
    newer_signature = sign(sandbox, release_key, newer_manifest)
    tag = "aiscb-9.8.7"
    stable = {"tag_name": tag, "draft": False, "prerelease": False}
    good_tree = {
        install.MANIFEST_NAME: newer_manifest,
        install.SIGNATURE_NAME: newer_signature,
        **newer_files,
    }

    def trusted_verify(manifest: bytes, signature_bytes: bytes) -> None:
        install.verify_manifest_signature(manifest, signature_bytes, trusted)

    def run_update(release, tree, verify=trusted_verify, current=bundled):
        calls: list[str] = []
        lines: list[str] = []
        runs: list[tuple[list[str], dict[str, bytes], Path]] = []

        def fake_run(command, check):
            staged = Path(command[1]).parent.parent
            files = {
                str(path.relative_to(staged)): path.read_bytes()
                for path in staged.rglob("*") if path.is_file()
            }
            runs.append((list(command), files, staged))
            return subprocess.CompletedProcess(command, 0)

        code = install.release_update(
            output=lines.append,
            current=current,
            fetch_json=release_tree_fetcher(release, tag, tree, calls),
            verify=verify,
            run=fake_run,
        )
        return code, calls, lines, runs

    code, calls, lines, runs = run_update(stable, good_tree)
    command, staged_files, staged_dir = runs[0] if runs else ([], {}, sandbox)
    check("a newer signed release is staged and its own guided setup runs",
          code == 0 and len(runs) == 1
          and command[0] == sys.executable
          and command[1].endswith(os.path.join("scripts", "install.py"))
          and command[2:] == ["--interactive", "--offline"]
          and staged_files == newer_files,
          f"code={code} lines={lines!r} command={command!r}")
    check("the staged bundle is removed once its setup has finished",
          not staged_dir.exists())
    fetched = [url.split("/contents/", 1)[1].split("?", 1)[0]
               for url in calls if "/contents/" in url]
    check("the manifest and its signature are fetched before any bundled file",
          fetched[:2] == [install.MANIFEST_NAME, install.SIGNATURE_NAME]
          and set(fetched[2:]) == set(install.BUNDLE_FILES), str(fetched))

    code, calls, lines, runs = run_update(stable, good_tree, current=install.parse_baseline(
        newer_baseline, "installed"))
    check("a release that is not newer changes nothing and fetches no file",
          code == 0 and not runs and calls == [install.LATEST_RELEASE_URL]
          and any("is current" in line for line in lines), str(lines))
    code, calls, lines, runs = run_update(
        {**stable, "tag_name": "aiscb-0.0.1"}, good_tree)
    check("an older release is never applied",
          code == 0 and not runs and calls == [install.LATEST_RELEASE_URL])
    code, calls, lines, runs = run_update({**stable, "prerelease": True}, good_tree)
    check("a prerelease is not an update", code == 1 and not runs and len(calls) == 1)

    refusals = {
        "a signature from a key the installer does not carry": {
            **good_tree, install.SIGNATURE_NAME: sign(sandbox, other_key, newer_manifest)},
        "a manifest signed for the installed version, served under the new tag": {
            **good_tree, install.MANIFEST_NAME: current_manifest,
            install.SIGNATURE_NAME: signature},
        "a bundled file changed after signing": {
            **good_tree, "scripts/install.py":
                current_files["scripts/install.py"] + b"\n# changed\n"},
        "a bundled file longer than the manifest says": {
            **good_tree, install.BASELINE: newer_baseline + b"\n"},
        "a bundled file shorter than the manifest says": {
            **good_tree, install.BASELINE: newer_baseline[:-1]},
    }
    for label, tree in refusals.items():
        code, calls, lines, runs = run_update(stable, tree)
        check(f"{label} is refused without running anything",
              code == 2 and not runs
              and any("Update refused" in line for line in lines)
              and any(install.QUICK_START_URL in line for line in lines),
              f"code={code} lines={lines!r}")
    code, calls, lines, runs = run_update(stable, refusals[
        "a signature from a key the installer does not carry"])
    check("a refused signature stops the download before any bundled file",
          not any(name in url for url in calls for name in install.BUNDLE_FILES
                  if name != install.BASELINE)
          and not any(url.endswith(f"{install.BASELINE}?ref={tag}") for url in calls),
          str(calls))
    code, calls, lines, runs = run_update(
        stable, good_tree,
        verify=lambda manifest, signature_bytes: install.verify_manifest_signature(
            manifest, signature_bytes, ()))
    check("an installer without a release key refuses and names the Quick start",
          code == 2 and not runs and any("no release signing key" in line for line in lines)
          and any(install.QUICK_START_URL in line for line in lines), str(lines))
    code, calls, lines, runs = run_update(
        stable, {key: value for key, value in good_tree.items()
                 if key != install.MANIFEST_NAME})
    check("a release without a manifest is a failed download, not an update",
          code == 1 and not runs and any("download failed" in line for line in lines),
          str(lines))
    derived = install.parse_baseline(
        bundled.content.replace(bundled.baseline_id.encode(), b"aiscb-0.1.0+acme", 1),
        "installed",
    )
    code, calls, lines, runs = run_update(stable, good_tree, current=derived)
    check("a derived baseline is not replaced by the official release",
          code == 2 and not calls and not runs, str(lines))

    committed_manifest = install.REPO / install.MANIFEST_NAME
    committed_signature = install.REPO / install.SIGNATURE_NAME
    check("the committed manifest describes the bundled files",
          committed_manifest.is_file()
          and committed_manifest.read_bytes() == current_manifest,
          "run: make sign-bundle KEY=<release key>")
    committed_error = (
        verification_error(current_manifest, committed_signature.read_bytes(),
                           install.ALLOWED_SIGNERS)
        if committed_signature.is_file() else "no signature file"
    )
    check("the committed manifest carries a signature from a key install.py trusts",
          committed_error is None, committed_error or "")

    import bundle_manifest  # noqa: E402

    repo_copy = sandbox / "repo"
    for name, content in current_files.items():
        (repo_copy / name).parent.mkdir(parents=True, exist_ok=True)
        (repo_copy / name).write_bytes(content)
    try:
        bundle_manifest.sign_manifest(repo_copy, release_key)
    except ValueError as error:
        not_carried = str(error)
    else:
        not_carried = ""
    check("signing with a key install.py does not carry is refused and names the line",
          release_signer in not_carried, not_carried)
    original_signers = install.ALLOWED_SIGNERS
    try:
        install.ALLOWED_SIGNERS = trusted
        bundle_manifest.sign_manifest(repo_copy, release_key)
        bundle_manifest.verify_bundle(repo_copy)
        signed_ok = True
        (repo_copy / helper_name).write_bytes(current_files[helper_name] + b"\n")
        try:
            bundle_manifest.verify_bundle(repo_copy)
        except ValueError as error:
            stale = str(error)
        else:
            stale = ""
    finally:
        install.ALLOWED_SIGNERS = original_signers
    check("the release tool writes a manifest and signature the installer verifies",
          signed_ok and (repo_copy / install.MANIFEST_NAME).read_bytes()
          == current_manifest)
    check("a manifest that no longer matches the bundled files fails verification",
          "does not describe" in stale, stale)

    for argv, reason in ((["--update", "--offline"], "combined with other arguments"),
                         (["--update"], "run without a terminal")):
        completed = subprocess.run(
            [sys.executable, str(install.INSTALLER_SOURCE), *argv],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        check(f"--update refuses to run {reason}",
              completed.returncode == 2 and "usage" in completed.stderr,
              completed.stderr[-200:])

print(f"\ninstall: {'ok' if not failures else f'{failures} failures'}")
sys.exit(1 if failures else 0)
