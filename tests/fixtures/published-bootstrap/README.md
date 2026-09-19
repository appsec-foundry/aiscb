# Published compatibility fixture

These are public historical bytes, not the current build:

- `setup.sh`: commit `6deb1bd83c627a54c31570899a4dd1dc40f690c1`.
- `bundle.json` and `bundle.json.sig`: tag `aiscb-bundle-0.1.15-2`.

The tests verify the README's currently published bootstrap hash, the bootstrap
pins, and the manifest's real public-key signature. Runtime bootstrap mutation
tests substitute freshly built fixture hashes only in a temporary script.
Current release verification separately requires `make check-release` on the
actual staged and signed output. Never rewrite this fixture to represent an
unpublished development build; a future published bootstrap gets its own
authenticated fixture and corresponding Quick start test update.
