# Tasks

- [x] Change the baseline: drop the webhook clause from `aiscb-MECHANISMS-001`.
      The module goes from 1,111 to 1,058 bytes and from 234 to 226
      `o200k_base` tokens; the complete baseline from 5,380 to 5,372 tokens.
- [x] Update the test cases and their requirement IDs. None needed: no case
      observes the clause (`greenfield-order-app` covers password hashing only).
      `tests/test_split_modules.py` pins the rule bodies of the three split
      modules; its hash now covers the bodies after this change, and the
      comment names this directory.
- [x] Update `specs/requirements.md` (`aiscb-MECHANISMS-001`) and the size
      tables in the README and `docs/modular-baseline-handoff.md`; the current
      totals in `docs/web-auth-crypto-split.md`.
- [x] Run `make build-full-baseline` and `make check`.
- [x] Run the affected model cases, or note why not. Not run: no case observes
      the removed clause, and the one that names the rule group,
      `greenfield-order-app`, exercises password hashing.
- [x] Archive this directory.
