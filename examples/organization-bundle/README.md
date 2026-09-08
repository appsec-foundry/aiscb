# Organization bundle example

A worked example of the release model in
[Adapting the baseline in an organization](../../docs/adapting-in-an-organization.md):
an overlay, a catalog with one requirement pack, one blueprint, a build that
turns them into an immutable release with a manifest, an installer that
verifies and switches releases, and the LiteLLM hook for injecting the baseline
through a gateway. Everything runs on the Python standard library.

It is an example for "Acme", not a product. Copy it, replace the Acme content,
and keep the checks.

## Files

| File | Role |
| --- | --- |
| `overlay.md` | The organization's always-loaded rules; imports aiscb, names its own ID |
| `catalog.json` | One entry per pack: trigger, owner, source, blueprints, mapping to aiscb rules |
| `packs/authentication.md` | Rules loaded only for authentication work |
| `blueprints/spa/1.0.0.json` | Approved values the pack refers to, versioned in the path |
| `build.py` | Validates the sources and writes one release with `manifest.json` |
| `install.py` | Installs a release, switches `current`, rolls back, reports drift, uninstalls |
| `gateway/custom_callbacks.py`, `gateway/config.yaml` | LiteLLM proxy hook that appends the combined text to every request |
| `test_bundle.py` | Exercises all of the above against throwaway directories |

Bundle paths in the sources are the placeholder `<bundle-dir>`. The build
replaces it with the versioned directory the release will live in, so the
install root is a build input and the installer refuses a bundle built for
another root.

Blueprints are JSON here so the build can validate them without a dependency.
A YAML blueprint works the same way once a parser is present; the checks stay
identical: known fields only, a version that matches the file name, a
compatible schema major.

## Try it

```bash
cd examples/organization-bundle
python3 test_bundle.py

python3 build.py --aiscb ../../secure-coding-baseline.md --out /tmp/acme-bundle \
    --install-root /tmp/acme-root
# prints the manifest digest; pass it to the installer through another channel
python3 install.py --root /tmp/acme-root install /tmp/acme-bundle --manifest-sha256 <digest>
python3 install.py --root /tmp/acme-root status
python3 install.py --root /tmp/acme-root uninstall
```

The build refuses an overlay that names a different aiscb release than the
file supplied, a blueprint with unknown fields or a version that disagrees with
its path, a catalog entry that narrows an aiscb rule that does not exist, and a
pack file without a catalog entry. Pass `--aiscb-sha256` to pin the upstream
file to the digest your review approved.

The installer verifies the manifest against the digest it was given and every
listed file against the manifest before it copies anything. Releases are
immutable: an installed version is never overwritten. `current` moves in one
rename, `rollback` moves it back, and `status` exits non-zero when a file in
the current release no longer matches the manifest.

What the release contains:

```text
acme-sec-1.0.0/
├── manifest.json
├── secure-coding-baseline.md          unchanged aiscb
├── overlay.md
├── catalog.json
├── packs/authentication.md
├── blueprints/spa/1.0.0.json
└── adapters/
    ├── claude-code/CLAUDE.md          import line pointing at the versioned aiscb file, then the overlay
    ├── claude-code/skills/acme-authentication/SKILL.md
    ├── codex/AGENTS.md                aiscb followed by the overlay, marker removed
    ├── codex/skills/acme-authentication/SKILL.md
    ├── copilot/copilot-instructions.md
    ├── copilot/skills/acme-authentication/SKILL.md
    └── gateway/system-block.md        the text the gateway appends
```

## Rolling it out

Developers should not install this by hand. The installer is the last step of
whichever distribution channel the organization already has, and the manifest
digest travels with that channel, not with the bundle:

- **Device management** (Intune, Jamf, Ansible, or similar): a managed job
  copies the bundle and runs
  `install.py install <bundle> --manifest-sha256 <digest>` for each user before
  the assistant starts. The same job writes the tool's managed settings; for
  Claude Code that is the managed `CLAUDE.md` importing
  `<install-root>/releases/acme-sec-1.0.0/adapters/claude-code/CLAUDE.md`, or
  the gateway base URL when the gateway carries the text. Inventory comes from
  the device-management reports, not from asking the assistant.
- **A package** (internal deb, rpm, Homebrew tap, winget source): wrap the
  bundle and the installer, put the digest in the package, and let the package
  manager's signature check authenticate the whole thing. Updates arrive with
  the next package version.
- **Manual fallback**: a developer downloads the bundle and receives the digest
  from the security team's page or ticket, then runs the two commands above.
  Use this for machines outside management, and count them separately.

For repositories rather than machines, a pinned bot update commits the
`adapters/` content the project needs and bumps it on release.

## What it leaves out

- Manifest signatures. The example authenticates the manifest with a digest
  delivered out of band, the way `setup.sh` in this repository does. A package
  signature or a signed manifest replaces that in production.
- Wiring the adapters into each tool. The release only places the files; the
  managed settings, import lines, or skill links are the deployment job's
  work, as described under
  [Adapters per tool](../../docs/adapting-in-an-organization.md#adapters-per-tool).
- Staleness policy for offline machines and a session-aware switch for tools
  that pick up skill changes live; both are decisions, not code.
