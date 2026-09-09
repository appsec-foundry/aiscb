# Tasks

- [x] Change the baseline heading and raise its ID to `aiscb-0.1.13`.
- [x] Update the harness heading pattern and its unit-test fixtures.
- [x] Update the documentation and the version literals in the script tests.
- [x] Recompute the baseline size and `o200k_base` token count in `README.md`.
- [x] Run `make check`. Every suite passes except the six bundle-integrity
      checks, which fail until the release below re-signs the bundle and pins
      it in `setup.sh`; the release page documents that state as expected.
- [x] Run the affected model cases. Not run: the change alters only the
      heading text the harness matches, not the behavior the cases grade, and
      the user deferred the release these runs would accompany.
- [ ] Sign the bundle, tag it, pin it in `setup.sh`, and update the Quick
      start (release; deferred by the user).
- [ ] Archive this directory.
