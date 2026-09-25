# Clarify module boundaries observed in CWEval

## Problem

The local run `tests/results/cweval/run-2zotqs2n/report.md` (0.1.18,
three samples per arm) exposes unsafe YAML loading, header and log injection,
invalid URL path segments, and unintended credential fields in responses.
The modules before this change do not spell out these mechanisms.

## Goal

Implement the five recommendations approved by the user on 2026-09-24 in
`baseline/modules/aiscb-data-handling.md` and `baseline/modules/aiscb-web.md`.
Record their requirements here and in `specs/requirements.md`; add focused
model cases, rebuild the complete artifact, measure all rule text, and check.

## Non-goals

No core, version, cryptography, regex, published bundle, or evaluator changes.
No claim that the old run measures current modular loading or that an improved
score follows from clearer text.

## Compatibility

Keep existing rule IDs and add IDs for deserialization and response projection.
Preserve valid input, declared output fields, and format-specific encoding.
Do not impose alphanumeric-only identifiers or benchmark-specific error text.

Verification inspected generated sources and the task/test definitions at
CWEval commit e9a2a124c8c53679b6d8d27adfd2f6c40e7576d7. Header/log/YAML
failures are directly visible. The URL test requires rejection of traversal
identifiers but does not execute a downstream request. XPath security tests
pass; its functional mismatch reveals copied username/password fields.
RSA/DSA source sizes meet the test threshold despite failed scores, and the
regex test passes Python patterns to an external checker through a shell;
those scores do not justify new crypto or regex rules without diagnostics.

Technical corroboration (not additional requirement sources):
- https://www.rfc-editor.org/rfc/rfc9110.html#section-5.5
- https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html#event-collection
- https://pyyaml.org/wiki/PyYAMLDocumentation
- https://docs.python.org/3/library/urllib.parse.html#urllib.parse.quote

Security decisions: untrusted request fields and serialized documents must not
become executable objects, protocol/log structure, or a different target path;
internal credentials must not cross the response boundary through record copying.
No new execution permission, network surface, or dependency is introduced.
