"""Existing admission of model verification output and of the assembled result."""

import re

FINDING_ID = re.compile(r"V-[0-9]{3,}")
SURVEY_ID = re.compile(r"T-[0-9]{3,}")
CWE = re.compile(r"CWE-[0-9]{1,5}")
FINDING_FIELDS = {"id", "cwe", "file", "line", "reason"}


def admit_finding(raw):
    """Admit one verification finding produced by the model, or raise ValueError."""
    if not isinstance(raw, dict) or set(raw) != FINDING_FIELDS:
        raise ValueError("Invalid verification finding")
    if not isinstance(raw["id"], str) or not FINDING_ID.fullmatch(raw["id"]):
        raise ValueError("Invalid finding id")
    if not isinstance(raw["cwe"], str) or not CWE.fullmatch(raw["cwe"]):
        raise ValueError("Invalid CWE")
    path = raw["file"]
    if not isinstance(path, str) or not path or path.startswith("/") or ".." in path.split("/"):
        raise ValueError("Invalid file")
    if type(raw["line"]) is not int or raw["line"] < 1:
        raise ValueError("Invalid line")
    if not isinstance(raw["reason"], str) or not 0 < len(raw["reason"]) <= 500:
        raise ValueError("Invalid reason")
    return dict(raw)


def admit_result(result):
    """Check the assembled result before any report is rendered from it."""
    for finding in result["verification_findings"]:
        if set(finding) - FINDING_FIELDS - {"survey_finding_ids"}:
            raise ValueError("Unexpected verification field")
        admit_finding({key: finding[key] for key in FINDING_FIELDS})
        linked = finding.get("survey_finding_ids", [])
        if not isinstance(linked, list) or not all(
            isinstance(value, str) and SURVEY_ID.fullmatch(value) for value in linked
        ):
            raise ValueError("Invalid survey link")
    return result
