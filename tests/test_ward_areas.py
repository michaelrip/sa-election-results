"""Offline regression tests for 2026 ward-area tables."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_ward_areas import parse_ward_areas

PAGE = """<!doctype html><html><body>
<h2>Provisional ward results</h2>
<table><tr><th>Ward</th><th>Leading party</th></tr>
<tr><td>Ward 1</td><td>Not yet counted</td></tr>
<tr><td>Ward 2</td><td>DA</td></tr></table>
<h2>Every ward</h2>
<table>
<tr><th>Ward</th><th>Covers parts of</th></tr>
<tr><td><a href='/wards-2026/1/'>Ward 1</a></td><td>Bellville, Milnerton, Parow</td></tr>
<tr><td><a href='/wards-2026/2/'>Ward 2</a></td><td>Bellville, Parow</td></tr>
</table>
<h2>Ward by-elections since 2021</h2>
<table><tr><td>25 Mar 2026</td><td>104</td><td>ANC</td></tr></table>
</body></html>"""

class WardAreaTests(unittest.TestCase):
    def test_extracts_places_and_ignores_unrelated_tables(self):
        self.assertEqual(
            parse_ward_areas(PAGE, 2),
            {"1": "Bellville, Milnerton, Parow", "2": "Bellville, Parow"},
        )

    def test_requires_every_ward_section(self):
        with self.assertRaisesRegex(ValueError, "Every ward"):
            parse_ward_areas(PAGE.replace("<h2>Every ward</h2>", "<h2>Old wards</h2>"), 2)

    def test_refuses_incomplete_coverage(self):
        with self.assertRaisesRegex(ValueError, "Expected 3"):
            parse_ward_areas(PAGE, 3)

    def test_rejects_duplicate_conflicting_labels(self):
        page = PAGE.replace(
            "<td>Bellville, Parow</td></tr>",
            "<td>Bellville, Parow</td></tr><tr><td>Ward 1</td><td>Another place</td></tr>",
            1,
        )
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            parse_ward_areas(page, 2)

if __name__ == "__main__":
    unittest.main()
