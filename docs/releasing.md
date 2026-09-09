# Releasing aiscb

This page describes how to publish a new release of aiscb, step by step. It is
written for the maintainer. AGENTS.md states the rules; this page gives the
order and the commands.

## What a release consists of

Three files are shipped together. They are called the bundle:

- `secure-coding-baseline.md`
- `scripts/install.py`
- `scripts/show_baseline_version.py`

Users receive the bundle in two ways:

1. **Quick start** (new installs). `setup.sh` contains the name of a bundle tag
   and the SHA-256 of each of the three files. The Quick start block in
   `README.md` contains the commit of `setup.sh` and its SHA-256.
2. **`install.py --update`** (existing user-level installs). The installed
   copy downloads `bundle.json` and `bundle.json.sig` from the latest release,
   checks the signature against the public keys in `ALLOWED_SIGNERS` in
   `scripts/install.py`, and then downloads and checks the three files.

Both paths depend on hashes and a signature that match the released files. As
long as one of them does not match the working tree, `make check` fails and
names the missing step.

## One-time setup: create the release key

You need an SSH key of type Ed25519. Its private half must never be committed,
uploaded to CI, or shown to an assistant.

With a FIDO security key (recommended, the private half cannot be copied):

```bash
ssh-keygen -t ed25519-sk -C aiscb-release -f ~/.ssh/aiscb-release
```

Without a security key:

```bash
ssh-keygen -t ed25519 -C aiscb-release -f ~/.ssh/aiscb-release
```

Choose a passphrase. Then add the public key to `ALLOWED_SIGNERS` in
`scripts/install.py`:

```python
ALLOWED_SIGNERS: tuple[str, ...] = (
    "aiscb-release ssh-ed25519 AAAA...",
)
```

The line is `aiscb-release`, a space, and the first two fields of
`~/.ssh/aiscb-release.pub`. If you run `make sign-bundle` before the line
exists, it prints the exact line to add. Commit the change; it ships with the
next bundle.

## Publishing a release

Follow the steps in this order. Each step that changes one of the three
bundle files invalidates the signature and the hashes from the steps after it.

### 1. Finish the content

- Merge the baseline change through its specification under `specs/`.
- Set the new `baseline-id` in `secure-coding-baseline.md`. Only change the
  version when it has been approved explicitly.
- Recompute the file size and the `o200k_base` token count of the baseline and
  update both numbers in `README.md`.

### 2. Update the version in the other files

Replace the previous version number in:

- `README.md`: the `baseline?` example answer and the ID examples
- `docs/adapting-in-an-organization.md`: the derived-ID example and the
  `Extends aiscb` line in the overlay block
- `examples/organization-bundle/overlay.md`: the `Extends aiscb` line;
  `make check` fails until it names the new release
- `scripts/test_show_baseline_version.py`: `VALID_ID` and the invalid-UTF-8
  test case
- `scripts/test_install.py`: the "Switch to a managed copy of ..." question

### 3. Sign the bundle

```bash
make sign-bundle KEY=~/.ssh/aiscb-release
```

This writes `bundle.json` with the size and SHA-256 of the three files, signs
it into `bundle.json.sig`, and checks the signature against
`ALLOWED_SIGNERS`. If you change one of the three files after this step, run
it again.

### 4. Commit the bundle

Commit the changed files together with `bundle.json` and `bundle.json.sig`,
for example:

```
release: identify the baseline as aiscb-X.Y.Z
```

`make check` still fails at this point, because `setup.sh` has the old
hashes. That is expected.

### 5. Tag the bundle

```bash
git tag aiscb-bundle-X.Y.Z-1
```

The last number counts the bundles of one baseline version. A second bundle
for the same version, for example after an installer fix, gets `-2`. Never
move or reuse a published tag.

### 6. Pin the bundle in `setup.sh`

Set `bundle_ref` to the new tag. Set `baseline_sha`, `installer_sha`, and
`helper_sha` to the SHA-256 of the files in that tagged commit:

```bash
git show aiscb-bundle-X.Y.Z-1:secure-coding-baseline.md | sha256sum
git show aiscb-bundle-X.Y.Z-1:scripts/install.py | sha256sum
git show aiscb-bundle-X.Y.Z-1:scripts/show_baseline_version.py | sha256sum
```

Leave the download size limits as they are. Replace the two occurrences of the
old bundle tag in `scripts/test_install.py`. Commit:

```
build: pin the aiscb-X.Y.Z bundle
```

`make check` passes again.

### 7. Pin the bootstrap in `README.md`

The Quick start block needs the commit from step 6 and the SHA-256 of
`setup.sh` in that commit:

```bash
git rev-parse HEAD
git show HEAD:setup.sh | sha256sum
```

Put the commit into the URL and the hash into the `echo` line. Commit:

```
docs: pin the aiscb-X.Y.Z bootstrap
```

Do not push or merge the state between step 6 and step 7. In that state the
README still installs the previous bundle.

### 8. Tag and publish

Create the release tag on the commit from step 7, push everything, and publish
a GitHub release for it. It must be a normal release, not a prerelease or a
draft, because `install.py --update` and the startup hook read the latest
release.

```bash
git tag aiscb-X.Y.Z
git push origin main aiscb-bundle-X.Y.Z-1 aiscb-X.Y.Z
gh release create aiscb-X.Y.Z --title aiscb-X.Y.Z --notes-file <notes>
```

The release can also be created in the GitHub web interface.

## Special cases

**Installer or hook changed, baseline unchanged.** Run steps 3 to 7 with the
next bundle number, for example `aiscb-bundle-X.Y.Z-2`. New installs get the
change through the Quick start right away. Existing installs get it with the
next baseline release, because `--update` only acts on a higher baseline
version.

**Documentation only.** No bundle, no tag, no hashes. Commit and push.

## Checking a published release

- `make check` passes on the published commit.
- `python3 scripts/bundle_manifest.py --verify` prints
  `bundle manifest verified`.
- On a machine with the previous release installed for the user, run
  `python3 ~/.local/share/aiscb/install.py --update`. It should name the new
  version, verify it, and start the guided setup. A new session then shows the
  new ID in the banner.
- On a clean machine, the Quick start block from the README installs the new
  bundle, and `baseline?` in a new session names the new ID.

## Rotating the release key

**Planned rotation, old key still trusted.** Add the new public key to
`ALLOWED_SIGNERS` and keep the old one. Sign the next bundle with the old key.
Existing installs can verify that bundle, and after the update they carry both
keys. Sign the bundle after that with the new key and remove the old line.

**Old key compromised.** Remove the old line immediately and sign with the new
key. Installs from before this release cannot verify it; `--update` refuses and
points them to the Quick start. Say so in the release notes.
