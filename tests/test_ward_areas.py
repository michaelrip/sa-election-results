"""Offline regression tests for 2026 individual ward-page labels."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_ward_areas import parse_ward_label, valid_existing

PAGE = """<!doctype html><html><body>
<nav>2026 election · Ward 1</nav>
<h1>Ward 1</h1>
<p>Covers parts of Bellville, Milnerton, Parow.</p>
<h2>Election-night status</h2>
<div>Ward 1 — Not yet counted. DA 41.8%</div>
<h2>Places in this ward</h2>
<li>Bellville: Loevenstein</li>
<li>Milnerton: Plattekloof Glen, Monte Vista</li>
</body></html>"""

class WardAreaTests(unittest.TestCase):
    def test_uses_area_description_not_votes(self):
        self.assertEqual(
            parse_ward_label(PAGE, 1), "Bellville, Milnerton, Parow"
        )

    def test_validates_ward_identity(self):
        with self.assertRaisesRegex(ValueError, "Wrong ward"):
            parse_ward_label(PAGE, 2)

    def test_requires_geographic_description(self):
        with self.assertRaisesRegex(ValueError, "description unavailable"):
            parse_ward_label(PAGE.replace("Covers parts of", "Election status for"), 1)

    def test_rejects_vote_status_labels(self):
        with self.assertRaisesRegex(ValueError, "Vote results"):
            parse_ward_label(PAGE.replace("Bellville, Milnerton, Parow", "Not yet counted"), 1)

    def test_rejects_old_bogus_area_mapping(self):
        self.assertFalse(valid_existing({"1": "Not yet counted – –"}, 1))
        self.assertFalse(valid_existing({"1": "DA 75.3% 67.3%"}, 1))
        self.assertTrue(valid_existing({"1": "Bellville, Milnerton, Parow"}, 1))


if __name__ == "__main__":
    unittest.main()
