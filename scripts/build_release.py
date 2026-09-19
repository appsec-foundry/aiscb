#!/usr/bin/env python3
"""Stage an immutable complete bundle without signing or publishing it."""

import argparse
import os
import tempfile
from pathlib import Path

import build_baseline as build
import bundle_manifest
import install


def stage(version, revision, root=build.ROOT):
    if version != build.VERSION or not revision.isdecimal() or int(revision) < 1 or str(int(revision)) != revision:
        raise ValueError("explicit current version and positive canonical bundle revision required")
    catalog, artifacts, complete = build.validate(root / "baseline")
    if (root / "baseline/catalog.json").read_bytes() != build.render_catalog(catalog, artifacts):
        raise ValueError("stale catalog metadata")
    parent = root / "dist" / f"aiscb-{version}"
    target = parent / f"bundle-{revision}"
    if target.exists() or target.is_symlink():
        raise ValueError("release staging directory already exists; never overwrite it")
    for path in (root / "dist", parent):
        if path.is_symlink():
            raise ValueError("symlink in release staging path")
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".staging-", dir=parent) as tmp:
        work = Path(tmp) / "bundle"
        (work / "scripts").mkdir(parents=True)
        (work / install.BASELINE).write_bytes(complete)
        for name in install.BUNDLE_FILES:
            if name != install.BASELINE:
                (work / name).write_bytes(install.read_limited(root / name, install.BUNDLE_FILES[name]))
        bundle_manifest.write_manifest(work)
        template = (root / "scripts/release-setup.sh.in").read_text()
        replacements = {"@RELEASE@": f"aiscb-bundle-{version}-{revision}"}
        for marker, name in (("@BASELINE_SHA@", install.BASELINE),
                             ("@INSTALLER_SHA@", "scripts/install.py"),
                             ("@HELPER_SHA@", "scripts/show_baseline_version.py")):
            replacements[marker] = install.hashlib.sha256((work / name).read_bytes()).hexdigest()
        for marker, value in replacements.items():
            template = template.replace(marker, value)
        (work / "setup.sh").write_text(template)
        os.rename(work, target)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    try:
        print(stage(args.version, args.revision))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Release staging refused: {exc}\n")


if __name__ == "__main__":
    main()
