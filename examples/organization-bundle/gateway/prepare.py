#!/usr/bin/env python3
"""Prepare a verified policy snapshot for the gateway; print its trusted digest."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import install_policy
import policy_loader


def prepare(out, organization=None, expected=None):
    if out.exists():
        raise ValueError("output must not exist")
    release, core, overlay, modules, files = (
        install_policy.organization(organization, expected)
        if organization
        else install_policy.official()
    )
    package = {
        "schema": 1,
        "release": release,
        "core": core,
        "overlay": overlay,
        "modules": modules,
        "files": {
            name: {"size": len(raw), "sha256": policy_loader.digest(raw)}
            for name, raw in files.items()
        },
    }
    raw = (json.dumps(package, sort_keys=True, indent=2) + "\n").encode()
    out.mkdir(parents=True)
    for name, content in files.items():
        path = policy_loader.safe_path(out, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (out / "policy.json").write_bytes(raw)
    digest = policy_loader.digest(raw)
    policy_loader.load_package(out, digest)
    return digest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--organization", type=Path)
    parser.add_argument("--organization-sha256")
    args = parser.parse_args()
    try:
        if bool(args.organization) != bool(args.organization_sha256):
            raise ValueError(
                "organization package and trusted digest are required together"
            )
        print(prepare(args.out, args.organization, args.organization_sha256))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f"Gateway policy preparation refused: {exc}\n")
