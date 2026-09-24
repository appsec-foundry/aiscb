# Web, authentication and cryptography split

The development catalog replaces `aiscb:web-auth-crypto` with:

- `aiscb:web`: browser and transport controls, including browser tests.
- `aiscb:authentication`: account/session controls, OAuth and password boundaries, and authentication tests. Requires `aiscb:cryptography` and `aiscb:data-handling`.
- `aiscb:cryptography`: established mechanisms, cryptographic primitives and signed webhook replay protection. Requires `aiscb:secrets-initialization`. Webhooks match both web and cryptography.

Security clauses are preserved. The former mixed mechanisms and tests groups are split using new IDs `aiscb-AUTHMECHANISMS-001` and `aiscb-AUTHTESTS-001`. The baseline version and published bootstrap pins are unchanged. Existing installed immutable snapshots retain their previous catalog; the new catalog rejects the retired ID.

## Context measurements

Historical split measurement, before compact loader receipts, with `o200k_base`: installed core, full catalog and loader instructions, plus required module bodies and verification output once. Paths and the installation digest in initial instructions are normalized identically. Other task-relevant modules are included equally in both variants. These are policy payload counts, not total model usage or peak session context.

| Task | Combined | Split | Difference |
| --- | ---: | ---: | ---: |
| unrelated | 2,319 | 2,346 | +27 |
| web | 3,423 | 2,783 | -640 |
| authentication | 4,277 | 4,085 | -192 |
| cryptography | 3,837 | 3,055 | -782 |
| mixed | 4,277 | 4,522 | +245 |

Web assumes a Referrer-Policy change on a public response. Authentication assumes an internal shared-session adapter and includes data-handling and secrets. Cryptography assumes an in-memory helper with external keys and includes secrets. Mixed assumes browser login and includes data-handling and secrets. Unrelated work loads no modules. These sets are explicit measurement assumptions, not observed module selection.

Narrow Web and cryptography work benefits most. Browser login loads all three and costs more. Complete rule text grows from 5,352 to 5,455 tokens; the always-on core stays at 1,656. Discovery remains additional context.

### Compact loader receipts

The current repository and installed loaders retain the verified module ID and
release but omit the per-module hash from their success output. Full integrity
verification still runs before output; the trusted digest in the installed
loader command is unchanged. Before whitespace cleanup, the same split-module
sets and normalization gave:

| Task | Full-hash receipts | Compact receipts | Tokens saved |
| --- | ---: | ---: | ---: |
| unrelated | 2,346 | 2,346 | 0 |
| web | 2,783 | 2,744 | 39 |
| authentication | 4,085 | 3,921 | 164 |
| cryptography | 3,055 | 2,972 | 83 |
| mixed | 4,522 | 4,319 | 203 |

Core, module and generated complete rule-text sizes were unchanged by the receipt
change. This output-only change also applies to complete installations;
it does not change the historical model-run evidence below.

After removing purely visual line breaks within paragraphs, the same normalized
compact-receipt payloads are 2,340 tokens (unrelated), 2,738 (web), 3,912
(authentication), 2,965 (cryptography), and 4,310 (mixed). Words and rendered
Markdown structure are unchanged. Current rule text is 1,650 tokens for core
and 5,436 for the complete baseline; README lists all module measurements.

### Duplicate-content review

Dependency traversal emits each module once per invocation; a later invocation
still emits full bodies so that loading works after context loss. Installer
checks cover inherited complete policies and additional automatic complete
rules. The repository's `AGENTS.md` references the core without embedding it;
`CLAUDE.md` imports AGENTS and the core once each, and the Copilot entry points
to the same read-and-load workflow. These source checks do not establish how
often every client sends instructions in a real session. No further deduplication
or persistent loaded-state cache was added.

## Verification

Local checks reconstruct all original security clauses, enforce unique IDs and validate narrow loads, dependency deduplication, obsolete-ID refusal, and rejection of missing, failed or late routing evidence. Existing installer, gateway and organization adapters are covered by make check.

Focused model evidence is recorded in the change specification and tests/results/split-20260923/. Four planning tasks use the production modular installer and verified loader through restricted fixture tools. They check delivered modules before the first plan write; they cannot prove loading before internal reasoning, implementation security or reliability across repeated runs and other clients. No application code or broad comparison matrix is executed for this split.


Before the dependency fix: Sonnet 4.6, one run per task on 2026-09-23, with the frozen candidate snapshot:

| Task | New split modules | Other required modules missing | Full routing check |
| --- | --- | --- | --- |
| Web | web | None | Pass |
| Authentication | authentication, cryptography | secrets-initialization | Fail |
| Cryptography | cryptography | secrets-initialization | Fail |
| Mixed | web, authentication, cryptography | data-handling, secrets-initialization | Fail |

All four tasks completed and wrote their plans. The new thematic selections were
correct, but only one task satisfied the complete expected module set. No retries
or prompt tuning followed. There is no matched pre-split model control, so these
results establish neither a routing regression nor equal reliability. They leave
cross-module completeness unresolved; the deterministic split and integrity checks
must not be reported as reliable end-to-end module selection.


## Fix for omitted supporting modules

The user requested a fix after reviewing the initial failures. Cryptography now
requires secrets-initialization; authentication requires cryptography and
data-handling. This makes the verified loader supply supporting rules without a
separate model choice. It also loads secrets for purely public cryptographic
operations and data-handling for narrowly scoped authentication changes; that
additional context is deliberate, and each rule still applies only in its scope.

The regression check replays the three successful-but-incomplete module sets
from the failed tasks through the corrected real loader. Each now contains all
previously missing rules exactly once; missing secrets content still refuses
loading. These deterministic checks pass. No post-fix model runs were made;
the original 1/4 model result remains recorded, not relabeled as a model pass.
The correction prevents these omissions once the relevant parent module is
selected; it cannot force a model to select that parent or follow the rules.
