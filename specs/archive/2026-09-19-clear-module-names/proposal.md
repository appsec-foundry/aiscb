# Clear module names and loading triggers

## Problem

Several module names hide their scope, and retrieval/memory and deployment
triggers can match unrelated work. Names and discovery need to agree.

## Goal

Apply the user's approved names and clarify loading descriptions, retaining
supply-chain for packages, CI actions, images, build tools and downloads.
Keep all adapters, dependencies, tests and current documentation aligned.

## Non-goals

No new security controls, changed rule IDs, baseline version change, release
publication or new override mechanism. Keep aiscb-0.1.16 and the existing
published bootstrap pins. Do not rewrite historical archived specifications.

## Compatibility

The modular interface is an unpublished branch trial. Replace seven module IDs
and their filenames without aliases; keep llm-applications and supply-chain.
Existing local snapshots retain their own files and loader references. Reinstall
from this checkout to adopt the new names in a fresh session.
