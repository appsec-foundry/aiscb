#!/usr/bin/env python3
"""Local policy installation for reviewed checkouts and authenticated org bundles."""

import json
import os
import re
import shlex
import shutil
import tempfile
from pathlib import Path

import build_baseline
import policy_loader as loader

ROOT = Path(__file__).resolve().parent.parent
# Kiro loads the project AGENTS.md, so it shares the Codex entry point.
ENTRY_POINTS = {"claude": "CLAUDE.md", "codex": "AGENTS.md",
                "copilot": ".github/copilot-instructions.md", "kiro": "AGENTS.md"}
START = "<!-- aiscb managed policy -->"
END = "<!-- /aiscb managed policy -->"


def entry_path(root, name):
    if Path(name).is_absolute():
        return loader.safe_path(Path(Path(name).anchor), str(Path(name)).lstrip("/"))
    return loader.safe_path(root, name)


def installation_record(root, entry_points=None):
    entry_points = entry_points or ENTRY_POINTS
    record = json.loads(loader.read(loader.safe_path(root, ".aiscb/installation.json")),
                        object_pairs_hook=loader.pairs)
    if (not isinstance(record, dict) or set(record) != {"digest", "modular", "entries"}
            or not isinstance(record["digest"], str)
            or not loader.DIGEST.fullmatch(record["digest"])
            or type(record["modular"]) is not bool
            or not isinstance(record["entries"], dict) or not record["entries"]
            or any(rel not in entry_points.values() or not isinstance(digest, str)
                   or not loader.DIGEST.fullmatch(digest)
                   for rel, digest in record["entries"].items())):
        raise ValueError("invalid local installation record")
    return record


def official():
    catalog, artifacts, _ = build_baseline.validate(ROOT / "baseline")
    files = {}
    for entry, raw in artifacts:
        if entry["size"] != len(raw) or entry["sha256"] != loader.digest(raw):
            raise ValueError("stale source metadata; run build_baseline.py --write")
        files[entry["file"]] = raw
    modules = [{"id": m["id"], "artifact": m["file"], "trigger": m["trigger"],
                "paths": m["paths"], "requires": m["requires"], "blueprints": []}
               for m in catalog["modules"]]
    return catalog["baseline_id"], "aiscb-core.md", None, modules, files


def organization(bundle, expected):
    raw = loader.read(bundle / "manifest.json")
    if not expected or loader.digest(raw) != expected:
        raise ValueError("organization manifest does not match the trusted digest")
    manifest = json.loads(raw, object_pairs_hook=loader.pairs)
    if set(manifest) != {"bundle", "overlay", "aiscb", "aiscb_sha256", "release_dir", "files"}:
        raise ValueError("invalid organization manifest")
    if manifest["aiscb"] != build_baseline.BASELINE_ID:
        raise ValueError("organization package uses an incompatible aiscb release")
    files = {}
    if not isinstance(manifest["files"], dict) or len(manifest["files"]) > 256:
        raise ValueError("invalid organization file inventory")
    for name, entry in manifest["files"].items():
        content = loader.read(loader.safe_path(bundle, name))
        if (not isinstance(entry, dict) or set(entry) != {"size", "sha256"}
                or type(entry["size"]) is not int
                or entry["size"] != len(content) or entry["sha256"] != loader.digest(content)):
            raise ValueError(f"organization artifact mismatch: {name}")
        files[name] = content
    catalog = json.loads(files["catalog.json"], object_pairs_hook=loader.pairs)
    if (set(catalog) != {"schema", "release_set", "modules"} or catalog["schema"] != 1
            or catalog["release_set"] != {"aiscb": manifest["aiscb"],
                                          "organization": manifest["overlay"]}):
        raise ValueError("organization catalog release mismatch")
    overlay_text = files["overlay.md"].decode("utf-8")
    if (f"`baseline-id: {manifest['overlay']}`" not in overlay_text
            or f"Extends aiscb (`{manifest['aiscb']}`)" not in overlay_text
            or manifest["bundle"] != manifest["overlay"]):
        raise ValueError("organization overlay release mismatch")
    namespaces = set(re.findall(r"`([a-z][a-z0-9-]*):\*`", overlay_text)) - {"aiscb"}
    for module in catalog["modules"]:
        publisher = module["id"].split(":", 1)[0]
        if publisher != "aiscb" and publisher not in namespaces:
            raise ValueError("organization namespace is not declared by the overlay")
        if module["publisher"] != publisher:
            raise ValueError("organization module publisher mismatch")
        version = (manifest["aiscb"] if publisher == "aiscb" else manifest["overlay"]).rsplit("-", 1)[-1]
        if module["version"] != version:
            raise ValueError("organization module version mismatch")
    # Revalidate official sources with the same validator used by the repository.
    with tempfile.TemporaryDirectory(prefix="aiscb-org-verify-") as tmp:
        source = Path(tmp)
        upstream = files["aiscb-catalog.json"]
        if loader.digest(upstream) != manifest["aiscb_sha256"]:
            raise ValueError("upstream catalog digest mismatch")
        original = json.loads(upstream, object_pairs_hook=loader.pairs)
        (source / "catalog.json").write_bytes(upstream)
        for entry in [original["core"], *original["modules"]]:
            path = loader.safe_path(source, entry["file"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(files[entry["file"]])
        _, artifacts, _ = build_baseline.validate(source)
        for entry, content in artifacts:
            if entry["size"] != len(content) or entry["sha256"] != loader.digest(content):
                raise ValueError("organization package altered an official module")
    modules = [{key: m[key] for key in
                ("id", "artifact", "trigger", "paths", "requires", "blueprints")}
               for m in catalog["modules"]]
    official_ids = {m["id"] for m in original["modules"]}
    if {m["id"] for m in modules if m["id"].startswith("aiscb:")} != official_ids:
        raise ValueError("organization catalog changes the official inventory")
    for upstream_entry in original["modules"]:
        merged = next(m for m in modules if m["id"] == upstream_entry["id"])
        if any(merged[key] != upstream_entry[key] for key in ("trigger", "paths", "requires")):
            raise ValueError("organization catalog changes official routing")
        if merged["artifact"] != upstream_entry["file"]:
            raise ValueError("organization catalog substitutes an official artifact")
    used = {"aiscb-core.md", "overlay.md"}
    for m in modules:
        used.add(m["artifact"])
        used.update(m["blueprints"])
    selected = {name: files[name] for name in used}
    # Built imports are replaced by the installed core; blueprints are returned
    # by the loader together with their module, so no source-machine path is used.
    for name, content in selected.items():
        if name.endswith(".md"):
            text = content.decode().replace(manifest["release_dir"] + "/", "")
            if name == "overlay.md":
                text = text.removeprefix("@aiscb-core.md\n\n")
            selected[name] = text.encode()
    return manifest["bundle"], "aiscb-core.md", "overlay.md", modules, selected


def atomic(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".aiscb-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def install(tools, root, *, modular=True, bundle=None, expected=None,
            entry_points=None, prepared=None):
    entry_points = entry_points or ENTRY_POINTS
    prepared = prepared or {}
    if root == Path(root.anchor) or not root.is_dir():
        raise ValueError("target must be an existing non-root project directory")
    if any(character in str(root) for character in "`\n\r"):
        raise ValueError("project path cannot contain Markdown delimiters or line breaks")
    data = organization(bundle, expected) if bundle else official()
    release, core, overlay, modules, files = data
    files["policy_loader.py"] = (ROOT / "scripts/policy_loader.py").read_bytes()
    package = {"schema": 1, "release": release, "core": core, "overlay": overlay,
               "modules": modules, "files": {name: {"size": len(raw), "sha256": loader.digest(raw)}
                                              for name, raw in sorted(files.items())}}
    manifest = (json.dumps(package, indent=2) + "\n").encode()
    fingerprint = loader.digest(manifest)
    storage = loader.safe_path(root, ".aiscb")
    record_path = loader.safe_path(root, ".aiscb/installation.json")
    previous = installation_record(root, entry_points) if record_path.exists() else {}
    if previous:
        status(root, entry_points)
        # One record describes one release/format for every managed entry point.
        tools = list(dict.fromkeys([*tools, *(tool for tool, rel in entry_points.items()
                                             if rel in previous["entries"])]))
    destination = loader.safe_path(root, f".aiscb/releases/{fingerprint}")
    with tempfile.TemporaryDirectory(prefix="aiscb-policy-") as tmp:
        stage = Path(tmp)
        for name, raw in files.items():
            path = loader.safe_path(stage, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        (stage / "policy.json").write_bytes(manifest)
        _, contents, inventory = loader.load_package(stage, fingerprint)
        initial = contents[core].rstrip() + "\n"
        if overlay:
            initial += "\n" + contents[overlay].rstrip() + "\n"
        if modular:
            command = shlex.join(["python3", str(destination / "policy_loader.py"), "--digest", fingerprint])
            initial += ("\n## Installed module adapter\n\n"
                        f"Installation mode: modular. Source: {destination}. Release: {release}.\n"
                        "The catalog below lists available modules, not loaded bodies.\n"
                        f"Load selected IDs with `{command} MODULE_ID [MODULE_ID ...]`.\n"
                        "The loader verifies full bodies and includes dependencies and blueprint values. "
                        "Use this loader before affected work and again after context loss; "
                        "if unavailable, stop affected work. Do not fetch or read substitute policy.\n\n")
            for entry in modules:
                initial += f"- `{entry['id']}`: {entry['trigger']}"
                if entry["paths"]:
                    initial += "; additional paths: " + ", ".join(entry["paths"])
                initial += "\n"
        else:
            initial += "\n" + loader.render(stage, fingerprint, list(inventory))
            initial += "\n\nInstallation mode: complete. All configured modules and blueprint values are loaded above.\n"
        block = START + "\n" + initial + "\n" + END
        edits = dict(prepared)
        records = dict(previous.get("entries", {}))
        written = set()
        for tool in tools:
            rel = entry_points[tool]
            if rel in written:
                continue  # Tools sharing an entry point get one block.
            written.add(rel)
            path = Path(rel) if Path(rel).is_absolute() else root / rel
            if path in prepared:
                loader.safe_path(Path(path.anchor), str(path.parent).lstrip("/"))
            # A migration may replace a verified managed symlink without following it.
            if path not in prepared:
                path = entry_path(root, rel)
            old = (prepared[path].decode() if path in prepared else
                   loader.read(path).decode() if path.exists() else "")
            if START in old or END in old:
                if old.count(START) != 1 or old.count(END) != 1:
                    raise ValueError(f"invalid managed markers in {rel}")
                start, end = old.index(START), old.index(END) + len(END)
                current = old[start:end]
                if end < start or records.get(rel) != loader.digest(current.encode()):
                    raise ValueError(f"modified or unowned policy block in {rel}")
                outside = old[:start] + old[end:]
                if "module-id:" in outside or "secure-coding-baseline.md" in outside:
                    raise ValueError(f"additional baseline outside managed block in {rel}")
                new = old[:start] + block + old[end:]
            else:
                if "baseline-id:" in old or "secure-coding-baseline.md" in old:
                    raise ValueError(f"existing baseline in {rel}; remove its old integration before switching")
                new = old + ("\n\n" if old else "") + block + "\n"
            edits[path] = new.encode()
            records[rel] = loader.digest(block.encode())
        if destination.exists():
            loader.load_package(destination, fingerprint)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=destination.parent))
            try:
                shutil.copytree(stage, staging, dirs_exist_ok=True)
                loader.load_package(staging, fingerprint)
                os.rename(staging, destination)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        for path, content in edits.items():
            atomic(path, content)
        atomic(record_path, (json.dumps({"digest": fingerprint, "modular": modular,
                                        "entries": records}, indent=2) + "\n").encode())
    messages = [f"Installed {release} for {', '.join(tools)} ({'modular' if modular else 'complete'}).",
                "Start new sessions; retained release snapshots keep existing loader references stable."]
    if "copilot" in tools:
        messages.append("Copilot: verify the exact CLI/IDE/cloud surface and instruction limits; "
                        "modular mode needs permitted Python command execution. File installation is not loading evidence.")
    if "kiro" in tools:
        messages.append("Kiro: modular mode needs approved shell execution of the loader; "
                        "verify with `aiscb?` in a new session.")
    return messages


def status(root, entry_points=None):
    record = installation_record(root, entry_points)
    fingerprint = record["digest"]
    if not loader.DIGEST.fullmatch(fingerprint):
        raise ValueError("invalid installed digest")
    loader.load_package(root / ".aiscb/releases" / fingerprint, fingerprint)
    for rel, expected in record["entries"].items():
        text = loader.read(entry_path(root, rel)).decode()
        if text.count(START) != 1 or text.count(END) != 1:
            raise ValueError(f"missing managed block in {rel}")
        block = text[text.index(START):text.index(END) + len(END)]
        if loader.digest(block.encode()) != expected:
            raise ValueError(f"modified managed block in {rel}")
    return "Local policy and tool entry points match their recorded digests."


def uninstall(root, entry_points=None):
    status(root, entry_points)
    record = installation_record(root, entry_points)
    for rel in record["entries"]:
        path = entry_path(root, rel)
        text = path.read_text()
        start, end = text.index(START), text.index(END) + len(END)
        atomic(path, (text[:start] + text[end:]).encode())
    (root / ".aiscb/installation.json").unlink()
    return "Removed managed instruction blocks; release snapshots retained in .aiscb/releases."
