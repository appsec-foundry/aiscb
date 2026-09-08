#!/usr/bin/env python3
"""Assemble one immutable release from this directory and an approved aiscb file.

The build copies the sources, validates the catalog and blueprints, generates
the adapters each tool reads, and writes a manifest that records every file
with its size and SHA-256. It refuses to build when the overlay names an aiscb
release other than the one supplied, when a blueprint has unknown fields or a
version that disagrees with its path, or when the catalog points at a rule,
pack, or blueprint that does not exist.

Bundle paths in the sources are the placeholder ``<bundle-dir>``. The build
replaces it with the versioned directory the release will be installed to, so
the install root has to be known here and must match at install time.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLACEHOLDER = "<bundle-dir>"
IMPORT_MARKER = f"@{PLACEHOLDER}/secure-coding-baseline.md\n\n"
ID_RE = re.compile(r"`baseline-id: ([a-z][a-z0-9-]*-\d+\.\d+\.\d+)`")
EXTENDS_RE = re.compile(r"Extends aiscb \(`(aiscb-\d+\.\d+\.\d+)`\)")
RULE_RE = re.compile(r"\[(aiscb-[A-Z]+-\d{3})\]")
PACK_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
REQUIREMENT_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+-\d{3}$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
MAX_SOURCE_BYTES = 256 * 1024

BLUEPRINT_KEYS = {"version", "sso", "session_cookie", "headers", "audit_events"}
BLUEPRINT_MAJOR = 1
PACK_KEYS = {"id", "file", "owner", "source", "trigger", "paths", "blueprints",
             "requirements"}

# tool -> (instruction file the tool reads, whether it can follow the import)
ADAPTERS = {
    "claude-code": ("CLAUDE.md", True),
    "codex": ("AGENTS.md", False),
    "copilot": ("copilot-instructions.md", False),
}


class BuildError(Exception):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise BuildError(f"{path} does not exist")
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise BuildError(f"{path.name} exceeds {MAX_SOURCE_BYTES} bytes")
    return path.read_bytes()


def read_text(path: Path) -> str:
    return read_bytes(path).decode("utf-8")


def single(pattern: re.Pattern, text: str, what: str) -> str:
    found = pattern.findall(text)
    if len(found) != 1:
        raise BuildError(f"expected exactly one {what}, found {len(found)}")
    return found[0]


def validate_blueprint(source: Path, rel: str) -> None:
    path = source / rel
    if not rel.startswith("blueprints/") or path.suffix != ".json":
        raise BuildError(f"blueprint {rel} must be a JSON file under blueprints/")
    try:
        data = json.loads(read_text(path))
    except ValueError as exc:
        raise BuildError(f"blueprint {rel} is not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise BuildError(f"blueprint {rel} must be a JSON object")
    unknown = sorted(set(data) - BLUEPRINT_KEYS)
    missing = sorted(BLUEPRINT_KEYS - set(data))
    if unknown or missing:
        raise BuildError(f"blueprint {rel}: unknown fields {unknown}, missing {missing}")
    version = data["version"]
    if not isinstance(version, str) or not SEMVER_RE.match(version):
        raise BuildError(f"blueprint {rel}: version must be MAJOR.MINOR.PATCH")
    if version != path.stem:
        raise BuildError(f"blueprint {rel}: version {version} does not match the file name")
    if int(version.split(".")[0]) != BLUEPRINT_MAJOR:
        raise BuildError(f"blueprint {rel}: schema major {BLUEPRINT_MAJOR} required")


def load_catalog(source: Path, aiscb_rules: set[str]) -> dict:
    try:
        data = json.loads(read_text(source / "catalog.json"))
    except ValueError as exc:
        raise BuildError(f"catalog.json is not valid JSON: {exc}") from None
    if not isinstance(data, dict) or set(data) != {"packs"}:
        raise BuildError("catalog.json must contain exactly the key 'packs'")
    packs = data["packs"]
    if not isinstance(packs, list) or not packs:
        raise BuildError("catalog.json must list at least one pack")
    ids: set[str] = set()
    requirement_ids: set[str] = set()
    listed_files: set[str] = set()
    for pack in packs:
        if not isinstance(pack, dict) or set(pack) != PACK_KEYS:
            raise BuildError(f"every pack needs exactly the keys {sorted(PACK_KEYS)}")
        pack_id = pack["id"]
        if not isinstance(pack_id, str) or not PACK_ID_RE.match(pack_id) or pack_id in ids:
            raise BuildError(f"pack id {pack_id!r} is invalid or duplicated")
        ids.add(pack_id)
        rel = pack["file"]
        if not isinstance(rel, str) or not rel.startswith("packs/") or "/" in rel[6:]:
            raise BuildError(f"pack {pack_id}: file must sit directly under packs/")
        text = read_text(source / rel)
        listed_files.add(rel)
        trigger = pack["trigger"]
        if (not isinstance(trigger, str) or not trigger.strip() or len(trigger) > 200
                or ":" in trigger or "\n" in trigger):
            raise BuildError(f"pack {pack_id}: trigger must be one short line without ':'")
        for key in ("owner", "source"):
            if not isinstance(pack[key], str) or not pack[key].strip():
                raise BuildError(f"pack {pack_id}: {key} must be a non-empty string")
        for key in ("paths", "blueprints"):
            value = pack[key]
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise BuildError(f"pack {pack_id}: {key} must be a list of strings")
        for blueprint in pack["blueprints"]:
            validate_blueprint(source, blueprint)
        requirements = pack["requirements"]
        if not isinstance(requirements, dict) or not requirements:
            raise BuildError(f"pack {pack_id}: requirements must be a non-empty object")
        for req_id, mapping in requirements.items():
            if not REQUIREMENT_RE.match(req_id) or req_id in requirement_ids:
                raise BuildError(f"requirement id {req_id!r} is invalid or duplicated")
            requirement_ids.add(req_id)
            if f"[{req_id}]" not in text:
                raise BuildError(f"pack {pack_id} does not define {req_id}")
            if mapping == {"organization": True}:
                continue
            if (not isinstance(mapping, dict) or set(mapping) != {"narrows"}
                    or not isinstance(mapping["narrows"], list) or not mapping["narrows"]):
                raise BuildError(f"{req_id}: map to {{\"narrows\": [...]}} or {{\"organization\": true}}")
            unknown = sorted(set(mapping["narrows"]) - aiscb_rules)
            if unknown:
                raise BuildError(f"{req_id} narrows unknown aiscb rules {unknown}")
    on_disk = {f"packs/{p.name}" for p in (source / "packs").glob("*.md")}
    stray = sorted(on_disk - listed_files)
    if stray:
        raise BuildError(f"packs without a catalog entry: {stray}")
    return data


def build(source: Path, aiscb_path: Path, out: Path, install_root: Path,
          aiscb_sha256: str | None = None) -> tuple[dict, str]:
    aiscb_bytes = read_bytes(aiscb_path)
    if aiscb_sha256 and sha256(aiscb_bytes) != aiscb_sha256.lower():
        raise BuildError("the aiscb file does not match the approved digest")
    aiscb_text = aiscb_bytes.decode("utf-8")
    aiscb_id = single(ID_RE, aiscb_text, "aiscb baseline-id")

    overlay = read_text(source / "overlay.md")
    if not overlay.startswith(IMPORT_MARKER):
        raise BuildError("overlay.md must start with the aiscb import marker")
    overlay_id = single(ID_RE, overlay, "overlay baseline-id")
    extends = single(EXTENDS_RE, overlay, "'Extends aiscb' statement")
    if extends != aiscb_id:
        raise BuildError(f"overlay extends {extends} but the supplied file is {aiscb_id}")

    catalog = load_catalog(source, set(RULE_RE.findall(aiscb_text)))
    release_dir = (install_root / "releases" / overlay_id).resolve()

    if out.exists() and any(out.iterdir()):
        raise BuildError(f"output directory {out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict[str, object]] = {}

    def put(rel: str, data: bytes) -> None:
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files[rel] = {"size": len(data), "sha256": sha256(data)}

    def fill(text: str) -> str:
        return text.replace(PLACEHOLDER, str(release_dir))

    put("secure-coding-baseline.md", aiscb_bytes)
    put("overlay.md", fill(overlay).encode("utf-8"))
    put("catalog.json", read_bytes(source / "catalog.json"))
    for pack in catalog["packs"]:
        put(pack["file"], fill(read_text(source / pack["file"])).encode("utf-8"))
        for blueprint in pack["blueprints"]:
            put(blueprint, read_bytes(source / blueprint))

    body = fill(overlay[len(IMPORT_MARKER):])
    combined = aiscb_text.rstrip("\n") + "\n\n" + body
    for tool, (name, follows_import) in ADAPTERS.items():
        if follows_import:
            text = f"@{release_dir}/secure-coding-baseline.md\n\n{body}"
        else:
            text = combined
        put(f"adapters/{tool}/{name}", text.encode("utf-8"))
        for pack in catalog["packs"]:
            skill = (f"---\nname: {pack['id']}\ndescription: {pack['trigger']}\n---\n\n"
                     + fill(read_text(source / pack["file"])))
            put(f"adapters/{tool}/skills/{pack['id']}/SKILL.md", skill.encode("utf-8"))
    put("adapters/gateway/system-block.md", combined.encode("utf-8"))

    manifest = {
        "bundle": overlay_id,
        "overlay": overlay_id,
        "aiscb": aiscb_id,
        "aiscb_sha256": sha256(aiscb_bytes),
        "release_dir": str(release_dir),
        "files": dict(sorted(files.items())),
    }
    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8") + b"\n"
    (out / "manifest.json").write_bytes(manifest_bytes)
    return manifest, sha256(manifest_bytes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--aiscb", required=True, type=Path,
                        help="the approved secure-coding-baseline.md")
    parser.add_argument("--aiscb-sha256", help="digest the aiscb file must match")
    parser.add_argument("--out", required=True, type=Path, help="empty output directory")
    parser.add_argument("--install-root", type=Path,
                        default=Path.home() / ".local" / "share" / "aiscb",
                        help="root the release will be installed under")
    parser.add_argument("--source", type=Path, default=HERE)
    args = parser.parse_args(argv)
    try:
        manifest, digest = build(args.source, args.aiscb, args.out,
                                 args.install_root.expanduser(), args.aiscb_sha256)
    except (BuildError, OSError, UnicodeDecodeError) as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1
    print(f"bundle:       {manifest['bundle']} (aiscb {manifest['aiscb']})")
    print(f"release dir:  {manifest['release_dir']}")
    print(f"files:        {len(manifest['files'])}")
    print(f"manifest:     {digest}")
    print("Pass the manifest digest to install.py through a channel other than the bundle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
