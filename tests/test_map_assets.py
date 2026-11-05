"""Offline checks that published 2026 ward geometry matches the election feed."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "Cape Town": ("cape-town", 118),
    "Tshwane": ("tshwane", 107),
    "Johannesburg": ("johannesburg", 135),
}

class WardMapAssets(unittest.TestCase):
    def test_complete_2026_metro_boundaries(self):
        for city, (slug, n) in EXPECTED.items():
            with self.subTest(city=city):
                path = ROOT / "ward-boundaries" / (slug + ".geojson")
                self.assertTrue(path.exists(), "Missing downloaded boundaries for " + city)
                fc = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(fc["type"], "FeatureCollection")
                features = fc["features"]
                self.assertEqual(len(features), n)
                self.assertEqual({f["properties"]["ward"] for f in features}, set(range(1, n + 1)))
                self.assertTrue(all(f["geometry"]["type"] in ("Polygon", "MultiPolygon") for f in features))

    def test_boundary_ids_match_result_ward_ids(self):
        results = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
        areas = json.loads((ROOT / "ward-areas.json").read_text(encoding="utf-8"))
        for city, (_, n) in EXPECTED.items():
            with self.subTest(city=city):
                self.assertEqual({int(w["number"]) for w in results["metros"][city]["wards"]}, set(range(1, n + 1)))
                self.assertEqual(set(areas["metros"][city]), {str(i) for i in range(1, n + 1)})

    def test_dashboard_links_drilldown_assets(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "ward-maps.js").read_text(encoding="utf-8")
        self.assertIn('id="ward-detail-map"', html)
        self.assertIn('src="./ward-maps.js"', html)
        self.assertIn('data-ward-map-metro="Cape Town"', html)
        self.assertIn('data-ward-map-metro="Tshwane"', html)
        self.assertIn('data-ward-map-metro="Johannesburg"', html)
        self.assertIn("chooseWard(", js)
        self.assertIn("returnGeometry", js)
        self.assertIn("metroWardMaps", js)

if __name__ == "__main__":
    unittest.main()
