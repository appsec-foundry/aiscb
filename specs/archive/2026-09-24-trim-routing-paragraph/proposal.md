# Replace the routing paragraph with its one non-duplicated sentence

## Problem

The paragraph under `Module Routing` in `baseline/aiscb-core.md` costs 87
`o200k_base` tokens and restates three things the assistant already has in
context. "Use only the bounded adapter catalog and loader" and "missing content
stops affected work" are in `aiscb-MODULES-001` directly above it. "Use this
loader before affected work ... if unavailable, stop affected work" is in the
adapter text that `scripts/install_policy.py` appends after the core. The
sentence about a complete integration describes the complete adapter text,
which says so itself ("Installation mode: complete").

The only content the paragraph adds is what the initial context holds and that
module bodies are not loaded ahead of affected work.

## Goal

Keep that content in one sentence of 31 tokens and drop the rest. The core goes
from 1,650 to 1,594 tokens.

## Non-goals

No change to `aiscb-MODULES-001`, to the adapter text, to the loader, or to the
selection behavior. No new version or baseline ID; the change waits in the
sources for the next release.

## Compatibility

An assistant reading the core alone, without an adapter, loses the sentence
that the adapter provides the catalog and loader. Every installation produced
by this repository includes that adapter text, and `aiscb-MODULES-001` already
stops affected work when catalog or loader is missing. Consumers that quoted
the removed sentences find their content in `aiscb-MODULES-001` and in the
adapter text.
