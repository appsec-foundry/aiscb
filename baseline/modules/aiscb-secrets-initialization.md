# Secrets and Initialization Module

`module-id: aiscb:secrets-initialization`. Load for credentials, passwords, tokens,
keys, signing, secret rotation, first-start setup, seed data, demo accounts, or
prototype initialization.

## Secrets and Initialization

- **[aiscb-BOOTSTRAP-001] Credentials and Initialization:** Never ship, seed, initialize, display, or document working default, demo, or shared credentials through bundled data, setup, fixtures, UI, or docs, except when the user explicitly requests seed accounts for a clearly marked local-only prototype. Such accounts use CSPRNG-generated credentials, never fixed, memorable, or dictionary-style passwords; disclose them to the operator only through the reply, an interactive console, or a restricted file, never a tracked artifact. Without explicit throwaway local-only framing, the result stays production-deployable and requested seeded accounts are reported in the **Security note (aiscb)** as what keeps it out of production. Bootstrap production-capable software with unique externally supplied credentials or one-time activation. Require the first administrator credential from external configuration and fail startup if absent, or generate it once at first start and disclose it once through an interactive console or restricted file, never UI or logs. A placeholder the operator is merely advised to change is still a shipped default. Never substitute an ephemeral key for a required persistent security key.
- **[aiscb-SECRETTESTS-001] Secret Lifecycle Tests:** For greenfield deployable applications, or existing applications when initialization or secrets change, verify missing or invalid required configuration blocks startup and clean initialization creates no known credential or unintended privileged account. Tests and fixtures may use artificial credentials only when isolated and non-runnable outside the test context.
