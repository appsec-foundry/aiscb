# Tasks

- [x] Apply MODULE-NAMES-001 names and MODULE-NAMES-002 triggers. Renamed
  seven IDs/files; retained llm-applications and supply-chain. Rule IDs and
  security rule bodies match the previous source, except the llm-agents reference.
- [x] Update dependencies, current specs, documentation and generated adapters.
  Historical archived specs and published bootstrap fixtures remain unchanged.
- [x] Verify every official module through the exact installed command for all
  three entry points, both with and without an organization overlay. Verify
  source and installed loaders reject all seven obsolete IDs without partial
  output; shared dependencies occur once. Catalog and changed introductions agree.
- [x] Rebuild complete output and update README and handoff context tables and
  budget comparisons. Verified all byte sizes and o200k_base counts below.
- [x] Run make check and review the diff against MODULE-NAMES-003. Passed,
  including immutable release staging, manifest/bootstrap checks and SSH
  signing/verification with temporary test keys. No release was published.
- [x] Record model evidence: no model-selection runs were performed. The main
  harness installs complete policy; the organization experiment exercises a
  synthetic pack, so neither tests this catalog's selection. Added positive
  and negative scenarios to docs/local-policy-installation.md; actual-client
  selection remains unverified.
- [x] Archive this change under 2026-09-19-clear-module-names.

| Artifact | Bytes | Tokens |
| --- | ---: | ---: |
| Always-on core | 7,780 | 1,558 |
| aiscb:web-auth-crypto | 5,189 | 1,040 |
| aiscb:data-handling | 1,720 | 344 |
| aiscb:secrets-initialization | 1,900 | 351 |
| aiscb:supply-chain | 1,173 | 223 |
| aiscb:deployment-environments | 1,659 | 311 |
| aiscb:llm-applications | 1,252 | 247 |
| aiscb:llm-agents | 2,033 | 401 |
| aiscb:llm-retrieval-memory | 1,666 | 325 |
| aiscb:mcp-clients-servers | 2,225 | 415 |
| Complete baseline | 26,606 | 5,215 |
