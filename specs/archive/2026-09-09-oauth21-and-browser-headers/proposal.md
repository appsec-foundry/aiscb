# OAuth 2.1 and current browser header requirements

## Problem

`aiscb-MECHANISMS-001` names OAuth 2.0 and forbids only the implicit flow. It
allows the password grant, PKCE `plain`, access tokens in a URL, and tokens in
browser-readable storage, all of which OAuth 2.1 (draft-ietf-oauth-v2-1-16,
section 10) and RFC 9700 remove or forbid. `aiscb-DEFAULTS-001` names "CSP"
without a mechanism, so a policy with `unsafe-inline` satisfies it, and it
omits the cross-origin isolation headers, `Cache-Control: no-store`, and the
`__Host-` cookie prefix that the OWASP HTTP Headers, CSP, and Session
Management cheat sheets recommend.

## Goal

Name the mechanism where the bare keyword permits an unsafe default: the
grants and PKCE method, where a token may travel and be stored, what a CSP
must contain, and which headers and cookie prefix apply. Nothing else moves.

## Non-goals

No DPoP, PAR, JAR, COEP, Trusted Types, `Clear-Site-Data`, or
`Integrity-Policy` requirements. No new rule group and no version change in
this directory; the version is raised together with `common-coding-gaps`
once the user names the value.

## Compatibility

Both rule groups keep their IDs and headings. The two bullets grow by 131
`o200k_base` tokens; the baseline stays under its budget. Existing model
checks match on unchanged headings and header names.
