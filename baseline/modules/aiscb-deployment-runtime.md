# Deployment and Runtime Module

`module-id: aiscb:deployment-runtime`. Load for public or network exposure, TLS
termination, proxying, containers, CI permissions, production configuration,
startup requirements, debug behavior, development servers, mocks, or fixtures.

## Deployment and Runtime

- **[aiscb-DEPLOYMENT-001] Least-Privilege Runtime:** Give CI jobs read-only tokens by default, keep untrusted pull-request code out of workflows holding write access or secrets, and run containers as a non-root user. Production configuration must enable applicable platform protections. Require security-critical configuration at startup and fail closed when it is missing, invalid, or ambiguous.
- **[aiscb-ENV-001] Production vs. Development:** Keep mocks, bypasses, debug modes, development servers, and weakened settings out of production. Development tooling means mocks, fixtures, seed data, and debug output; a switch that turns off authentication, authorization, CSRF, or transport security belongs nowhere. Development tooling must be opt-in and non-public; treat uncertain contexts as production. Documentation must distinguish local development and provide a production-safe start or deployment path.
- **[aiscb-DEPLOYTESTS-001] Deployment Tests:** For greenfield deployable applications, or existing applications when these areas change, verify missing or invalid required configuration blocks startup and applicable production controls operate. Exercise the production-safe start or deployment path rather than inferring it from development behavior.
