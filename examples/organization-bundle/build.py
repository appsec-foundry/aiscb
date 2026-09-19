#!/usr/bin/env python3
"""Assemble one immutable release from organization and approved aiscb modules.

The build validates both catalogs, merges every namespaced module into one flat
release directory, generates the adapters each tool reads, and writes a
manifest that records every file with its size and SHA-256.

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

sys.path.append(str(Path(__file__).resolve().parents[2] / "scripts"))
import build_baseline
from policy_loader import closure

HERE = Path(__file__).resolve().parent
PLACEHOLDER = "<bundle-dir>"
IMPORT_MARKER = f"@{PLACEHOLDER}/aiscb-core.md\n\n"
ID_RE = re.compile(r"`baseline-id: ([a-z][a-z0-9-]*-\d+\.\d+\.\d+)`")
EXTENDS_RE = re.compile(r"Extends aiscb \(`(aiscb-\d+\.\d+\.\d+)`\)")
RULE_RE = re.compile(r"\[(aiscb-[A-Z0-9]+-\d{3})\]")
PACK_ID_RE = re.compile(r"^[a-z][a-z0-9-]*:[a-z][a-z0-9-]*$")
REQUIREMENT_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+-\d{3}$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_SOURCE_BYTES = 256 * 1024

BLUEPRINT_KEYS = {"version", "sso", "session_cookie", "headers", "audit_events"}
BLUEPRINT_MAJOR = 1
PACK_KEYS = {"id", "file", "owner", "source", "trigger", "paths", "blueprints",
             "requirements"}
AISCB_TOP_KEYS = {"schema", "baseline_id", "core", "modules"}
AISCB_CORE_KEYS = {"file", "rules", "size", "sha256"}
AISCB_MODULE_KEYS = {
    "id", "publisher", "version", "file", "trigger", "paths", "requires",
    "rules", "size", "sha256",
}

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


def verified_artifact(root: Path, entry: dict, expected_prefix: str) -> tuple[str, bytes]:
    rel = entry.get("file")
    if (not isinstance(rel, str) or Path(rel).is_absolute() or ".." in Path(rel).parts
            or (expected_prefix and not rel.startswith(expected_prefix))):
        raise BuildError(f"unsafe aiscb artifact path {rel!r}")
    raw = read_bytes(root / rel)
    if (entry.get("size") != len(raw) or not isinstance(entry.get("sha256"), str)
            or not SHA256_RE.fullmatch(entry["sha256"])
            or entry["sha256"] != sha256(raw)):
        raise BuildError(f"aiscb artifact metadata does not match {rel}")
    return rel, raw


def load_aiscb(root: Path, approved_digest: str | None = None) -> dict:
    """Load one verified modular aiscb source tree."""
    if not root.is_dir():
        raise BuildError("--aiscb must name the modular baseline directory")
    catalog_raw = read_bytes(root / "catalog.json")
    if approved_digest and sha256(catalog_raw) != approved_digest.lower():
        raise BuildError("the aiscb catalog does not match the approved digest")
    try:
        _, artifacts, _ = build_baseline.validate(root)
        for entry, raw in artifacts:
            if entry["size"] != len(raw) or entry["sha256"] != sha256(raw):
                raise BuildError("aiscb artifact metadata does not match its source")
    except (build_baseline.Invalid, OSError, TypeError, KeyError) as exc:
        raise BuildError(str(exc)) from exc
    try:
        catalog = json.loads(catalog_raw)
    except ValueError as exc:
        raise BuildError(f"aiscb catalog is not valid JSON: {exc}") from None
    if not isinstance(catalog, dict) or set(catalog) != AISCB_TOP_KEYS:
        raise BuildError(f"aiscb catalog needs exactly {sorted(AISCB_TOP_KEYS)}")
    if catalog["schema"] != 1 or not isinstance(catalog["modules"], list):
        raise BuildError("unsupported aiscb catalog schema")
    core = catalog["core"]
    if not isinstance(core, dict) or set(core) != AISCB_CORE_KEYS:
        raise BuildError(f"aiscb core needs exactly {sorted(AISCB_CORE_KEYS)}")
    core_rel, core_raw = verified_artifact(root, core, "")
    if core_rel != "aiscb-core.md":
        raise BuildError("aiscb core must be aiscb-core.md")
    core_text = core_raw.decode("utf-8")
    baseline_id = single(ID_RE, core_text, "aiscb baseline-id")
    if catalog["baseline_id"] != baseline_id:
        raise BuildError("aiscb catalog and core baseline IDs differ")

    ids: set[str] = set()
    files: list[tuple[str, bytes]] = [(core_rel, core_raw)]
    modules: list[dict] = []
    all_rules = set(RULE_RE.findall(core_text))
    for module in catalog["modules"]:
        if not isinstance(module, dict) or set(module) != AISCB_MODULE_KEYS:
            raise BuildError(f"aiscb module needs exactly {sorted(AISCB_MODULE_KEYS)}")
        module_id = module["id"]
        if (not isinstance(module_id, str) or not PACK_ID_RE.fullmatch(module_id)
                or not module_id.startswith("aiscb:") or module_id in ids):
            raise BuildError(f"invalid or duplicate aiscb module ID {module_id!r}")
        ids.add(module_id)
        rel, raw = verified_artifact(root, module, "modules/")
        text = raw.decode("utf-8")
        if f"`module-id: {module_id}`" not in text:
            raise BuildError(f"aiscb module body does not declare {module_id}")
        trigger = module["trigger"]
        if not isinstance(trigger, str) or not trigger.strip() or "\n" in trigger:
            raise BuildError(f"aiscb module {module_id} needs one semantic trigger")
        rules = set(RULE_RE.findall(text))
        if rules != set(module["rules"]) or all_rules.intersection(rules):
            raise BuildError(f"aiscb module rule inventory is invalid for {module_id}")
        all_rules.update(rules)
        files.append((rel, raw))
        modules.append(module)
    return {"id": baseline_id, "catalog": catalog, "catalog_raw": catalog_raw,
            "catalog_sha256": sha256(catalog_raw), "core": core_text,
            "files": files, "modules": modules, "rules": all_rules}


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
        if f"`module-id: {pack_id}`" not in text:
            raise BuildError(f"pack {pack_id} does not declare its module-id")
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
    aiscb = load_aiscb(aiscb_path, aiscb_sha256)
    aiscb_id = aiscb["id"]

    overlay = read_text(source / "overlay.md")
    if not overlay.startswith(IMPORT_MARKER):
        raise BuildError("overlay.md must start with the aiscb import marker")
    overlay_id = single(ID_RE, overlay, "overlay baseline-id")
    extends = single(EXTENDS_RE, overlay, "'Extends aiscb' statement")
    if extends != aiscb_id:
        raise BuildError(f"overlay extends {extends} but the supplied file is {aiscb_id}")

    organization = load_catalog(source, aiscb["rules"])
    seen_ids = {m["id"] for m in aiscb["modules"]}
    seen_paths = {m["file"] for m in aiscb["modules"]}
    for pack in organization["packs"]:
        target = "modules/" + pack["id"].replace(":", "-") + ".md"
        if pack["id"].startswith("aiscb:") or pack["id"] in seen_ids or target in seen_paths:
            raise BuildError("organization namespace or artifact collides with another module")
        seen_ids.add(pack["id"])
        seen_paths.add(target)
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

    put("aiscb-core.md", aiscb["files"][0][1])
    for rel, raw in aiscb["files"][1:]:
        put(f"modules/{Path(rel).name}", raw)
    put("overlay.md", fill(overlay).encode("utf-8"))
    put("aiscb-catalog.json", aiscb["catalog_raw"])

    merged_modules = []
    for module in aiscb["modules"]:
        merged_modules.append({
            "id": module["id"],
            "publisher": "aiscb",
            "version": module["version"],
            "artifact": f"modules/{Path(module['file']).name}",
            "trigger": module["trigger"],
            "paths": module["paths"],
            "requires": module["requires"],
            "blueprints": [],
            "rules": module["rules"],
        })
    for pack in organization["packs"]:
        module_name = pack["id"].replace(":", "-") + ".md"
        body = fill(read_text(source / pack["file"])).encode("utf-8")
        put(f"modules/{module_name}", body)
        for blueprint in pack["blueprints"]:
            put(blueprint, read_bytes(source / blueprint))
        merged_modules.append({
            "id": pack["id"],
            "publisher": pack["id"].split(":", 1)[0],
            "version": overlay_id.rsplit("-", 1)[-1],
            "artifact": f"modules/{module_name}",
            "trigger": pack["trigger"],
            "paths": pack["paths"],
            "requires": [],
            "blueprints": pack["blueprints"],
            "rules": sorted(pack["requirements"]),
            "owner": pack["owner"],
            "source": pack["source"],
            "mappings": pack["requirements"],
        })

    merged_catalog = {
        "schema": 1,
        "release_set": {"aiscb": aiscb_id, "organization": overlay_id},
        "modules": merged_modules,
    }
    put("catalog.json", (json.dumps(merged_catalog, indent=2) + "\n").encode("utf-8"))

    body = fill(overlay[len(IMPORT_MARKER):])
    triggers = {
        module["id"]: module["trigger"] + (
            "; additional paths: " + ", ".join(module["paths"]) if module["paths"] else ""
        )
        for module in merged_modules
    }
    discovery = "## Configured Module Catalog\n\n" + "\n".join(
        f"- `{module['id']}` — {triggers[module['id']]}"
        for module in merged_modules
    ) + "\n"
    combined = aiscb["core"].rstrip("\n") + "\n\n" + body.rstrip("\n") + "\n\n" + discovery
    for tool, (name, follows_import) in ADAPTERS.items():
        if follows_import:
            text = f"@{release_dir}/aiscb-core.md\n\n{body.rstrip()}\n\n{discovery}"
        else:
            text = combined
        put(f"adapters/{tool}/{name}", text.encode("utf-8"))
        for module in merged_modules:
            skill_name = module["id"].replace(":", "-")
            description = json.dumps(f"{module['id']}: {triggers[module['id']]}")
            inventory = {entry["id"]: entry for entry in merged_modules}
            selected = [inventory[module_id] for module_id in closure(inventory, [module["id"]])]
            module_body = "\n\n".join(read_text(out / entry["artifact"]).rstrip()
                                         for entry in selected) + "\n"
            for blueprint in sorted({p for entry in selected for p in entry["blueprints"]}):
                module_body += "\nBlueprint values: " + blueprint + "\n" + read_text(out / blueprint)
            skill = (f"---\nname: {skill_name}\ndescription: {description}\n"
                     f"---\n\n{module_body}")
            put(f"adapters/{tool}/skills/{skill_name}/SKILL.md",
                skill.encode("utf-8"))
    # The gateway has no loader: ship complete policy, not unresolved module references.
    eager = aiscb["core"].rstrip() + "\n\n" + body.rstrip() + "\n\n"
    eager += "\n\n".join(read_text(out / m["artifact"]).rstrip() for m in merged_modules)
    for blueprint in sorted({p for m in merged_modules for p in m["blueprints"]}):
        eager += "\n\nBlueprint values: " + blueprint + "\n" + read_text(out / blueprint)
    eager += "\n"
    put("complete-policy.md", eager.encode("utf-8"))
    put("adapters/gateway/system-block.md", eager.encode("utf-8"))

    manifest = {
        "bundle": overlay_id,
        "overlay": overlay_id,
        "aiscb": aiscb_id,
        "aiscb_sha256": aiscb["catalog_sha256"],
        "release_dir": str(release_dir),
        "files": dict(sorted(files.items())),
    }
    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8") + b"\n"
    (out / "manifest.json").write_bytes(manifest_bytes)
    return manifest, sha256(manifest_bytes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--aiscb", required=True, type=Path,
                        help="the approved modular aiscb baseline directory")
    parser.add_argument("--aiscb-sha256", help="digest the aiscb catalog must match")
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
