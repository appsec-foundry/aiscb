Our existing local assessment CLI should offer "Continue with Claude Code",
"Continue with Codex", and "Exit" after an analysis. The selected tool starts
in the assessed project with a short task pointing to the existing report,
the assessed revision, and what the user wants to do next. The report should
stay where it is; no separate export or repeated analysis is needed. Later,
the same handoff should be available through a continue subcommand.

The operator already uses the chosen tool for this project with its configured
provider and permissions. The handoff uses that same configuration and data
scope. Give me a concise proposed user flow, including how to show that the
working tree has changed since the assessment. This is design only; do not
launch a tool or implement the feature yet.
