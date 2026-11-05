"""Verify ward-ballot top three are real party votes, never metro estimates."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_ward_details import parse_ward_page, valid_candidate
from fetch_results import Text

NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
WARD = {
    "number": 31, "winner": "DA", "reporting": "1 of 9 districts",
    "source_url": "https://go.esp.info/elections/local/2026/western-cape/city-of-cape-town/ward-31",
    "parties": [{"name": "DA", "share": 41.8}],
}
SAMPLE = """<html><head><style>Ward ballot ? · 999 valid votes</style></head><body>
<h1>Ward 31</h1><div>Western Cape</div><p>City of Cape Town</p>
<p>2026 Ward ballot</p><p>This ward 1 of 9 voting districts in</p>
<h2>Ward ballot ? · 729 valid votes</h2>
<ol>
<li><img alt="DA"> Democratic Alliance 305 41.8%</li>
<li><img alt="PA"> Patriotic Alliance 265 36.4%</li>
<li>H.O.I. Home of Independence 31 4.3%</li>
<li><img alt="ANC"> African National Congress 20 2.7%</li>
</ol>
<h2>PR ballot ? · 723 valid votes</h2><li>DA 319 44.1%</li>
<h2>About these figures</h2><p>IEC data last fetched 05 Nov 2026, 11:05 SAST.</p>
</body></html>"""

def visible(html):
    t = Text()
    t.feed(html)
    return " ".join(" ".join(t.parts).split())


class TopThreeTests(unittest.TestCase):
    def test_three_from_ward_ballot_not_pr(self):
        parsed = parse_ward_page(visible(SAMPLE), "Cape Town", 31, WARD, NOW)
        self.assertEqual(parsed["valid_votes"], 729)
        self.assertEqual(parsed["parties"], [
            {"name": "DA", "share": 41.8, "votes": 305},
            {"name": "PA", "share": 36.4, "votes": 265},
            {"name": "H.O.I.", "share": 4.3, "votes": 31},
        ])
        self.assertTrue(valid_candidate(WARD, parsed, NOW))

    def test_rejects_stale_mismatched_leader(self):
        out = parse_ward_page(visible(SAMPLE), "Cape Town", 31, WARD, NOW)
        self.assertFalse(valid_candidate(
            {**WARD, "parties": [{"name": "ANC", "share": 33.3}]}, out, NOW
        ))
        self.assertFalse(valid_candidate(
            {**WARD, "reporting": "2 of 9 districts"}, out, NOW
        ))

    def test_bad_vote_counts_not_published(self):
        tampered = SAMPLE.replace("Patriotic Alliance 265 36.4%", "Patriotic Alliance 365 36.4%")
        with self.assertRaisesRegex(ValueError, "disagree"):
            parse_ward_page(visible(tampered), "Cape Town", 31, WARD, NOW)

    def test_rejects_pr_only_page(self):
        wrong = SAMPLE.replace("Ward ballot ? · 729 valid votes", "PR ballot ? · 729 valid votes")
        with self.assertRaisesRegex(ValueError, "Ward ballot votes"):
            parse_ward_page(visible(wrong), "Cape Town", 31, WARD, NOW)

    def test_rejects_wrong_ward(self):
        with self.assertRaisesRegex(ValueError, "Wrong ward"):
            parse_ward_page(visible(SAMPLE), "Cape Town", 32, WARD, NOW)

    def test_missing_second_party_is_not_invented(self):
        insufficient = SAMPLE.replace(
            '<li><img alt="PA"> Patriotic Alliance 265 36.4%</li>',
            ""
        ).replace('<li>H.O.I. Home of Independence 31 4.3%</li>', "")
        insufficient = insufficient.replace(
            '<li><img alt="ANC"> African National Congress 20 2.7%</li>',
            ""
        )
        with self.assertRaisesRegex(ValueError, "Fewer than two"):
            parse_ward_page(visible(insufficient), "Cape Town", 31, WARD, NOW)


if __name__ == "__main__":
    unittest.main()
