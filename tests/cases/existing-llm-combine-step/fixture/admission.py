"""Existing admission of model-written finding text."""

TEXT_FIELDS = {"title", "scenario", "remediation"}


def _text(value, low, high):
    return isinstance(value, str) and low <= len(value) <= high


def admit_text(raw):
    """Admit the title, scenario and remediation a model wrote, or raise ValueError."""
    if not isinstance(raw, dict) or set(raw) != TEXT_FIELDS:
        raise ValueError("Invalid finding text")
    if not _text(raw["title"], 8, 200) or not _text(raw["scenario"], 40, 4000):
        raise ValueError("Invalid title or scenario")
    remediation = raw["remediation"]
    if not isinstance(remediation, dict) or set(remediation) != {"steps", "verification"}:
        raise ValueError("Invalid remediation")
    steps = remediation["steps"]
    if (not isinstance(steps, list) or not 2 <= len(steps) <= 12
            or not all(_text(step, 4, 600) for step in steps)
            or not _text(remediation["verification"], 10, 1000)):
        raise ValueError("Invalid remediation")
    return {
        "title": raw["title"],
        "scenario": raw["scenario"],
        "remediation": {"steps": list(steps), "verification": remediation["verification"]},
    }
