"""Validate factual 2021 ward-ballot comparisons (not PR or 2024 ballots)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fetch_results import Text
from update_history_2021 import parse_metro, parse_ward

def visible(raw):
    p = Text()
    p.feed(raw)
    return " ".join(" ".join(p.parts).split())

METRO = """<html><body>
<h1>City of Cape Town</h1><p>2021</p><p>Wards DA 83 ANC 33</p>
<h2>Ward ballot ? · 909 509 valid votes</h2>
<ol><li><img alt="DA"> Democratic Alliance 525 515 57.8%</li>
<li><img alt="ANC"> African National Congress 167 907 18.5%</li>
<li><img alt="EFF"> Economic Freedom Fighters 37 255 4.1%</li></ol>
<h2>PR ballot ? · 925 000 valid votes</h2>
<li>DA 660 000 71.4%</li>
<h2>About these figures</h2></body></html>"""

WARD = """<html><body>
<h1>Ward 1</h1><p>Covers parts of Pretoria.</p>
<h2>How this ward voted over time</h2>
<h3>2024 national ballot</h3>
<p>DA 66.7%</p><p>VF+ 11.1%</p>
<h3>2021 party (PR) ballot</h3>
<p>DA 61.8%</p><p>VF+ 20.8%</p><p>ANC 7.4%</p>
<h3>2021 ward ballot</h3>
<p>DA 62.6%</p><p>VF+ 21.3%</p><p>ANC 7.2%</p>
<p>ActionSA 3.6%</p><p>EFF 2.3%</p><p>Others 2.9%</p>
<p>Turnout 51.5% · 9 335 valid votes · 6 of this ward’s 6 voting districts have results for that year</p>
<p>Earlier results are those of the ward's own voting districts, matched by voting-district number.</p>
</body></html>"""

class History2021Tests(unittest.TestCase):
    def test_metro_ward_ballot_not_pr(self):
        row = parse_metro(
            visible(METRO), "Cape Town",
            "https://go.esp.info/elections/local/2021/western-cape/city-of-cape-town")
        self.assertEqual(row["valid_votes"], 909509)
        self.assertEqual(row["parties"]["DA"], 57.8)
        self.assertEqual(row["parties"]["ANC"], 18.5)
        self.assertEqual(row["parties"]["EFF"], 4.1)

    def test_ward_uses_current_area_historic_districts(self):
        row = parse_ward(
            visible(WARD), 1,
            "https://theledgersa.com/metros/tshwane/wards-2026/1/")
        self.assertEqual(row["parties"]["DA"], 62.6)
        self.assertEqual(row["parties"]["FF+"], 21.3)
        self.assertEqual(row["parties"]["ANC"], 7.2)
        self.assertNotEqual(row["parties"]["DA"], 61.8)
        self.assertEqual(row["matched_districts"], 6)
        self.assertEqual(row["districts_in_2026_ward"], 6)

    def test_never_infer_missing_party_or_zero(self):
        row = parse_ward(
            visible(WARD), 1,
            "https://theledgersa.com/metros/tshwane/wards-2026/1/")
        self.assertNotIn("PA", row["parties"])
        self.assertNotIn("MK", row["parties"])

    def test_overstrand_historical_municipality_not_false_metro(self):
        raw = visible(METRO.replace("City of Cape Town", "Overstrand"))
        row = parse_metro(raw, "Hermanus", "https://go.esp.info/elections/local/2021/western-cape/overstrand")
        self.assertEqual(row["parties"]["DA"], 57.8)
        self.assertEqual(row["year"], 2021)
        self.assertEqual(row["ballot_type"], "Ward")

    def test_wrong_ward_rejected(self):
        with self.assertRaisesRegex(ValueError, "Wrong ward"):
            parse_ward(visible(WARD), 37, "https://example.com")

    def test_missing_2021_section_rejected(self):
        with self.assertRaisesRegex(ValueError, "section missing"):
            parse_ward(visible(WARD.replace("<h3>2021 ward ballot</h3>", "<h3>2021 PR ballot again</h3>")), 1, "https://example.com")

    def test_incomplete_coverage_preserved_not_invented(self):
        ward = WARD.replace("6 of this ward’s 6 voting districts", "4 of this ward’s 6 voting districts")
        row = parse_ward(visible(ward), 1, "https://example.com")
        self.assertEqual(row["matched_districts"], 4)
        self.assertEqual(row["districts_in_2026_ward"], 6)

if __name__ == "__main__":
    unittest.main()
