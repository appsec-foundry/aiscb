import unittest

from admission import admit_text
from register import build_register

TEXT = {
    "title": "Basket owner is not checked",
    "scenario": "A logged-in user changes the basket id in the request and reads another user's basket.",
    "remediation": {
        "steps": ["Load the basket by id and owner", "Return 404 for foreign baskets"],
        "verification": "Request another user's basket and expect 404",
    },
}


def finding(**changes):
    base = dict(id="T-001", method="survey", cwe="CWE-639", severity="medium",
                locations=[dict(file="routes/basket.js", line=18)], **TEXT)
    return dict(base, **changes)


SURVEY = [finding(), finding(id="T-002", cwe="CWE-89", locations=[dict(file="routes/search.js", line=23)])]
VERIFIED = finding(id="V-001", method="verification", severity="high",
                   locations=[dict(file="routes/basket.js", line=20)],
                   title="Basket id from the request selects any basket")


class FakeProvider:
    def __init__(self, reply):
        self.reply = reply
        self.roles = []

    def __call__(self, role, prompt):
        self.roles.append(role)
        return self.reply


COMBINED = dict(TEXT, title="Any user can read any basket by its id")


class RegisterTests(unittest.TestCase):
    def test_separate_issues_stay_separate(self):
        entries = build_register(SURVEY[1:], [VERIFIED], FakeProvider(COMBINED))
        self.assertEqual([entry["ids"] for entry in entries], [["T-002"], ["V-001"]])

    def test_same_issue_becomes_one_entry(self):
        provider = FakeProvider(COMBINED)
        entries = build_register(SURVEY, [VERIFIED], provider)
        combined = [entry for entry in entries if entry["ids"] == ["T-001", "V-001"]]
        self.assertEqual(len(entries), 2)
        self.assertEqual(len(combined), 1)
        self.assertEqual(combined[0]["methods"], ["survey", "verification"])
        self.assertEqual(combined[0]["severity"], "high")
        self.assertEqual(combined[0]["locations"], [dict(file="routes/basket.js", line=18),
                                                    dict(file="routes/basket.js", line=20)])
        self.assertEqual(combined[0]["title"], COMBINED["title"])
        self.assertEqual(provider.roles, ["merge"])

    def test_rejected_merge_text_keeps_verification_text(self):
        for reply in (dict(COMBINED, severity="low"), dict(COMBINED, title="x"), "text"):
            with self.subTest(reply=reply):
                entries = build_register(SURVEY, [VERIFIED], FakeProvider(reply))
                combined = [entry for entry in entries if entry["ids"] == ["T-001", "V-001"]]
                self.assertEqual(combined[0]["title"], VERIFIED["title"])
                self.assertEqual(combined[0]["severity"], "high")

    def test_admission_rejects_malformed_text(self):
        for bad in (dict(TEXT, extra=1), dict(TEXT, scenario="short"),
                    dict(TEXT, remediation={"steps": ["only one"], "verification": "Check it works"})):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                admit_text(bad)


if __name__ == "__main__":
    unittest.main()
