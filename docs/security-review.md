# Independent security review with AISCB

Use the optional [security-review skill example](../examples/security-review/aiscb-security-review/SKILL.md)
to review a finished change in a fresh context. The implementer keeps the AISCB
core and relevant modules. The reviewer uses the same policy and returns
findings; the implementer makes corrections.

This is an experimental, tool-neutral workflow example. The normal installer
does not install or activate it. It adds no normative baseline rules and does
not run after every edit. The [architecture analysis](security-review-analysis.md)
records the decision for Option B and the proposed evaluation.

## Use the example

In the implementation session, request:

> Use the AISCB security-review skill at
> `examples/security-review/aiscb-security-review/SKILL.md` to prepare and run
> an independent review of this change. Keep the baseline active. The reviewer
> should report findings and leave corrections to the implementer.

Identify the change and requirements if the session does not already have them.
The skill prepares a [handoff](../examples/security-review/aiscb-security-review/references/handoff.md)
and passes the [reviewer instructions](../examples/security-review/aiscb-security-review/references/reviewer.md)
to one fresh context when the host supports authorized delegation without the
implementation conversation. It does not infer that a skill invocation itself
creates a new context.

Otherwise start a new session manually, with access to the same stable code and
policy snapshots, and give it the completed handoff and reviewer instructions.
This manual path does not depend on a particular CLI, subagent API or skill
discovery mechanism. Do not resume the implementation conversation as the
reviewer. A path-based request requires the client to actually read the file.

Keep the reviewed tree stable until the result returns. A new code revision
needs a new review result. Existing user-level policy can still be inherited by
a new session; verify its compatibility with the pinned project policy rather
than assuming a fresh conversation selects the right release.

## Permissions and results

The reviewer reads code and loads policy. Host permissions should enforce
read-only project access where available; the prompt is not an enforcement
mechanism. Running project tests needs a separately available isolated execution
boundary because tests can modify files or run arbitrary project code. Static
review remains useful when execution is unavailable, but the result must state
the material verification gaps.

An interrupted review, policy mismatch or missing required module is an
incomplete review, not a pass. Findings do not automatically authorize broader
changes or create a new human approval requirement. Existing AISCB and project
decision rules still apply. A reviewer does not replace tests, scanners, CI
controls or the implementer's own final review.

## Validation status

Local static validation checked the skill frontmatter, resolved the example's
relative links, and matched all 48 rule groups in the analysis against the
catalog. Recomputed baseline measurements match the README: 10,467 bytes /
2,010 tokens for the core and 31,066 bytes / 6,004 tokens for complete output;
every cataloged module also matches. No normative source changed.

`make check` passed outside the restricted sandbox. The first sandboxed run
failed at the existing CSRF oracle's local HTTP fixture; the unchanged test
passed on the unrestricted local run. Neither run called a model.

The example adds the following source text, measured with `o200k_base`:

| Artifact | Bytes | Tokens |
| --- | ---: | ---: |
| Coordinator SKILL.md | 4,063 | 739 |
| Handoff template | 2,256 | 410 |
| Reviewer instructions | 4,298 | 769 |

These are file-text counts, not total context or billed usage. The coordinator
reads the references to prepare the request; the reviewer receives its own
instructions and the completed handoff, plus policy and code. Filled-in fields,
client wrappers, skill discovery and repeated model requests add overhead.

The example has no client-specific launcher, automatic installer integration,
repair loop or four-arm experiment runner. Native delegation, read-only host
enforcement and policy delivery must be verified on the selected client before
claiming that integration works. Static skill validation cannot establish
independence, finding quality or model compliance.

The proposed next experiment compares no baseline, modular AISCB, and modular
AISCB plus reviewer on three small scenarios. Paid model runs require a separate
explicit budget decision. A reduced implementation policy is deferred until its
exact differences and approval are defined.
