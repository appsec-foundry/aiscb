"""Findings register built from survey and verification findings."""

SEVERITY = ("low", "medium", "high", "critical")


def same_issue(survey_finding, verification_finding):
    """Findings with the same CWE within three lines of each other describe one issue."""
    return survey_finding["cwe"] == verification_finding["cwe"] and any(
        a["file"] == b["file"] and abs(a["line"] - b["line"]) <= 3
        for a in survey_finding["locations"]
        for b in verification_finding["locations"]
    )


def entry(finding):
    return dict(finding, ids=[finding["id"]], methods=[finding["method"]])


def build_register(survey, verification, complete):
    """Return one register entry per finding."""
    return [entry(finding) for finding in survey + verification]
