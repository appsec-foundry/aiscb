# Tasks

- [x] Change the baseline: rewrite `aiscb-REPORT-001` from 614 to 466 tokens.
- [x] Update the test cases and their requirement IDs. No case changes: the
      IDs and the graded behavior stay the same.
- [x] Update `specs/requirements.md` and the documentation. The catalog entry
      is condensed the same way; the README summary already matched.
- [x] Recompute the baseline size and `o200k_base` token count in `README.md`.
- [x] Run `make check`. Every suite passes except the bundle-integrity
      checks in `scripts/test_install.py`, which fail until the maintainer
      re-signs the bundle for the changed baseline and pins it in `setup.sh`.
- [x] Run the affected model cases, or note why not. Not run: the wording change keeps every graded behavior; a rerun would measure run-to-run variance, not the change.
- [x] Archive this directory.
