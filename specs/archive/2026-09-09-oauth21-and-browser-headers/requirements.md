# Requirements

## OAUTH21-001 OAuth 2.1 grants and token lifetime

Source: the user's request in this conversation to build the OAuth 2.1 gaps
into the baseline; draft-ietf-oauth-v2-1-16 section 10 and RFC 9700
sections 2.1.2, 2.3, and 2.4.

Under `aiscb-MECHANISMS-001`, an assistant uses the authorization-code flow
with PKCE `S256`, never the implicit or password grant, requests
least-privilege scopes for the intended resource, and rotates or
sender-constrains refresh tokens.

Acceptance: generated federated login uses authorization code with `S256`,
no `grant_type=password` or `response_type=token` appears, and refresh tokens
are rotated or bound to the client.

## OAUTH21-002 Where access tokens travel and live

Source: the user's request in this conversation; RFC 9700 section 4.3.2 and
draft-ietf-oauth-browser-based-apps section 6.1.

Under `aiscb-MECHANISMS-001`, an assistant sends access tokens only in the
`Authorization` header, never in a URL, and keeps them out of
browser-readable storage by letting a backend hold them behind a cookie
session.

Acceptance: no access token appears in a query string, and a browser
application stores no access or refresh token in `localStorage`,
`sessionStorage`, or a JavaScript-readable cookie.

## HEADERS-001 Browser policy mechanisms

Source: the user's request in this conversation; OWASP HTTP Headers, Content
Security Policy, and Session Management cheat sheets.

Under `aiscb-DEFAULTS-001`, an assistant sets a nonce- or hash-based CSP with
no `unsafe-inline` for scripts and with `object-src 'none'`,
`base-uri 'none'`, and `frame-ancestors`; sets `Cross-Origin-Opener-Policy`
and `Cross-Origin-Resource-Policy` to `same-origin` unless cross-origin use
is intended; sets `Cache-Control: no-store` on authenticated responses; and
names session cookies with the `__Host-` prefix.

Acceptance: a generated page's script policy contains a nonce or hash and no
`unsafe-inline`, the listed directives and headers are present, an
authenticated response carries `no-store`, and the session cookie name starts
with `__Host-`.
