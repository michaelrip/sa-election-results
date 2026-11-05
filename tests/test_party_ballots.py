"""PR and district ballot sources: don't mix candidate ballots or count voters twice."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_party_ballots import parse_ballot, party_name
from fetch_results import Text

NOW = datetime(2026, 11, 5, 14, tzinfo=timezone.utc)
PR = """<html><body>
<h1>City of Cape Town</h1><p>2026</p>
<h2>Vote breakdown · PR ballot</h2>
<p>City of Cape Town 2 of 829 voting districts in</p>
<h2>PR ballot ? · 723 valid votes</h2>
<ol>
<li><img alt="DA"> Democratic Alliance 319 44.1%</li>
<li><img alt="PA"> Patriotic Alliance 257 35.5%</li>
<li>H.O.I. Home of Independence 29 4.0%</li>
<li><img alt="ANC"> African National Congress 21 2.9%</li>
</ol>
<h2>Wards · 118</h2>
<p>IEC data last fetched 05 Nov 2026, 11:32 SAST.</p>
</body></html>"""

def clean(s):
    p = Text()
    p.feed(s)
    return " ".join(" ".join(p.parts).split())

class PartyBallotTests(unittest.TestCase):
    def test_pr_uses_actual_ballot_rows_and_real_denominator(self):
        result = parse_ballot(clean(PR), "Cape Town", "pr", "https://go.esp.info/elections/local/2026/western-cape/city-of-cape-town?ballot=pr", NOW)
        self.assertEqual(result["valid_votes"], 723)
        self.assertEqual(result["parties"][0], {"name": "DA", "votes": 319, "share": 44.1})
        self.assertEqual(result["parties"][1]["name"], "PA")
        self.assertEqual(result["unlisted_votes"], 97)
        self.assertEqual(result["ballot_type"], "PR")

    def test_district_separate_council(self):
        src = PR.replace("City of Cape Town", "Overstrand").replace("PR ballot", "DC 40% ballot")
        result = parse_ballot(clean(src), "Hermanus", "dc", "https://esp.info/elections/local/2026/western-cape/overstrand?ballot=dc", NOW)
        self.assertEqual(result["ballot_type"], "District PR")
        self.assertEqual(result["valid_votes"], 723)
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            parse_ballot(clean(src), "Cape Town", "dc", "", NOW)

    def test_no_ward_vote_substitution_for_pr(self):
        wrong = PR.replace("PR ballot ? · 723", "Ward ballot ? · 723")
        with self.assertRaisesRegex(ValueError, "No source-confirmed"):
            parse_ballot(clean(wrong), "Cape Town", "pr", "", NOW)

    def test_source_vote_and_share_disagreement_rejected(self):
        corrupt=PR.replace("Democratic Alliance 319 44.1%", "Democratic Alliance 519 44.1%")
        with self.assertRaisesRegex(ValueError, "Missing/contradictory"):
            parse_ballot(clean(corrupt), "Cape Town", "pr", "", NOW)

    def test_no_fabrication_when_source_outdated(self):
        out=PR.replace("05 Nov 2026", "02 Nov 2026")
        with self.assertRaisesRegex(ValueError, "stale"):
            parse_ballot(clean(out), "Cape Town", "pr", "", NOW)

    def test_canonical_party_codes(self):
        self.assertEqual(party_name("ImageVF PLUS Vryheidsfront Plus | Freedom Front Plus"), "FF+")
        self.assertEqual(party_name("ImageMKP Umkhonto Wesizwe Party"), "MK")
        self.assertEqual(party_name("ImageDA Democratic Alliance"), "DA")

if __name__ == "__main__":
    unittest.main()
