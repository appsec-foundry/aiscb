#!/usr/bin/env python3
"""Write, sign, and verify the bundle manifest an installed copy updates from.

The manifest pins the size and SHA-256 of every bundled file; the signature
binds it to a release key whose public half ships in install.py. Signing needs
the maintainer's private key and happens in an explicit staged bundle directory
before publication. Generated files are release assets, not committed sources.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402

MAX_PUBLIC_KEY_BYTES = 4 * 1024


def bundle_files(repo: Path) -> dict[str, bytes]:
    return {
        name: install.read_limited(repo / name, limit)
        for name, limit in install.BUNDLE_FILES.items()
    }


def public_key_line(private_key: Path) -> str:
    """The allowed_signers line for a key, as install.py must carry it."""
    public = private_key.with_name(private_key.name + ".pub")
    fields = install.read_limited(public, MAX_PUBLIC_KEY_BYTES).decode().split()
    if len(fields) < 2:
        raise ValueError(f"{public} is not an OpenSSH public key")
    return f"{install.SIGNER_PRINCIPAL} {fields[0]} {fields[1]}"


def write_manifest(repo: Path) -> Path:
    manifest = repo / install.MANIFEST_NAME
    manifest.write_bytes(install.manifest_document(bundle_files(repo)))
    return manifest


def sign_manifest(repo: Path, private_key: Path) -> Path:
    line = public_key_line(private_key)
    if line not in install.ALLOWED_SIGNERS:
        raise ValueError(
            "install.py does not carry this key; add the line below to "
            f"ALLOWED_SIGNERS first, then sign again:\n  {line!r}"
        )
    manifest = write_manifest(repo)
    signature = repo / install.SIGNATURE_NAME
    signature.unlink(missing_ok=True)
    subprocess.run(
        [
            "ssh-keygen", "-Y", "sign",
            "-f", str(private_key),
            "-n", install.SIGNATURE_NAMESPACE,
            str(manifest),
        ],
        check=True,
        timeout=install.SSH_KEYGEN_TIMEOUT,
    )
    install.verify_manifest_signature(manifest.read_bytes(), signature.read_bytes())
    return signature


def verify_bundle(repo: Path) -> None:
    """Refuse a manifest that is stale, malformed, or signed by an unknown key."""
    manifest = install.read_limited(repo / install.MANIFEST_NAME, install.MAX_MANIFEST_BYTES)
    if manifest != install.manifest_document(bundle_files(repo)):
        raise ValueError("bundle.json does not describe the current bundle files")
    install.parse_manifest(manifest)
    signature = install.read_limited(
        repo / install.SIGNATURE_NAME, install.MAX_SIGNATURE_BYTES
    )
    install.verify_manifest_signature(manifest, signature)


def verify_release(repo: Path) -> None:
    """Publication gate: signed bytes, versioned staging, and matching bootstrap."""
    verify_bundle(repo)
    parsed = install.parse_manifest((repo / install.MANIFEST_NAME).read_bytes())
    if repo.parent.name != parsed.baseline_id or not re.fullmatch(r"bundle-[1-9][0-9]*", repo.name):
        raise ValueError("release directory must be dist/aiscb-VERSION/bundle-N")
    bootstrap = (repo / "setup.sh").read_text()
    revision = repo.name.removeprefix("bundle-")
    if f"/releases/download/aiscb-bundle-{parsed.version}-{revision}" not in bootstrap:
        raise ValueError("bootstrap release mismatch")
    if any(digest not in bootstrap for _, digest in parsed.files.values()):
        raise ValueError("bootstrap hashes do not match signed bundle")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, required=True,
                        help="explicit staged bundle directory, never the source tree")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--write", action="store_true", help="write bundle.json for the staged bundle"
    )
    group.add_argument(
        "--sign", metavar="KEY", type=Path,
        help="write bundle.json and sign it with this OpenSSH private key",
    )
    group.add_argument(
        "--verify", action="store_true",
        help="check that the staged bundle matches its manifest and trusted signature",
    )
    args = parser.parse_args(argv)
    repo = args.bundle_dir.resolve()
    try:
        if args.write:
            print(f"wrote {write_manifest(repo)}")
        elif args.sign is not None:
            print(f"wrote {sign_manifest(repo, args.sign)}")
        else:
            verify_release(repo)
            print("bundle manifest verified")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"bundle manifest: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
