# Upgrade an existing organization overlay

From the repository containing your organization's `overlay.md`, run the
upgrade script from a reviewed current aiscb checkout. No options are needed:

```bash
python3 /path/to/aiscb/scripts/upgrade_organization.py
```

Replace `/path/to/aiscb` with your local checkout path. The tool uses that
checkout's baseline; it does not download a release or contact a model.
It needs Python 3.10+ and the full checkout, not just a copied script.

The tool reads `overlay.md`, an optional `catalog.json`, and policy files under
`packs/` and `blueprints/`. It creates `.aiscb-upgrade/` in the organization
repository with candidate sources, `upgrade.diff`, and `upgrade-report.json`.
Original files and active client installations stay unchanged. Existing output
is never overwritten; move a previous draft elsewhere before running again.
The report and diff can contain internal policy: review their contents before
committing or sharing them.

The next organization patch version is proposed automatically, for example
`acme-sec-1.0.0` becomes `acme-sec-1.0.1`. This is a draft, not a published
organization release. A different version can be supplied with
`--organization-id acme-sec-2.0.0`.

## What gets upgraded

- The recognized complete-baseline import becomes a core import, the declared
  upstream version becomes the checkout version, and `On baseline?` becomes
  `On aiscb?` (both questions are backtick-delimited in the source).
- Legacy pack IDs such as `acme-authentication` become `acme:authentication`
  when the namespace follows the old example's organization identity or is
  declared in the overlay. Otherwise, the tool requests an explicit namespace.
- Exact routing and authority clauses from the historical `0.1.15` example
  become the current shared routing contract. Customized clauses are preserved
  and flagged for review. Domain rules and blueprint values are retained.
- An overlay without modules gets an empty organization catalog. Its rules
  remain always loaded; official aiscb modules still load on demand.

An arbitrary combined baseline/overlay file cannot be separated reliably.
Embedded aiscb rule definitions, unknown rule references, custom imports and
unrecognized old loading references require manual review. The tool does not
split organization prose into modules or decide whether its meaning conflicts
with newer baseline rules. Historical versions other than the tested `0.1.15`
example are handled only where their format matches these recognized cases.

Every file under `packs/` must be registered. Unlisted files, including files
in subdirectories, stay in the draft and block readiness; the current catalog
format requires module files directly under `packs/`.

## Review and activate

Exit `0` means the candidate passes the current bundle builder and organization
installer validation and no recognized migration blockers remain. It still
requires a policy review. Exit `2` means a draft and report were produced but
manual corrections are needed. Exit `1` means invalid or unsafe input/output
was refused. With `--check`, no draft is written.

Review the diff and report, resolve open points, and approve the organization
rules against the new baseline. Then build and distribute the reviewed sources
using the [organization package workflow](local-policy-installation.md#add-organization-policy),
using `.aiscb-upgrade/` as the builder's `--source`. Preserve the previous
approved source and package for rollback. Do not run the old organization's
`build.py`: use the builder from the reviewed current aiscb checkout.

Close agent sessions before replacing old integration references. The existing
installer's `--migrate` supports verified managed complete installations;
custom integrations need a reviewed manual transition. Check fresh sessions
in each actual CLI/IDE used: core, organization overlay and discovery initially;
matching aiscb and organization modules only when needed. Also test refused
loader execution and damaged package files before rollout.

The upgrade command is available in the development checkout. It is not part
of the already published `0.1.17` installer.
