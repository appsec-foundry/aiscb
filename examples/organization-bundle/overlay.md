@<bundle-dir>/secure-coding-baseline.md

# Acme Secure Coding Overlay

`baseline-id: acme-sec-1.0.0`. Extends aiscb (`aiscb-0.1.13`). On `baseline?`,
report both IDs and their source files.

These rules may narrow aiscb but never relax it. If a conflict exists, or an
applicable pack or blueprint is unavailable or invalid, stop the affected work
and report the problem. Do not invent a substitute.

- **[ACME-REQ-ROUTING-001]** Load every requirement pack matching the task and
  its blueprints before affected work. Do not load unrelated packs. The catalog
  is `<bundle-dir>/catalog.json`; each pack names the blueprints it needs.
- **[ACME-TENANT-001]** (narrows aiscb-ACCESS-001): Bind every protected query
  to the authenticated identity and tenant. Never take effective tenant or
  permissions from request data.
