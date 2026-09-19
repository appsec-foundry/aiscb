"""Embed reviewed modular resources in the installer covered by the bundle signature.

The public bundle keeps its three-file contract. No resource is fetched at
runtime, and resources are not another installation-time trust anchor.
"""

import json

import build_baseline as build

HELPERS = ("build_baseline.py", "policy_loader.py", "install_policy.py",
           "policy_setup.py", "bundle_resources.py")
MARKER = "EMBEDDED_POLICY = None  # release resource slot"


def installer_bytes(legacy, root=None):
    if legacy.EMBEDDED_POLICY is not None and root is None:
        return legacy.read_limited(legacy.INSTALLER_SOURCE, legacy.MAX_INSTALLER_BYTES)
    root = root or build.ROOT
    catalog, artifacts, _ = build.validate(root / "baseline")
    catalog_bytes = (root / "baseline/catalog.json").read_bytes()
    if catalog_bytes != build.render_catalog(catalog, artifacts):
        raise ValueError("stale catalog metadata")
    files = {"baseline/catalog.json": catalog_bytes.decode()}
    files.update({"baseline/" + entry["file"]: raw.decode() for entry, raw in artifacts})
    for name in HELPERS:
        files["scripts/" + name] = (root / "scripts" / name).read_text()
    source = (root / "scripts/install.py").read_text()
    if source.count(MARKER) != 1:
        raise ValueError("installer must contain exactly one release resource slot")
    # repr creates a Python string literal; JSON is parsed as data, not interpolated code.
    encoded = repr(json.dumps(files, sort_keys=True))
    result = source.replace(MARKER, "EMBEDDED_POLICY = " + encoded).encode()
    if len(result) > legacy.MAX_INSTALLER_BYTES:
        raise ValueError("embedded installer exceeds signed distribution size limit")
    return result
