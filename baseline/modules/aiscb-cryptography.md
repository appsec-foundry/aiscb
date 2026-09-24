# Cryptography Module

`module-id: aiscb:cryptography`. Load for: Encryption, hashing, signatures, random generation, secret comparison, password hashing, signed tokens, or webhooks. Requires `aiscb:secrets-initialization`.

## Cryptography

- **[aiscb-MECHANISMS-001] Proven Mechanisms:** Reuse established sound mechanisms and maintained libraries; never hand-roll cryptography, authentication, or sessions. Use vetted algorithms and a CSPRNG; no MD5/SHA-1 for security, insecure token RNGs, or fast password hashes. Use Argon2, scrypt, bcrypt, or PBKDF2 with sound parameters. Compare secrets, tokens, and MACs in constant time, and verify inbound webhook signatures before acting.
- **[aiscb-WEBHOOK-001] Webhook Replay Protection:** Verify the provider's signature over its prescribed bytes before processing. Enforce authenticated timestamp freshness where supported and atomically deduplicate authenticated event IDs or use an equivalent provider-supported replay mechanism before side effects. Test forged, stale, concurrent duplicate, and retried deliveries without blocking legitimate first delivery.
