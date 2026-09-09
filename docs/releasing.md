# Releasing aiscb

How a baseline release reaches users, and what the maintainer does in which
order. AGENTS.md carries the rules that bind every edit; this page is the
sequence with the commands.

Three files form the bundle that every install path ships together:
`secure-coding-baseline.md`, `scripts/install.py`, and
`scripts/show_baseline_version.py`. Two things pin them:

- `setup.sh` names one bundle tag and the SHA-256 of each file. The Quick start
  in `README.md` names one commit of `setup.sh` and its SHA-256. This is the
  path for new installs.
- `bundle.json` lists the size and SHA-256 of each file, and `bundle.json.sig`
  is an OpenSSH signature over it by the release key. `install.py --update`
  fetches both from the latest release tag, verifies them against the public
  keys in `ALLOWED_SIGNERS` in `scripts/install.py`, and only then installs.
  This is the path for existing user-level installs.

`make check` fails while any of these no longer matches the working tree. That
is intended: the failure names the step still missing.

## One-time setup: the release key

Generate an Ed25519 key that never enters the repository, CI, or an
assistant's context. With a FIDO token the private half cannot be copied:

```bash
ssh-keygen -t ed25519-sk -C aiscb-release -f ~/.ssh/aiscb-release
```

Without a token, use `-t ed25519` and a passphrase. Then add the public half to
`ALLOWED_SIGNERS` in `scripts/install.py` as one allowed-signers line:

```python
ALLOWED_SIGNERS: tuple[str, ...] = (
    "aiscb-release ssh-ed25519 AAAA...",
)
```

`make sign-bundle KEY=~/.ssh/aiscb-release` prints the exact line when it is
missing. Commit the change; it is part of the next bundle.

## Release sequence

Every step that changes a bundled file invalidates the manifest and the
`setup.sh` hashes, so the order below runs from content to distribution.

1. **Finish the content.** Merge the baseline change through its specification
   under `specs/`. Set the new `baseline-id` in `secure-coding-baseline.md`
   only when the user approved the exact value. Recompute the file size and the
   `o200k_base` token count and update both in `README.md`.
2. **Update the version references.** The IDs in `README.md` (the `baseline?`
   answer and the ID examples), the derived-ID example in
   `docs/adapting-in-an-organization.md`, `VALID_ID` and the invalid-UTF-8 case
   in `scripts/test_show_baseline_version.py`, and the migration question in
   `scripts/test_install.py`.
3. **Sign the bundle.** Run `make sign-bundle KEY=~/.ssh/aiscb-release`. It
   writes `bundle.json` for the current bundled files, signs it, and verifies
   the signature against `ALLOWED_SIGNERS`. Repeat after any later change to a
   bundled file.
4. **Commit the bundle** with the manifest and signature, for example
   `release: identify the baseline as aiscb-X.Y.Z`. `make check` still fails
   on the `setup.sh` hashes at this point.
5. **Tag the bundle.** Tags are never moved or reused; the number after the
   version counts bundles of the same baseline version:

   ```bash
   git tag aiscb-bundle-X.Y.Z-1
   ```

6. **Pin the bundle in `setup.sh`.** Set `bundle_ref` to the new tag and the
   three `*_sha` values to the SHA-256 of the files in that exact commit, for
   example `git show aiscb-bundle-X.Y.Z-1:scripts/install.py | sha256sum`.
   Keep the download size limits. Update the two `aiscb-bundle-` strings in
   `scripts/test_install.py`. Commit: `build: pin the aiscb-X.Y.Z bundle`.
   `make check` passes again.
7. **Pin the bootstrap in `README.md`.** The Quick start block needs the commit
   from step 6 and the SHA-256 of `setup.sh` in it:

   ```bash
   git rev-parse HEAD
   git show HEAD:setup.sh | sha256sum
   ```

   Put both into the command block and commit:
   `docs: pin the aiscb-X.Y.Z bootstrap`. Never publish or merge the state
   between steps 6 and 7; the README would install the previous bundle.
8. **Tag and publish the release** on the commit from step 7, as a stable
   release, not a prerelease or draft. `install.py --update` and the startup
   hook read `releases/latest`, so the release tag must contain the version
   and point at a tree whose `bundle.json` matches its bundled files, which
   the docs commit does:

   ```bash
   git tag aiscb-X.Y.Z
   git push origin main aiscb-bundle-X.Y.Z-1 aiscb-X.Y.Z
   gh release create aiscb-X.Y.Z --title aiscb-X.Y.Z --notes-file <notes>
   ```

A change to `install.py` or the hook helper without a baseline change needs
steps 3 to 7 with the next bundle number, for example `aiscb-bundle-X.Y.Z-2`,
and reaches `--update` users with the next baseline release; the Quick start
delivers it immediately. A documentation-only commit needs no bundle.

## Checking a release

- `make check` is green on the published commit.
- `python3 scripts/bundle_manifest.py --verify` reports the manifest verified.
- From a machine with the previous release installed at user level,
  `python3 ~/.local/share/aiscb/install.py --update` names the new version,
  verifies, and starts the guided setup; a fresh session's banner shows the new
  ID.
- The Quick start block from the README installs the new bundle on a clean
  machine, and `baseline?` in a new session names the new ID.

## Rotating the release key

Planned rotation, old key still trusted: add the new public line to
`ALLOWED_SIGNERS`, keep the old one, and sign the next bundle with the old key.
Existing installs verify that bundle and now carry both keys. Sign the bundle
after that with the new key and drop the old line.

Compromise: drop the old line at once, sign with the new key, and say in the
release notes that installs from before this release refuse `--update` and must
run the Quick start once. The refusal message already points there.
