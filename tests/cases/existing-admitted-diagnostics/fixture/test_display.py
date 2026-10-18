import unittest

from display import render


class DisplayTests(unittest.TestCase):
    def test_retry_keeps_useful_admitted_explanation(self):
        text = render(dict(kind="retry", reason="connection_reset", attempt=2, maximum=3))
        self.assertIn("retry", text.lower())
        self.assertIn("2/3", text)
        self.assertIn("Peer closed the connection", text)

    def test_final_failure_is_distinct(self):
        text = render(dict(kind="failed", reason="timeout", attempt=3, maximum=3))
        self.assertIn("fail", text.lower())
        self.assertIn("3/3", text)
        self.assertIn("Timed out waiting for the transport", text)

    def test_raw_payload_does_not_reach_output(self):
        raw = dict(kind="retry", reason="timeout", attempt=1, maximum=3)
        expected = render(raw)
        raw["raw_exception"] = "SYNTHETIC_PRIVATE_PAYLOAD\n\x1b[31m"
        self.assertEqual(render(raw), expected)
        self.assertNotIn("SYNTHETIC_PRIVATE_PAYLOAD", expected)
        self.assertNotIn("\x1b", expected)

    def test_invalid_reason_stays_rejected(self):
        with self.assertRaises(ValueError):
            render(dict(kind="retry", reason="SYNTHETIC_PRIVATE_PAYLOAD", attempt=1, maximum=3))

    def test_invalid_attempts_stay_rejected(self):
        for attempt in (0, 4, True, "1"):
            with self.subTest(attempt=attempt), self.assertRaises(ValueError):
                render(dict(kind="retry", reason="timeout", attempt=attempt, maximum=3))


if __name__ == "__main__":
    unittest.main()
