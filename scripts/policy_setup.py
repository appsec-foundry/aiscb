"""Default modular setup and explicit migration of managed complete installs."""

import json
import shlex
from pathlib import Path

import install_policy as policy
import policy_loader as loader


def layout(legacy, home, root, user):
    if not user:
        return root, policy.ENTRY_POINTS
    points = {
        "claude": str(legacy.tool_config_root("claude", home) / "CLAUDE.md"),
        "codex": str(legacy.tool_config_root("codex", home) / "AGENTS.md"),
        "copilot": str(legacy.tool_config_root("copilot", home) /
                       "instructions" / legacy.VSCODE_INSTRUCTIONS_NAME),
        # Kiro always includes an AGENTS.md from its global steering directory.
        "kiro": str(home / ".kiro/steering/AGENTS.md"),
    }
    shared = home / ".copilot/instructions" / legacy.VSCODE_INSTRUCTIONS_NAME
    if str(shared) != points["copilot"]:
        points["copilot-vscode"] = str(shared)
    return home, points


def text(path):
    if not path.exists() and not path.is_symlink():
        return ""
    if path.is_symlink():
        # Instruction symlinks are read only for conflict discovery, never written through.
        path = path.resolve(strict=True)
    return loader.read(path).decode()


def contains_policy(value):
    return any(marker in value for marker in
               ("baseline-id:", "secure-coding-baseline.md", "session-loader.md"))


def complete_policy(value):
    return contains_policy(value) and ("Installation mode: modular." not in value
                                       or "`module-id:" in value)


def instruction_files(directory):
    if not directory.exists():
        return []
    paths = []
    for path in directory.rglob("*.md"):
        paths.append(path)
        if len(paths) > 256:
            raise ValueError(f"too many instruction files to check safely: {directory}")
    return paths


def inherited_conflicts(legacy, home, root, tools):
    """Inspect bounded known instruction locations, not arbitrary user files."""
    _, user_points = layout(legacy, home, root, True)
    paths = {Path(user_points[t]) for t in tools}
    if "codex" in tools:
        paths.add(legacy.tool_config_root("codex", home) / "AGENTS.override.md")
    if "copilot" in tools:
        paths.add(legacy.previous_copilot_user_target(home))
        paths.update(instruction_files(legacy.tool_config_root("copilot", home) / "instructions"))
    if "claude" in tools or "copilot" in tools:
        paths.update(instruction_files(legacy.tool_config_root("claude", home) / "rules"))
    if "kiro" in tools:
        paths.update(instruction_files(home / ".kiro/steering"))
    # Ancestor instructions can bring an eager copy back even after user migration.
    for parent in root.parents:
        if "codex" in tools or "copilot" in tools:
            paths.update((parent / "AGENTS.md", parent / "AGENTS.override.md"))
        if "claude" in tools or "copilot" in tools:
            paths.update((parent / "CLAUDE.md", parent / "CLAUDE.local.md",
                          parent / ".claude/CLAUDE.md"))
    conflicts = []
    for path in sorted(paths):
        value = text(path)
        if complete_policy(value):
            conflicts.append(path)
    return conflicts


def migration(legacy, home, root, user, tools, points, enabled):
    """Plan only exact managed links/copies/imports; reject drift before any write."""
    source = legacy.user_source(home) if user else root / legacy.BASELINE
    targets = legacy.user_targets(home) if user else legacy.project_targets(root)
    candidates = {Path(points[t]) if user else root / points[t] for t in tools}
    for tool in tools:
        if tool not in targets:
            continue  # No legacy complete integration: copilot-vscode, kiro.
        candidates.update(path for _, path in targets[tool])
    if user and "copilot" in tools:
        candidates.add(legacy.previous_copilot_user_target(home))
    existing = [p for p in candidates if contains_policy(text(p)) and
                policy.START not in text(p)]
    if not existing:
        return {}, []
    if not enabled:
        raise ValueError("existing baseline; rerun with --migrate to replace verified "
                         "managed complete instructions (close affected sessions first): "
                         + ", ".join(map(str, sorted(existing))))
    if source.is_symlink() or not source.is_file():
        raise ValueError("existing baseline has no regular managed source; inspect it manually")
    raw = loader.read(source)
    if not legacy.parse_baseline(raw, "migration").is_official:
        raise ValueError("derived baseline must be migrated with its organization policy")
    registry, writable, _ = legacy.load_registry(legacy.registry_path(home))
    record = registry.get("user") if user else registry.get("projects", {}).get(str(root))
    recorded = legacy._entry_digest(record)
    if (not writable or (loader.digest(raw) != recorded and
                         raw != legacy.bundled_baseline().content)):
        raise ValueError("existing baseline is modified or unrecorded; migration refused")
    prepared = {}
    for path in existing:
        # Validate parents even when the final entry is a recognized managed link.
        loader.safe_path(Path(path.anchor), str(path.parent).lstrip("/"))
        if (legacy._session_link(path, source) or legacy._link_points_to(path, source)
                or legacy._copy_matches(path, source)
                or legacy._vscode_copy_matches(path, source)):
            prepared[path] = b""
        elif not path.is_symlink():
            value = text(path)
            imports = {f"@{source}"}
            if user:
                imports.add(f"@{targets['claude'][0][1]}")
            kept = "".join(line for line in value.splitlines(keepends=True)
                           if line.rstrip("\r\n") not in imports)
            if contains_policy(kept):
                raise ValueError(f"unmanaged or modified baseline instructions: {path}")
            prepared[path] = kept.encode()
        else:
            raise ValueError(f"unmanaged baseline link: {path}")
    # A dynamic hook can inject the complete source independently of its Markdown
    # entry. Remove only exact managed handlers and preserve unrelated hooks.
    for tool in ("claude", "codex"):
        if tool not in tools or not legacy._session_link(targets[tool][0][1], source):
            continue
        hook_home = home if user else None
        hook_path = legacy._session_hook_path(tool, root, hook_home)
        loader.safe_path(Path(hook_path.anchor), str(hook_path).lstrip("/"))
        config, exists = legacy._read_hook_config(hook_path)
        if not exists:
            continue
        hooks = config.get("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError("invalid session hook configuration")
        helper = legacy.version_hook_path(root, hook_home)
        for event, expected_hook in (
                ("SessionStart", legacy._session_hook(tool, helper, not user)),
                ("UserPromptSubmit", legacy._session_check_hook(tool, helper, not user))):
            entries = hooks.get(event, [])
            if not isinstance(entries, list):
                raise ValueError("invalid session hook event")
            hooks[event] = [entry for entry in entries if entry != expected_hook]
            if legacy.VERSION_HOOK_NAME in json.dumps(hooks[event]):
                raise ValueError("modified session hook; migration refused")
            if not hooks[event]:
                hooks.pop(event, None)
        if not hooks:
            config.pop("hooks", None)
        prepared[hook_path] = (json.dumps(config, indent=2) + "\n").encode()
    return prepared, existing


def user_updater(legacy, home):
    """Preflight updater ownership before changing instruction entry points."""
    from bundle_resources import installer_bytes
    destination = loader.safe_path(home, ".aiscb")
    contents = {
        "install.py": installer_bytes(legacy),
        legacy.BASELINE: legacy.bundled_baseline().content,
        legacy.VERSION_HOOK_NAME: legacy.read_limited(
            legacy.VERSION_HOOK_SOURCE, legacy.MAX_BASELINE_BYTES),
    }
    record_path = loader.safe_path(home, ".aiscb/updater.json")
    previous = json.loads(loader.read(record_path), object_pairs_hook=loader.pairs) if record_path.exists() else {}
    if (not isinstance(previous, dict) or (previous and set(previous) != set(contents))
            or any(not isinstance(v, str) or not loader.DIGEST.fullmatch(v) for v in previous.values())):
        raise ValueError("invalid updater ownership record")
    edits = {}
    for name, value in contents.items():
        path = loader.safe_path(destination, name)
        if path.exists():
            current = loader.read(path)
            if loader.digest(current) != previous.get(name):
                raise ValueError(f"modified or unowned updater artifact: {path}")
        edits[path] = value
    edits[record_path] = (json.dumps({name: loader.digest(raw) for name, raw in contents.items()},
                                   indent=2) + "\n").encode()
    return edits


def run(legacy, args, *, home=None, input_fn=input, output=print):
    home = (home or Path.home()).resolve()
    root = (args.into or Path.cwd()).resolve()
    if getattr(args, "refresh_installed", False):
        if args.user and args.into:
            raise ValueError("--user and --into cannot be combined")
        storage, points = layout(legacy, home, root, args.user)
        if not (storage / ".aiscb/installation.json").exists():
            return refresh_complete(legacy, args, home, root, output)
        policy.status(storage, points)
        record = policy.installation_record(storage, points)
        package, contents, _ = loader.load_package(
            storage / ".aiscb/releases" / record["digest"], record["digest"])
        if package["overlay"] is not None:
            raise ValueError("organization installations must use their organization updater")
        current = legacy.parse_baseline(contents[package["core"]].encode(), "installed")
        available = legacy.bundled_baseline()
        if not current.is_official or not available.is_official or available.version < current.version:
            raise ValueError("refresh requires the same official baseline without a downgrade")
        args.tools = [tool for tool, rel in points.items()
                      if rel in record["entries"] and tool in legacy.MODULAR_TOOLS]
        if not args.tools:
            raise ValueError("no supported installed tools")
        args.complete = not record["modular"]
        if getattr(args, "dry_run", False):
            if args.user:
                user_updater(legacy, home)
            output(f"Would refresh {current.baseline_id} to {available.baseline_id} "
                   f"for {', '.join(args.tools)} in {storage}; mode preserved.")
            return 0
    if args.interactive:
        output("aiscb setup: core and discovery first; modules load only when needed.")
        scope = input_fn("Install for [u]ser or [p]roject? [u] ").strip().lower() or "u"
        if scope not in {"u", "p"}:
            raise ValueError("choose u or p")
        args.user = scope == "u"
        if not args.user:
            root = Path(input_fn(f"Project directory [{root}]: ").strip() or root).expanduser().resolve()
        selected = input_fn("Tools (claude codex copilot kiro) [all]: ").strip()
        args.tools = selected.split() if selected else list(legacy.MODULAR_TOOLS)
    tools = list(dict.fromkeys(args.tools or legacy.MODULAR_TOOLS))
    if any(t not in legacy.MODULAR_TOOLS for t in tools):
        raise ValueError("unknown tool; choose claude, codex, copilot or kiro")
    if args.user and args.into:
        raise ValueError("--user and --into cannot be combined")
    storage, points = layout(legacy, home, root, args.user)
    if args.user and "copilot" in tools and "copilot-vscode" in points:
        tools.append("copilot-vscode")
    if args.status:
        output(policy.status(storage, points))
        record = policy.installation_record(storage, points)
        output("Installation mode: " + ("modular" if record["modular"] else "complete"))
        return 0
    if args.uninstall:
        output(policy.uninstall(storage, points))
        return 0
    if not args.user and not args.complete:
        conflicts = inherited_conflicts(legacy, home, root, tools)
        if conflicts:
            raise ValueError("inherited complete baseline; migrate its user/ancestor "
                             "installation first: " + ", ".join(map(str, conflicts)))
    if "codex" in tools:
        target = Path(points["codex"]) if args.user else root / points["codex"]
        if legacy.codex_override(target) is not None:
            raise ValueError(f"{target.with_name('AGENTS.override.md')} overrides the entry point")
    if args.interactive and not args.migrate:
        try:
            migration(legacy, home, root, args.user, tools, points, False)
        except ValueError as exc:
            output(str(exc))
            if input_fn("Migrate verified managed instructions? [y/N] ").strip().lower() != "y":
                raise ValueError("migration not approved") from exc
            args.migrate = True
    prepared, migrated = migration(legacy, home, root, args.user, tools, points, args.migrate)
    extra = []
    if "claude" in tools or "copilot" in tools:
        directory = (legacy.tool_config_root("claude", home) if args.user else root / ".claude")
        extra.extend(instruction_files(directory / "rules"))
    if "copilot" in tools:
        directory = (legacy.tool_config_root("copilot", home) if args.user else root / ".github")
        extra.extend(instruction_files(directory / "instructions"))
    if "kiro" in tools:
        extra.extend(instruction_files((home if args.user else root) / ".kiro/steering"))
    entry_paths = {Path(points[t]) if args.user else root / points[t] for t in tools}
    for path in extra:
        if path in entry_paths:
            continue  # The managed-block verifier checks these before replacement.
        value = prepared[path].decode() if path in prepared else text(path)
        if complete_policy(value):
            raise ValueError(f"additional complete policy in automatic instructions: {path}")
    updater_edits = user_updater(legacy, home) if args.user else {}
    if args.user and "copilot" in tools:
        for key in ("copilot", "copilot-vscode"):
            if key not in tools:
                continue
            target = Path(points[key])
            if not target.exists() or (target in prepared and not prepared[target]):
                prepared[target] = legacy.VSCODE_INSTRUCTIONS_HEADER
    for message in policy.install(tools, storage, modular=not args.complete,
                                  bundle=args.organization, expected=args.organization_sha256,
                                  entry_points=points, prepared=prepared):
        output(message)
    if migrated:
        output("Migrated managed instructions; the old complete source remains on disk, "
               "outside the configured instruction entry points.")
    if args.user:
        # Keep the authenticated distribution intact for signed updates. A checkout
        # produces the same self-contained installer as release staging.
        destination = loader.safe_path(home, ".aiscb")
        for path, content in updater_edits.items():
            policy.atomic(path, content)
        command = shlex.join(["python3", str(destination / "install.py"), "--update"])
        output(f"Signed update entry point: {command}")
    return 0


def refresh_complete(legacy, args, home, root, output):
    """Refresh only a recorded legacy scope, retaining its existing loading hooks."""
    registry_path = legacy.registry_path(home)
    registry, writable, _ = legacy.load_registry(registry_path)
    if not writable:
        raise ValueError("installation registry is not writable")
    if args.user:
        items = [item for item in legacy.scan_user(home, registry.get("user"))
                 if item.kind == "user"]
    else:
        entry = registry.get("projects", {}).get(str(root))
        item = legacy.scan_project(root, entry)
        items = [item] if item is not None else []
    if len(items) != 1:
        raise ValueError("no unique recorded installation; use the terminal updater")
    item = items[0]
    available = legacy.bundled_baseline()
    if (not item.tools or legacy._lacks_install_record(item)
            or not item.baseline.is_official or not available.is_official
            or available.version < item.baseline.version):
        raise ValueError("modified, unrecorded, foreign, or newer installation; refresh refused")
    if args.dry_run:
        output(f"Would refresh {item.baseline.baseline_id} to {available.baseline_id} "
               f"for {', '.join(item.tools)} in {item.root}; complete mode preserved.")
        return 0
    changed, incomplete = legacy._apply_update(item, available, registry, output)
    if changed:
        legacy.save_registry(registry_path, registry)
    if incomplete:
        raise ValueError("some managed artifacts could not be refreshed; inspect this installation")
    return 0
