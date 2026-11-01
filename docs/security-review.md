# Independent security review with AISCB

Use the optional [security-review skill example](../examples/security-review/aiscb-security-review/SKILL.md)
to review a finished change in a fresh context. The implementer keeps the AISCB
core and relevant modules. The reviewer uses the same policy and returns
findings; the implementer makes corrections.

This is an experimental, tool-neutral workflow example. The normal installer
does not install or activate it. It adds no normative baseline rules and does
not run after every edit. The [architecture analysis](security-review-analysis.md)
records the decision for Option B, the validation and the proposed evaluation.

## Use the example

In the implementation session, request:

> Use the AISCB security-review skill at
> `examples/security-review/aiscb-security-review/SKILL.md` to prepare and run
> an independent review of this change. Keep the baseline active. The reviewer
> should report findings and leave corrections to the implementer.

The skill prepares a [handoff](../examples/security-review/aiscb-security-review/references/handoff.md)
and uses the [reviewer instructions](../examples/security-review/aiscb-security-review/references/reviewer.md).

| Situation | Result |
| --- | --- |
| You asked it to start the review, and the host can start an agent without the implementation conversation | One fresh reviewer starts |
| Otherwise | Status **prepared**: start a new session with the same stable code and policy, then give it the completed handoff and reviewer instructions |

Before the review:

- Identify the change and requirements if the session does not already have them.
- Make sure the client actually reads the skill file.
- Keep the reviewed tree stable until the result returns.
- Do not resume the implementation conversation as the reviewer.
- Check that inherited user-level policy is compatible with the pinned project
  policy. A fresh conversation does not select the right release by itself.

## Permissions

- The reviewer reads code and loads policy. Host permissions should enforce
  read-only project access; a prompt enforces nothing.
- If the host cannot enforce access, the result states **not enforced**.
- Running project tests needs a separate isolated environment because tests can
  modify files or run arbitrary project code.
- Without one, the review stays static and the result states the material gaps.

## Results

- **Incomplete:** An interrupted review, policy mismatch or missing required module
  is not a pass.
- **New code:** A new revision needs a new review result.
- **Findings:** They do not authorize broader changes or create a new human approval
  requirement. Existing AISCB and project decision rules still apply.
- **Limits:** A reviewer does not replace tests, scanners, CI controls or the
  implementer's own final review.

Verify native delegation, read-only enforcement and policy delivery on your client
before claiming that the integration works.
