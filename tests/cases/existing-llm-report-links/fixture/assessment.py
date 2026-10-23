"""Assemble an assessment result from survey threats and model verification output."""

import json
from pathlib import Path

from admission import admit_finding, admit_result
from linker import link, number_survey

DEPTHS = json.loads((Path(__file__).parent / "depths.json").read_text())


def verified_aspects(depth):
    """Security aspects that verification examines at an assessment depth."""
    return list(DEPTHS[depth])


def assemble(survey_threats, model_findings):
    survey = number_survey(survey_threats)
    findings = link(survey, [admit_finding(raw) for raw in model_findings])
    return admit_result({"survey": survey, "verification_findings": findings})
