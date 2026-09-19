# Releasing aiscb

Source control contains core, modules, catalog, tooling and documentation.
Complete files, manifests and signatures are generated distribution artifacts,
not tracked copies of the rules. Never publish development output as a release.

## Build locations

- `make build-full-baseline`: `dist/dev/aiscb-VERSION/secure-coding-baseline.md`.
- `make build-release VERSION=X.Y.Z REVISION=N`:
  `dist/aiscb-X.Y.Z/bundle-N/`. The directory must not exist.
- Files inside a bundle retain stable names: `secure-coding-baseline.md`,
  `scripts/install.py`, `scripts/show_baseline_version.py`, `bundle.json`,
  and generated `setup.sh`. Signing adds `bundle.json.sig`.

The staged installer embeds the reviewed core, catalog, modules and Python
loader/setup sources as data. Its existing manifest entry and bootstrap hash
cover those exact bytes. Runtime setup extracts them into a private temporary
directory, validates the catalog, and installs persistent verified snapshots;
it fetches no replacement code or policy. The three-file signed update contract
therefore remains unchanged. The complete Markdown remains a compatibility asset,
not the default initial prompt. Never replace the staged installer with the
unbundled checkout script before signing.

A baseline version identifies core and official modules together. A bundle
revision distinguishes packaging changes; it does not approve new normative
content under an already-published baseline version. Organization overlays have
their own version and pin the upstream catalog.

## Development gate versus release gate

`make check` validates sources, builds development output and runs deterministic
tests without a maintainer key. It tests signatures with temporary test keys and
retains a signed historical bootstrap fixture for compatibility checks.
It does not declare the working tree published or signed.

`make check-release BUNDLE_DIR=dist/aiscb-X.Y.Z/bundle-N` is mandatory before
publication. It verifies the staged manifest, exact bytes, trusted signature,
versioned directory and matching bootstrap hashes. Missing signatures fail.
Never replace this with development checks or skip verification to make a release.

## Prepare and publish

1. Obtain explicit approval of the exact baseline version. Update the core ID,
   catalog baseline ID and every official module version, builder constants,
   overlay compatibility references and version-sensitive tests. Keep existing
   rule IDs. Update the README version examples.
2. Update [`CHANGELOG.md`](../CHANGELOG.md) from the Git changes since the
   previous release. Explain what changed for users and what they need to do
   when updating. Use short, plain-language entries. Group related changes;
   omit internal refactoring, routine test work, and planned features.

   Record completed changes under **Unreleased**. Before publication, put the
   changes being shipped under the approved version, date and release link.
   List later installer updates separately, with a date, under the version
   they install. Reuse the summary in GitHub release notes, keeping build and
   signing details separate. Do not publish without a current changelog entry.
3. Run `make build-full-baseline`; recompute all README byte and
   `o200k_base` token measurements. Run `make check`. Review the resulting
   sources and record the approved source commit. Generated output is ignored.
4. Stage the approved version and an unused positive revision:

   ```bash
   make build-release VERSION=X.Y.Z REVISION=1
   ```

   This writes an unsigned manifest and hash-pinned asset bootstrap, and refuses
   an existing directory. It neither signs nor publishes. For a changed staging
   attempt, use a new revision; never overwrite a published bundle.
5. The maintainer signs and checks the staged bytes:

   ```bash
   make sign-bundle BUNDLE_DIR=dist/aiscb-X.Y.Z/bundle-1 KEY=/path/to/release-key
   make check-release BUNDLE_DIR=dist/aiscb-X.Y.Z/bundle-1
   ```

   The private key stays outside the repository, CI and assistant context.
   The public key must already appear in `ALLOWED_SIGNERS` in the staged
   installer. A changed file after signing invalidates the release.
6. Create the immutable distribution tag `aiscb-bundle-X.Y.Z-N` on the reviewed
   source commit. Upload the staged files to its GitHub release, marked
   **prerelease** so a packaging tag cannot become the updater's latest stable
   baseline. The generated bootstrap pins this distribution tag and revision.
   Also prepare the new `aiscb-X.Y.Z` baseline release with identical assets
   for signed updates. Use these asset names on both releases:

   | Staged file | Asset name |
   | --- | --- |
   | `secure-coding-baseline.md` | `secure-coding-baseline.md` |
   | `scripts/install.py` | `install.py` |
   | `scripts/show_baseline_version.py` | `show_baseline_version.py` |
   | `bundle.json` | `bundle.json` |
   | `bundle.json.sig` | `bundle.json.sig` |

   The signed manifest keeps the logical `scripts/` paths; the downloader maps
   them to asset basenames. Do not use upload overwrite options. Keep source
   commit and bundle revision in the release notes. An archive is optional and
   must be named `aiscb-X.Y.Z-bundle-N.tar.gz`; it is not the updater input.
7. Prepare the new Quick start from the staged `setup.sh`. After the assets are
   available, put these exact bytes into the tracked root `setup.sh`, commit it,
   then update the **complete** README Quick start block with that commit and
   its exact SHA-256 in a follow-up documentation commit. Keep the old working
   Quick start until the new assets can actually be downloaded. Never publish
   or merge a mismatched bootstrap URL/hash pair.
8. Verify the real download path in a clean environment: expected version,
   signature, hash/size checks, refused tampering, installation and new-session
   loading. Publish the release as stable only after validation; the updater
   rejects draft/prerelease metadata. Do not claim release completion while
   real-client acceptance or the Quick start transition is unverified.

The initial asset publication, stable-release switch and Quick start transition
require maintainer coordination. This script set does not perform remote
publication or make a multi-step GitHub release atomic.

## Existing installations and migration

Historical releases keep their Git-tree files and tags unchanged. The published
0.1.15 bootstrap, manifest and signature remain archived in
`tests/fixtures/published-bootstrap/` as immutable compatibility fixtures.
The current README pins the 0.1.16 asset bootstrap.

The new updater supports legacy Git-tree files and, when a file is absent,
the same release's assets. Both paths still require the signed manifest before
executing downloaded code. Asset URLs are restricted to the expected release;
downloads and redirects are HTTPS-bound and size-limited.

**Older installed updaters cannot discover asset-only releases.** They fail
closed and point to the Quick start. Users must run the updated verified Quick
start once to migrate. Do not promise an automatic update from 0.1.15.
A transitional Git-tree release would be a separate maintainer decision.

Starting with 0.1.17, the signed installer embeds the modular sources and helpers
and defaults to modular project and user installation. It never fetches helper
code. The complete Markdown remains a compatibility asset for explicit complete
mode. Historical three-file bundles without embedded helpers cannot install
modular policy; users need the newly signed installer or a reviewed checkout.

## Organization rollout and client acceptance

New modules flow through the catalog into organization bundles and complete
output. Check installation with and without an overlay, all supported entry
points, dependencies, preserved instructions, update and rollback. Follow the
[client verification guide](agent-integration-verification.md); file tests do
not prove Claude, Copilot or Codex selected the right modules.

User-level legacy setup is distinct from project-local snapshots. Close sessions
before switching project entry points. Reinstall from an approved prior checkout
or organization bundle to roll back local snapshots. Never move release tags.

For packaging-only changes to an already published baseline, publish a new
distribution revision and update the Quick start; never replace the existing
stable release's assets. Existing installs update automatically only with a
higher baseline version. A packaging-only distribution remains a prerelease
entry so it cannot displace the latest stable baseline in the GitHub API.

## Key setup and rotation

Use a maintainer-owned Ed25519 or FIDO Ed25519 OpenSSH release key. Only its
public allowed-signers line enters `scripts/install.py`:

```text
aiscb-release ssh-ed25519 PUBLIC_KEY_BASE64
```

For planned rotation, ship both public keys in a bundle signed by the old key;
subsequent releases can use the new key. If the old key is compromised, remove
it and require users whose installer lacks the new key to migrate through the
verified Quick start. Never show a private key to an assistant.
