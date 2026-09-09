# Tasks

- [x] Change the baseline: trim the TLS and bootstrap bullets.
- [x] Update the test cases and their requirement IDs. No case changes: no
      check keys on the moved sentences.
- [x] Add `packs/deployment.md` and its catalog entry to the bundle example
      and list them in its README.
- [x] Update `specs/requirements.md` and the documentation. The catalog
      entries for both groups already describe the retained core.
- [x] Recompute the baseline size and `o200k_base` token count in `README.md`.
- [x] Run `make check`. Every suite passes except the bundle-integrity
      checks in `scripts/test_install.py`, which fail until the maintainer
      re-signs the bundle for the changed baseline and pins it in `setup.sh`.
- [x] Run the affected model cases, or note why not. Not run: no check keys on the moved sentences, and the retained core is what the TLS and first-credential cases grade.
- [ ] Archive this directory.
