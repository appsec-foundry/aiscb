#!/usr/bin/env python3
"""Mutation checks for the modular baseline builder."""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "build_baseline", ROOT / "scripts" / "build_baseline.py")
assert SPEC and SPEC.loader
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)

checks = 0


def check(condition: bool, message: str) -> None:
    global checks
    checks += 1
    if not condition:
        raise AssertionError(message)
    print(f"ok   {message}")


@contextmanager
def fixture():
    old = BUILD.SOURCE_ROOT, BUILD.CATALOG, BUILD.EAGER
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shutil.copytree(ROOT / "baseline", root / "baseline")
        (root / "secure-coding-baseline.md").write_bytes(BUILD.validate()[2])
        BUILD.SOURCE_ROOT = root / "baseline"
        BUILD.CATALOG = BUILD.SOURCE_ROOT / "catalog.json"
        BUILD.EAGER = root / "secure-coding-baseline.md"
        try:
            yield root
        finally:
            BUILD.SOURCE_ROOT, BUILD.CATALOG, BUILD.EAGER = old


def catalog() -> dict:
    return json.loads(BUILD.CATALOG.read_text(encoding="utf-8"))


def write_catalog(value: dict) -> None:
    BUILD.CATALOG.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def rejected(change, expected: str) -> bool:
    with fixture() as root:
        change(root)
        try:
            BUILD.stale_outputs()
        except BUILD.Invalid as exc:
            return expected in str(exc)
        return False


check(not BUILD.stale_outputs(), "current modular sources and eager artifact agree")


def duplicate_id(_root: Path) -> None:
    value = catalog()
    value["modules"][1]["id"] = value["modules"][0]["id"]
    write_catalog(value)


check(rejected(duplicate_id, "duplicate module id"), "duplicate module IDs are rejected")


def wrong_version(_root: Path) -> None:
    value = catalog()
    value["modules"][0]["version"] = "0.1.15"
    write_catalog(value)


check(rejected(wrong_version, "incompatible publisher or version"),
      "cross-release modules are rejected")


def unknown_dependency(_root: Path) -> None:
    value = catalog()
    value["modules"][0]["requires"] = ["aiscb:not-present"]
    write_catalog(value)


check(rejected(unknown_dependency, "requires unknown modules"),
      "unknown module dependencies are rejected")


def dependency_cycle(_root: Path) -> None:
    value = catalog()
    first, second = value["modules"][:2]
    first["requires"] = [second["id"]]
    second["requires"] = [first["id"]]
    write_catalog(value)


check(rejected(dependency_cycle, "dependency cycle"),
      "module dependency cycles are rejected")


def repeated_rule(root: Path) -> None:
    target = root / "baseline" / "modules" / "aiscb-data-handling.md"
    target.write_text(target.read_text().replace("aiscb-ERRORS-001",
                                                  "aiscb-AUTH-001", 1))
    value = catalog()
    next(m for m in value["modules"] if m["id"] == "aiscb:data-handling")["rules"][0] = "aiscb-AUTH-001"
    write_catalog(value)


check(rejected(repeated_rule, "more than one artifact"),
      "rule IDs repeated across modules are rejected")


def unlisted_module(root: Path) -> None:
    (root / "baseline" / "modules" / "extra.md").write_text(
        "# Extra\n\n`module-id: aiscb:extra`.\n\n"
        "## Extra\n\n- **[aiscb-EXTRA-001] Extra:** Rule.\n")


check(rejected(unlisted_module, "unlisted"), "unlisted module files are rejected")

with fixture() as root:
    module = root / "baseline" / "modules" / "aiscb-web.md"
    module.write_text(module.read_text() + "\nChanged.\n")
    failures = BUILD.stale_outputs()
    check(any("metadata is stale" in item for item in failures)
          and any("eager artifact" in item for item in failures),
          "changed module bytes make catalog metadata and eager output stale")

with fixture() as root:
    (root / "secure-coding-baseline.md").write_text("changed\n")
    check(BUILD.stale_outputs() == [
        "secure-coding-baseline.md is not the generated eager artifact"],
        "changed eager output is rejected")


def edit_catalog(edit):
    def change(_root: Path) -> None:
        value = catalog()
        edit(value)
        write_catalog(value)
    return change


def edit_file(relative: str, edit):
    def change(root: Path) -> None:
        target = root / "baseline" / relative
        target.write_bytes(edit(target.read_bytes()))
    return change


def raw_catalog(content: str):
    def change(_root: Path) -> None:
        BUILD.CATALOG.write_text(content, encoding="utf-8")
    return change


def module_path(root: Path) -> Path:
    return root / "baseline" / catalog()["modules"][0]["file"]


def symlinked_module(root: Path) -> None:
    target = module_path(root)
    copy = root / "elsewhere.md"
    copy.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(copy)


def missing_module(root: Path) -> None:
    module_path(root).unlink()


def first_module(key: str, value):
    return edit_catalog(lambda c: c["modules"][0].__setitem__(key, value))


FIRST = "modules/aiscb-web.md"
CORE = "aiscb-core.md"
REJECTIONS = [
    (raw_catalog("{"), "cannot read catalog", "unparsable catalog"),
    (raw_catalog('{"schema": 1, "schema": 1}'), "duplicate catalog key", "duplicate catalog keys"),
    (raw_catalog("[]"), "catalog must be an object", "non-object catalog"),
    (edit_catalog(lambda c: c.__setitem__("extra", 1)), "catalog keys must be exactly", "extra catalog key"),
    (edit_catalog(lambda c: c.__setitem__("schema", 2)), "schema 1", "unknown catalog schema"),
    (edit_catalog(lambda c: c.__setitem__("baseline_id", "aiscb-0.0.1")), "schema 1", "foreign baseline ID"),
    (edit_catalog(lambda c: c.__setitem__("core", [])), "core keys must be exactly", "malformed core entry"),
    (edit_catalog(lambda c: c.__setitem__("modules", [])), "non-empty list", "empty module list"),
    (edit_catalog(lambda c: c["core"].__setitem__("file", 7)), "must be a string", "non-string artifact path"),
    (edit_catalog(lambda c: c["core"].__setitem__("file", "../aiscb-core.md")), "unsafe or unexpected", "core path traversal"),
    (first_module("file", "modules/../aiscb-core.md"), "unsafe or unexpected", "module path traversal"),
    (first_module("file", "other/aiscb-web.md"), "unsafe or unexpected", "module outside modules/"),
    (symlinked_module, "contains a symlink", "symlinked module file"),
    (missing_module, "must be a regular file", "missing module file"),
    (edit_file(FIRST, lambda _raw: b""), "invalid size", "empty module file"),
    (edit_file(FIRST, lambda raw: raw + b"\xff\xfe\n"), "not UTF-8", "non-UTF-8 module"),
    (edit_file(FIRST, lambda raw: raw.rstrip(b"\n")), "end with a newline", "missing final newline"),
    (edit_file(CORE, lambda raw: raw + b"`baseline-id: aiscb-0.0.1`\n"), "must declare exactly", "second core baseline ID"),
    (edit_file(CORE, lambda raw: raw + b"- **[aiscb-bad] Bad:** x\n"), "invalid rule-group bullet", "malformed rule bullet"),
    (edit_file(CORE, lambda raw: raw + b"- **[aiscb-ZZZ-001] Extra:** x\n"), "core rule list does not match", "unlisted core rule"),
    (edit_file(FIRST, lambda raw: raw.replace(b"- **[", b"- [", 99)), "no rule groups", "module without rules"),
    (edit_file(FIRST, lambda raw: raw + raw[raw.index(b"- **["):]), "repeats a rule ID", "rule repeated within a module"),
    (edit_catalog(lambda c: c["core"].__setitem__("rules", "x")), "list of non-empty strings", "non-list rule inventory"),
    (edit_catalog(lambda c: c["modules"].__setitem__(0, [])), "keys must be exactly", "non-object module entry"),
    (first_module("id", "Web Module"), "invalid module id", "invalid module ID"),
    (first_module("trigger", " "), "semantic trigger", "blank module trigger"),
    (first_module("paths", [""]), "list of non-empty strings", "empty path pattern"),
    (edit_catalog(lambda c: c["modules"][0].__setitem__("requires", [c["modules"][0]["id"]])),
     "requires itself", "self-dependency"),
    (edit_file(FIRST, lambda raw: raw.replace(b"`module-id: aiscb:web`", b"`module-id: aiscb:other`")),
     "must declare exactly", "module file declaring another ID"),
    (edit_file(FIRST, lambda raw: raw + b"`baseline-id: aiscb-0.0.1`\n"), "declares a baseline ID", "module declaring a baseline ID"),
    (first_module("rules", ["aiscb-WEB-999"]), "rule list does not match", "module rule list mismatch"),
]
for change, expected, name in REJECTIONS:
    check(rejected(change, expected), f"{name} is rejected")


def run_main(*argv: str) -> int:
    import sys
    from contextlib import redirect_stderr, redirect_stdout
    from io import StringIO
    old = sys.argv
    sys.argv = ["build_baseline.py", *argv]
    try:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            return BUILD.main()
    finally:
        sys.argv = old


with fixture() as root:
    old_root = BUILD.ROOT
    BUILD.ROOT = root
    try:
        check(run_main("--check") == 0, "--check accepts current generated outputs")
        module = root / "baseline" / FIRST
        module.write_text(module.read_text() + "\nChanged.\n")
        check(run_main("--check") == 1, "--check fails on stale outputs without writing")
        check(run_main("--write") == 0 and run_main("--check") == 0,
              "--write regenerates catalog metadata and eager output")
        check(BUILD.EAGER.read_bytes() == BUILD.validate()[2],
              "--write stores exactly the validated eager artifact")
        module.write_text("")
        check(run_main("--write") == 1, "--write refuses invalid sources")
    finally:
        BUILD.ROOT = old_root

print(f"modular baseline builder: ok ({checks} checks)")
