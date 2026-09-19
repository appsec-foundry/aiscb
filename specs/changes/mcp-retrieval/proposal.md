# MCP and retrieval boundaries

## Problem

Generic agent, input, and authorization rules leave MCP integration and
retrieval/memory boundaries underspecified. More modules also increase routing
and rollout complexity; packaging tests alone do not prove model selection.

## Goal

Implement the user's approved assessment: two narrowly triggered modules,
file and outbound-request mechanisms in data-boundaries, and webhook replay
protection in web-auth. Verify installation and document rollout limitations.

## Non-goals

No separate file-processing, outbound-integrations, or specification module;
no MCP server or remote policy loader implementation; no version change,
release publication, or claim of model-tested routing.

## Compatibility

Keep aiscb-0.1.16 and generate complete output from the same catalog. MCP does
not require agent-systems; retrieval-memory requires llm-features. Existing
signed remote distribution remains complete-only until a separate approved
distribution change. Local updates must not mix releases across tool entries.
