import unittest

from assessment import assemble, verified_aspects
from report import verification_table

SURVEY = [
    dict(cwe="CWE-639", file="routes/basket.js", line=18),
    dict(cwe="CWE-89", file="routes/search.js", line=23),
    dict(cwe="CWE-639", file="routes/basket.js", line=21),
]


def finding(**changes):
    base = dict(id="V-001", cwe="CWE-639", file="routes/basket.js", line=19, reason="Basket id comes from the request")
    return dict(base, **changes)


class ReportTests(unittest.TestCase):
    def test_linked_finding_names_its_survey_findings(self):
        table = verification_table(assemble(SURVEY, [finding()]))
        self.assertIn("| V-001 (as T-001, T-003) |", table)

    def test_unlinked_finding_shows_only_its_id(self):
        table = verification_table(assemble(SURVEY, [finding(id="V-002", cwe="CWE-22", file="routes/file.js")]))
        self.assertIn("| V-002 |", table)
        self.assertNotIn("(as", table)

    def test_standard_depth_verifies_authz(self):
        self.assertEqual(verified_aspects("standard"), ["authz"])
        self.assertEqual(verified_aspects("quick"), [])

    def test_model_reason_stays_encoded(self):
        table = verification_table(assemble(SURVEY, [finding(reason="a | b <script>")]))
        self.assertIn("a \\| b &lt;script&gt;", table)
        self.assertNotIn("<script>", table)

    def test_malformed_model_finding_is_rejected(self):
        for bad in (finding(id="T-001"), finding(line="19"), finding(file="../x"), dict(finding(), extra=1)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                assemble(SURVEY, [bad])


if __name__ == "__main__":
    unittest.main()
