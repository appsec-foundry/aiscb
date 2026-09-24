# Why the core stays loaded

Some users would rather not have anything sit in the context permanently and ask whether the core could load only when a task needs it, as modules already do. This note explains why it stays static.

## What the core costs

The core is about 1,600 tokens (see [Structure and context budget](../README.md#structure-and-context-budget)). It is read once at session start from the assistant's instruction file and is not repeated per prompt or tool call. A session with three hundred tool calls pays the same as one with three; what grows in a long session is tool output.

Modules are already loaded on demand. Only the catalog and the loader instructions are always present.

## Loading the core situationally

All variants we considered have the same problem. The core matters most in tasks that do not look security-related, and whatever decides when to load it has to recognize those tasks in advance.

- A keyword or path hook adds the core when the prompt or a touched file looks security-related. The situations the core is for rarely look that way: making a failing test pass, pulling an issue or web page into the session, opening a log file or `.env`, adding a dependency. Preserve Security, Agentic Work, and Secrets would be missing exactly there.
- A hook before each tool call adds the core when the assistant edits or runs something. By then the design is settled, so Secure Design and Access Control arrive too late. It also pays the cost on every call, which makes long sessions more expensive.
- A short stub could tell the assistant to fetch the core before touching code, like the module loader. That leaves the decision to the model, and a model under pressure to finish is the least likely to fetch rules it has not seen. The stub itself stays in the context and has to describe when to load, so it saves a few hundred tokens at most.
- A session-start hook could load the core only in repositories that look like code. If it errs toward loading, it saves nothing. If it filters, scripts, infrastructure, and documentation work lose the core.

Hooks also fail open. If one does not start, times out, or is not installed in a client, the session runs without rules and nothing reports it. And once the core is in the context it stays there, so dynamic loading only postpones the cost for any session that needs it.

## Evidence

The recorded routing results (`make test-routing`) show no case in which the model failed to load a required module, so there is no reliability gap a hook would close. Nobody has measured whether the core makes tasks without security relevance worse. That would be the test to run before revisiting this note: the same tasks with and without the core.

## If you do not want the core in every session

Install the baseline per project instead of per user. Complete user installations configured for dynamic loading also have a [session switch](session-switch.md).
