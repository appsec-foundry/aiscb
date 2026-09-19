# Acme deployment requirements

Pack `acme-deployment`. Apply when a change decides how a service is exposed,
where TLS terminates, what sits in front of it, how it is containerized, or
what happens at first start.

- **[ACME-EXPOSE-001]** (narrows aiscb-DEFAULTS-001): Behind Acme's TLS
  terminator, trust forwarding headers only from the terminator's addresses,
  enable `Secure` cookies and HSTS on every non-loopback bind, and let a
  plain-HTTP listener do nothing but redirect to HTTPS.
- **[ACME-BOOTSTRAP-001]** (narrows aiscb-SECRETS-001): Container stdout and
  stderr are logs. A first-start credential reaches the operator through the
  interactive console or a file with owner-only permissions, never through
  stdout, and the deployment job records that it was consumed.

Verify forged forwarding headers from another source, a plain-HTTP request to
a non-loopback bind, and a first start under the container runtime.
