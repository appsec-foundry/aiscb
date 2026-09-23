#!/usr/bin/env python3
"""Verified source loader for work in this repository; needs no dist build."""

import argparse
import sys

import build_baseline as build
from policy_loader import closure


def render(selected, *, catalog_only=False):
    catalog, artifacts, _ = build.validate()
    if build.CATALOG.read_bytes() != build.render_catalog(catalog, artifacts):
        raise ValueError("stale catalog metadata; regenerate after approved source edits")
    modules = {entry["id"]: entry for entry in catalog["modules"]}
    if catalog_only:
        return "\n".join(f"{m['id']}: {m['trigger']} (requires: {', '.join(m['requires']) or 'none'})"
                         for m in modules.values())
    bodies = {entry["file"]: raw for entry, raw in artifacts}
    # Resolve everything before emitting anything; arbitrary paths/URLs refuse.
    return "\n\n".join(
        f"Verified {name}; {catalog['baseline_id']}\n\n"
        + bodies[modules[name]["file"]].decode("utf-8")
        for name in closure(modules, selected))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", action="store_true")
    parser.add_argument("ids", nargs="*")
    args = parser.parse_args()
    if args.catalog == bool(args.ids):
        parser.error("choose --catalog or one or more module IDs")
    try:
        output = render(args.ids, catalog_only=args.catalog)
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        print(f"Repository policy refused: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
