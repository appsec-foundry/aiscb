# Name and scope the LLM application module

## Problem

The llm-features trigger can be mistaken for the coding assistant's own prompts,
tool calls, or code generation. Its name does not distinguish those activities
from LLM functionality in the system being built.

## Goal

Rename the module to aiscb:llm-applications and explicitly scope its trigger to
the system being built. Keep the existing security mechanisms and dependencies.
The user approved this recommendation after the trigger review and specification
proposal in the conversation.

## Non-goals

No new security controls, core expansion, baseline version change, publication,
or blanket restriction of other modules to application code. In particular,
supply-chain still applies to packages executed by the coding assistant.

## Compatibility

The modular profile is an unpublished branch trial. Replace the old module ID
and source filename in current references and dependent modules, without an alias.
Keep aiscb-LLM-001 and aiscb-0.1.16. Historical archived specifications retain
the names they recorded.
