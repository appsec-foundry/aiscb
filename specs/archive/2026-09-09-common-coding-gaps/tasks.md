# Tasks

- [x] Change the baseline: one sentence each under `aiscb-INPUT-001`,
      `aiscb-MECHANISMS-001`, and `aiscb-DEFAULTS-001`.
- [x] Update the test cases and their requirement IDs. No case added: the
      existing cases do not observe these sentences, and none names a new ID
      because the rule groups keep theirs.
- [x] Update `specs/requirements.md` and the README summaries, and state the
      data-protection scope limit in the README.
- [x] Recompute the baseline size and `o200k_base` token count in `README.md`.
- [x] Run `make check`. Every suite passes except the bundle-integrity checks
      in `scripts/test_install.py`, which fail until the maintainer re-signs
      the bundle for the changed baseline and pins it in `setup.sh`.
- [x] Run the affected model cases, or note why not. Not run: no case
      observes the three new sentences, so a run would measure nothing new;
      cases for field binding, constant-time comparison, and CI permissions
      are a separate decision.
- [x] Raise the baseline ID to `aiscb-0.1.14`, as the user approved.
- [x] Archive this directory.
