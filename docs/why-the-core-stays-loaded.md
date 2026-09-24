# Why the core stays loaded

A common objection to the baseline is that nothing should sit in the context permanently, and that the core could load only when a task needs it, the way modules already do. This note records why the core stays static and what each dynamic variant would cost.

## What the core costs today

The core is about 1,600 tokens (see [Structure and context budget](../README.md#structure-and-context-budget)). It enters the context once, at session start, through the assistant's instruction file. It is not re-injected per prompt or per tool call, so a session with three hundred tool calls pays the same as one with three. What grows in a long session is tool output, not the core.

Modules are already situational: only the catalog and the loader instructions are always present, and module bodies stay on disk until the assistant selects them.

## Dynamic variants and why they do not help

Each variant below was considered as a replacement for the static core. They share one weakness: the core exists for tasks that do not look security-related, and every trigger that decides "this task needs the rules" has to recognize such tasks in advance.

- **Keyword or path hook.** A prompt-submit hook injects the core when the prompt, or a file the assistant touches, looks security-related. But the situations the core is for rarely carry such signals: making a failing test pass (Preserve Security), pulling an issue or web page into the session (Agentic Work), opening a log file or an `.env` (Secrets), adding a dependency (supply chain). A hook cannot recognize those, and these are the rules that matter most.
- **Per-tool-call hook.** A pre-tool-use hook adds the core whenever the assistant edits or runs something. By then the design is decided; the rules that shape the design (Secure Design, Access Control, Design decisions) come too late. It also pays the injection cost on every call instead of once, which makes long sessions more expensive, not cheaper.
- **Routing stub.** A short always-on stub tells the assistant to fetch the core before touching code, like the module loader. This moves the decision to the model, which is exactly where the baseline does not want it: a model under pressure to finish is the one least likely to fetch rules it has not yet seen. The stub stays in the context anyway, and to trigger reliably it has to describe when to load, so the saving shrinks to a few hundred tokens.
- **Session-start check.** A start hook loads the core only in repositories that look like code. If it errs toward loading, it loads almost always and saves nothing. If it filters, it drops the core for scripts, infrastructure, and documentation work that has side effects.

Two further points apply to every hook-based variant:

- **Hooks fail open.** If a hook does not start, times out, or is not installed in a client, the session runs without rules and nothing reports it. A static instruction file has no such failure mode.
- **Nothing leaves the context.** Once the core is injected, it stays for the rest of the session. Dynamic loading can only postpone the cost, never reduce it for a session that needs the rules.

## What was measured

The routing tests (`make test-routing`) currently pass for all cases, including scope changes and context loss, so there is no evidence that the model forgets to load modules and no reliability gap that a hook would close. There is also no measurement showing that the core degrades tasks without security relevance. If that concern comes up, the test is straightforward: run cases without security relevance with and without the core and compare. A result there would be the first reason to revisit this note.

## If you do not want the core in every session

Install the baseline per project instead of per user, so it applies only where you decided it should. Complete user installations configured for dynamic loading also have a [session switch](session-switch.md).
