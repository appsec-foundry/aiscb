# Session switch

`AISCB_DISABLE=1` omits the baseline security instructions supplied by each
installation set up for dynamic loading, in guided setup or with
`install.py --session-switch`. Unset the variable or use `0` to load them.
Other values block the prompt. Start a fresh session: the switch cannot remove
instructions from conversation history.

## Scope

Setup supports Claude Code and Codex at user and project level. Guided setup
asks how they load the baseline; static loading is the default, and tools added
later load it the way the installation already does. For an existing
installation, add `claude` or `codex` to the `--session-switch` command to
select one tool. Existing installer-managed links are migrated; foreign links,
combined instruction files, and customized loader hooks are refused. Other
instructions and permissions are preserved.

A derived baseline works when it is the managed `secure-coding-baseline.md`
file with one valid `baseline-id`. Separate overlays remain active. The
[organization bundle example](../examples/organization-bundle/) uses its own
adapters and installer, so this switch does not disable that package, its
overlay, or its requirement packs. Gateway and managed policy injections also
remain active.

## If the baseline still appears

- Check both installation scopes and any manual imports.
- Look for `blocked session switch` in the setup output, fix the named cause,
  and run `install.py --session-switch` again.
- Start a new conversation instead of resuming one.
- In Codex, trust the new hooks with `/hooks`. After a helper update, review
  its changed code and renew trust when Codex requests it.
- A session must inherit the variable, including any backend process that
  runs its hooks. Setting it in an unrelated terminal changes nothing.

Startup hooks supply four bounded parts of the baseline. A prompt hook rejects
invalid values or an unreadable baseline. If hook context is missing, the
instruction file tells the assistant to execute the loader and stop on failure;
that fallback relies on the assistant following instructions. `baseline?`
reports visible context, not proof of compliance. Normal setup retains the mode;
uninstall removes the managed loader and hooks.

## Verification

`make check` covers loading, migration, preservation of other settings,
parallel sessions, invalid values, and removal without model calls.

Run `python3 scripts/probe_session_switch.py` for an additional check against
installed CLIs (`--tools claude` or `--tools codex` selects one). It creates
temporary installations and captures requests to a loopback API dummy. No real
credentials or models are used. The probe needs permission to bind a local
socket. Its Codex hook-trust bypass applies only to its own generated fixtures;
normal setup never bypasses hook trust.

The probe tests Claude's `-p` and Codex's `exec` paths. It checks the complete
baseline and unrelated instructions in the request, rather than trusting an
assistant's answer. It does not test model compliance, graphical clients, or
environment forwarding by a separately running backend.
