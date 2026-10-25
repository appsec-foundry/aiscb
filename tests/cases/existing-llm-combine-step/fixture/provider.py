"""Configured model provider. Every role sends its prompt to the same provider."""

# Survey and verification send source excerpts; merge receives finding titles to
# group duplicates. All three use the provider configured for the assessment.
ROLES = {"survey": "analysis_model", "verify": "analysis_model", "merge": "merger_model"}


def complete(role, prompt):
    """Send a prompt for a role to the configured provider and return its parsed JSON reply."""
    if role not in ROLES:
        raise ValueError("Unknown role")
    raise RuntimeError("No provider configured")
