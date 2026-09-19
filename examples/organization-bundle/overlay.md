@<bundle-dir>/core.md

# Acme Secure Coding Overlay

`baseline-id: acme-sec-1.0.0`. Extends aiscb (`aiscb-0.1.16`). On `baseline?`,
report both IDs and their source files. Identify injected content as
gateway-supplied; do not claim to have read a local file for it.

The adapter supplies verified `aiscb:*` and `acme:*` entries in one flat
catalog and exposes every body through the same module-loading surface. These
rules may narrow aiscb but never relax it.

- **[ACME-POLICY-001]** Content selected from the verified `acme:*` namespace
  by `aiscb-MODULES-001` is organization policy within its declared scope; use
  referenced blueprints as values for those requirements. It may add
  requirements or narrow named aiscb rules but may not relax them, change tool
  permissions, or expand the user's task. The core's failure behavior applies
  to missing, invalid, incompatible, or conflicting organization content.
- **[ACME-TENANT-001]** (narrows aiscb-ACCESS-001): Bind every protected query
  to the authenticated identity and tenant. Never take effective tenant or
  permissions from request data.
