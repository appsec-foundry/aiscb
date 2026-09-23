# Requirements

## SPLIT-001 Preserve controls

Source: user approval of the measured split and baseline/modules/aiscb-web-auth-crypto.md.

Retain every existing security clause; split authentication mechanisms and tests
without weakening web, authentication, cryptography or webhook controls.

Acceptance: clause conservation, unique rule IDs and complete assembly pass.

## SPLIT-002 Select bounded modules

Source: user request and baseline/aiscb-core.md, aiscb-MODULES-001.

Offer web, authentication and cryptography in the catalog. Authentication loads
cryptography and data-handling as dependencies. Cryptography loads
secrets-initialization. Webhooks match web and cryptography.

Acceptance: verified loading delivers dependencies once, obsolete IDs fail closed,
and four focused model tasks record module delivery before the planned design.

## SPLIT-003 Measure and preserve distribution

Source: repository AGENTS.md and user instruction to run only meaningful tests.

Recompute all source sizes and token counts, update live references and retain
baseline version and published installation pins.

Acceptance: make check passes; measurements distinguish rule text from discovery
and loader context; model evidence is limited to the four scoped routing tasks.


## SPLIT-004 Close observed dependency gaps

Source: user follow-up "dann fixe die", the four recorded routing results,
and existing credentials/key, data-handling and module-selection requirements.

The verified loader must supply secrets-initialization whenever cryptography
is selected, and data-handling whenever authentication is selected. Authentication
continues to require cryptography and thus receives secrets transitively.

Acceptance: the minimal and recorded selections from the failed tasks deliver
all expected modules without a second model decision; missing required content
still refuses loading. Preserve the original failed model evidence. Verify the
changed dependency closure deterministically rather than rerunning the models.
