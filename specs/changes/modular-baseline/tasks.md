# Tasks

The approved follow-up in `../agent-systems/` renames the core, adds secure
design and agent-system rules, and implements project-local module installation
with organization overlays. Its task record contains current verification and
OWASP review evidence. The release boundary below remains outstanding.

- [x] Add the normative core, official modules, flat catalog, and deterministic eager builder.
- [x] Update the complete eager baseline to `aiscb-0.1.16` without losing existing requirements.
- [x] Add deterministic validation and mutation coverage for modular artifacts.
- [x] Adapt the organization overlay guidance and example to the flat module plane.
- [x] Update `AGENTS.md`, `specs/requirements.md`, README measurements, and release documentation.
- [x] Prepare `bundle.json` for maintainer signing. `bundle.json.sig`, the
  immutable bundle tag, `setup.sh`, and the complete README Quick start remain
  at 0.1.15 until a maintainer performs the documented key-bearing release
  sequence; no signature was fabricated.
- [x] Run `make check`. All modular, specification, harness, organization, and
  adapter checks passed. The five expected release checks fail because the
  committed signature and bootstrap still authenticate 0.1.15 rather than the
  unsigned 0.1.16 manifest.
- [x] Record model-test status. No paid model cases were run: the refactor moves
  rules across every domain and therefore has no honest narrow affected set;
  the complete suite is 162 agent turns plus judging, and the user did not ask
  to spend that budget. Existing case mappings and deterministic checks were
  updated.
- [ ] Archive this directory after maintainer signing and the remaining release
  checks pass.
