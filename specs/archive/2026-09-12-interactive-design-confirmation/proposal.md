# Use interactive confirmation for design decisions

## Problem

`aiscb-OM-004` explicitly requires an interactive choice when available, but
`aiscb-OM-005` only asks for explicit confirmation. The reported three-digit
login-code plan therefore asks in prose even though some sessions show a
selection dialog. Existing design cases do not observe question-tool calls.
Another reported answer appends an aiscb paragraph repeating the persistent
secret-store decision instead of attributing it within the design explanation.

## Goal

Give design confirmations the same interactive-first mechanism as overrides,
with clear alternatives and no implied acceptance. Attribute the decision in
the question itself. Add focused evidence for tool use, text fallback, and
waiting when no answer was submitted.
Integrate attribution into the affected explanation; retain the final Security
note only for qualifying residual risks without repeating them.

## Non-goals

No mandatory notice heading, tool-specific baseline text, code-length rule,
new rule ID, or publication. The user subsequently approved the exact release
version `aiscb-0.1.15`. Do not change when a decision
requires confirmation or make ordinary secure defaults require approval.

## Compatibility

Design confirmations gain an explicit choice mechanism. Text remains the
fallback when no permitted interactive tool is available. Baseline size and
token count must be remeasured. The signed bundle needs maintainer release
work after the content change; the old signature cannot cover the new text.
