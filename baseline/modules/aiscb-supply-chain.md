# Software Supply Chain Module

`module-id: aiscb:supply-chain`. Load when adding, updating, locking, or deploying packages, CI actions, container images, external scripts, build tools, installers, or external downloads; or executing packages or external tools not established by the project. Routine source reads and unchanged established test, build, or loader commands alone do not trigger this module.

## Software Supply Chain

- **[aiscb-DEPS-001] Dependencies:** Prefer existing dependencies. Before adding or updating a package, verify its exact name, selected version, expected authoritative upstream source, and known vulnerabilities using current authoritative information; do this before executing a package not established by the project. Treat external CI actions, container images, scripts, and build tools as dependencies: pin them to immutable identifiers and verify integrity or authenticity with the ecosystem's established mechanism before execution. Follow the project workflow, review manifest, lockfile, transitive changes, and install scripts, and do not run unreviewed install scripts. Report missing safeguards encountered in scope in an existing application; in greenfield work, commit a lockfile and use frozen CI and deployment installs, such as `npm ci` or `pip install --require-hashes`, plus dependency scanning by default.
