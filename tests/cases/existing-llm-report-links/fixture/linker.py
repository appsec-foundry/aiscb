"""Deterministic numbering and linking of survey and verification findings."""


def number_survey(threats):
    """Assign the survey IDs T-001, T-002, ... in report order."""
    return [dict(threat, id=f"T-{index:03d}") for index, threat in enumerate(threats, start=1)]


def link(survey, findings):
    """Link each verification finding to survey findings with its CWE within three lines."""
    for finding in findings:
        matches = [
            threat["id"]
            for threat in survey
            if threat["cwe"] == finding["cwe"]
            and threat["file"] == finding["file"]
            and abs(threat["line"] - finding["line"]) <= 3
        ]
        if matches:
            finding["survey_finding_ids"] = matches
    return findings
