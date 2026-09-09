# Requirements

## DEPLOY-CORE-001 Keep the transport behavior core

Source: the user's request in this conversation to move deployment detail
from `aiscb-DEFAULTS-001` and `aiscb-SECRETS-001` into packs; `AGENTS.md`,
which excludes application security specifications from the baseline; and
commit 0431a23, which introduced the sentences being moved.

`aiscb-DEFAULTS-001` requires TLS for all traffic that leaves the machine,
loopback binding by default, TLS configuration for any wider bind with startup
failing when it is absent, and a statement of the required TLS step when wider
exposure is out of scope. Proxy trust, redirect-only plain-HTTP listeners, and
per-bind cookie and HSTS settings leave the baseline.

Acceptance: the TLS bullet names those four behaviors and nothing else, and
the browser bullet still carries `Secure` cookies and HSTS.

## DEPLOY-CORE-002 Keep the bootstrap behavior core

Source: as above.

`aiscb-SECRETS-001` requires a first admin credential from external
configuration with startup failing when it is absent, or one generated at
first start and disclosed once through an interactive console or a restricted
file, never the UI or logs. The container-stdout sentence leaves the baseline.

Acceptance: the bootstrap bullet names those behaviors and nothing else.

## DEPLOY-PACK-001 Carry the moved detail in an example pack

Source: the user's request in this conversation.

`examples/organization-bundle/packs/deployment.md` states the moved detail as
Acme requirements narrowing `aiscb-DEFAULTS-001` and `aiscb-SECRETS-001`, and
`catalog.json` lists the pack with a trigger for exposure, TLS termination,
proxies, containers, and first-start work.

Acceptance: the bundle builds with two packs and a skill per pack, and
`test_bundle.py` passes.
