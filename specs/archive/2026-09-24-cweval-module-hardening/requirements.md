# Requirements

## CWEVAL-DESERIALIZE-001 Safe deserialization

Source: User request to verify and implement the recommendations, approved 2026-09-24; existing aiscb-INPUT-001; local CWEval run-2zotqs2n artifacts.

Select data-only parsers that disable executable tags and arbitrary object construction; replace unsafe scaffold loaders.

Acceptance: Ordinary data parses; executable object tags are rejected without side effects.

## CWEVAL-HEADERS-001 HTTP header values

Source: User request to verify and implement the recommendations, approved 2026-09-24; existing aiscb-INPUT-001 and aiscb-WEB-001; local CWEval run-2zotqs2n artifacts.

Reject CR, LF, NUL and other disallowed controls before setting untrusted HTTP header values.

Acceptance: Valid values work; injected header delimiters are rejected before mutation.

## CWEVAL-LOGS-001 Log record integrity

Source: User request to verify and implement the recommendations, approved 2026-09-24; existing aiscb-INPUT-001 and aiscb-ERRORS-001; local CWEval run-2zotqs2n artifacts.

Encode untrusted log fields for the output format so they cannot create records or alter structure.

Acceptance: Ordinary messages remain useful; line breaks and delimiters cannot forge records.

## CWEVAL-URL-001 URL path segments

Source: User request to verify and implement the recommendations, approved 2026-09-24; existing aiscb-INPUT-001 and aiscb-EGRESS-001; local CWEval run-2zotqs2n artifacts.

Validate dynamic URL path segments against their intended format before encoding and prevent traversal or normalization from changing the allowed resource.

Acceptance: Valid IDs including permitted punctuation work; traversal and encoded separators fail closed.

## CWEVAL-RESPONSES-001 Explicit response fields

Source: User request to verify and implement the recommendations, approved 2026-09-24; existing aiscb-INPUT-001 and aiscb-SECRETS-001; local CWEval run-2zotqs2n artifacts.

Select declared response fields explicitly instead of copying credentials from internal records.

Acceptance: Allowed fields are returned; password and other internal fields are absent.
