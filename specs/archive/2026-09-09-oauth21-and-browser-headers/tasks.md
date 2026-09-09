# Tasks

- [x] Change the baseline: the OAuth bullet under `aiscb-MECHANISMS-001` and
      the browser bullet under `aiscb-DEFAULTS-001`.
- [x] Update the test cases and their requirement IDs. No case added: the
      existing cases do not observe these sentences, and none names a new ID
      because the rule groups keep theirs.
- [x] Update `specs/requirements.md` and the README summaries.
- [x] Recompute the baseline size and `o200k_base` token count in `README.md`.
- [x] Run `make check`. Every suite passes except the bundle-integrity checks
      in `scripts/test_install.py`, which fail until the maintainer re-signs
      the bundle for the changed baseline and pins it in `setup.sh`.
- [x] Run the affected model cases, or note why not. Not run: no case
      observes the new sentences, so a run would measure nothing new; cases
      for OAuth grants, token storage, and CSP contents are a separate
      decision.
- [x] Raise the baseline ID to `aiscb-0.1.14` together with
      `common-coding-gaps`, as the user approved.
- [x] Archive this directory.
