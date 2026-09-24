# Tasks

- [x] Change the baseline: replace the paragraph under `Module Routing` with
      the one-sentence version. The core goes from 8,357 to 8,019 bytes and
      from 1,650 to 1,594 `o200k_base` tokens; the complete baseline from
      5,436 to 5,380 tokens.
- [x] Update the test cases and their requirement IDs. None needed: no case
      observes the removed sentences; `make test-routing` observes the kept
      behavior.
- [x] Update `specs/requirements.md` (`aiscb-MODULES-001`), the README sizes
      and budget comparison, and the measurements in
      `docs/modular-baseline-handoff.md` and `docs/web-auth-crypto-split.md`.
- [x] Run `make build-full-baseline` and `make check`.
- [x] Run `make test-routing`, or note why not. Not run: the preflight refused
      because this machine carries a user-level aiscb installation that the
      control arm would inherit. Run it from a machine or home without a
      user-level installation when evidence is wanted; the cases to watch are
      `semantic`, `multiple`, `scope-change`, `context-loss`, and `missing`.
- [x] Archive this directory.
