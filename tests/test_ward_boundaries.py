"""Offline validation of authoritative 2026 metro ward GeoJSON inputs."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_ward_boundaries import validate

POLYGON = {"type": "Polygon", "coordinates": [[[18.0, -34.0], [18.1, -34.0], [18.1, -34.1], [18.0, -34.0]]]}
def feature(number):
    return {
        "type": "Feature",
        "properties": {"WardNo": number, "MUNICNAME": "City of Cape Town", "WardID": f"CPT{number:03d}"},
        "geometry": copy.deepcopy(POLYGON),
    }

class WardGeometryTests(unittest.TestCase):
    def test_accepts_complete_ward_range(self):
        output = validate({"type": "FeatureCollection", "features": [feature(2), feature(1)]}, 2, "Cape Town")
        self.assertEqual([x["properties"]["ward"] for x in output["features"]], [1, 2])
        self.assertEqual(output["features"][0]["geometry"]["type"], "Polygon")
        self.assertEqual(set(output["features"][0]["properties"]), {"ward"})

    def test_missing_ward_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            validate({"type": "FeatureCollection", "features": [feature(1)]}, 2, "Cape Town")

    def test_wrong_municipality_rejected(self):
        rows = [feature(1)]
        rows[0]["properties"]["MUNICNAME"] = "City of Johannesburg"
        with self.assertRaisesRegex(ValueError, "Unexpected municipality"):
            validate({"type": "FeatureCollection", "features": rows}, 1, "Cape Town")

    def test_invalid_polygon_rejected(self):
        rows = [feature(1)]
        rows[0]["geometry"] = {"type": "Point", "coordinates": [18.0, -34.0]}
        with self.assertRaisesRegex(ValueError, "not a polygon"):
            validate({"type": "FeatureCollection", "features": rows}, 1, "Cape Town")

    def test_unsafe_coords_rejected(self):
        rows = [feature(1)]
        rows[0]["geometry"]["coordinates"][0][0] = [999.0, 999.0]
        with self.assertRaisesRegex(ValueError, "outside South Africa"):
            validate({"type": "FeatureCollection", "features": rows}, 1, "Cape Town")

if __name__ == "__main__":
    unittest.main()
