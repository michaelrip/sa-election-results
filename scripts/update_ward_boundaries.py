"""Download and validate 2026 municipal ward geometries for the three metros.

Source: MDBWards2026 ArcGIS FeatureServer (Municipal Demarcation Board dataset).
Never publish incomplete or mismatched geometries. Store only ward id + geometry;
party colouring is joined from the independently updated results.json by ward number.
"""
from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ENDPOINTS = (
    "https://services7.arcgis.com/oeoyTUJC8HEeYsRB/arcgis/rest/services/MDBWards2026/FeatureServer/0/query",
    "https://hips-gis.health.gov.za/server/rest/services/Hosted/MDB_Wards_2026/FeatureServer/0/query",
)
METROS = {
    "Cape Town": ("cape-town", "Cape Town", 118),
    "Tshwane": ("tshwane", "Tshwane", 107),
    "Johannesburg": ("johannesburg", "Johannesburg", 135),
}
OUTDIR = Path("ward-boundaries")
STATUS = Path("ward-boundary-status.json")


def request_features(endpoint: str, city_search: str) -> dict:
    params = {
        "where": f"MUNICNAME LIKE '%{city_search}%'",
        "outFields": "WardNo,WardID,MUNICNAME",
        "returnGeometry": "true",
        "outSR": "4326",
        "geometryPrecision": "5",
        "maxAllowableOffset": "0.00015",
        "f": "geojson",
    }
    url = endpoint + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SA-Metro-Watch/1.0 (municipal ward map)", "Accept": "application/geo+json,application/json"},
    )
    with urllib.request.urlopen(req, timeout=65) as response:
        if response.status != 200:
            raise ValueError(f"Source HTTP {response.status}")
        payload = response.read(30_000_001)
    if len(payload) > 30_000_000:
        raise ValueError("Boundary response larger than allowed")
    parsed = json.loads(payload)
    if "error" in parsed:
        raise ValueError("ArcGIS returned an error: " + str(parsed["error"])[:220])
    return parsed


def _each_position(value):
    if (
        isinstance(value, list) and len(value) >= 2
        and isinstance(value[0], (int, float)) and not isinstance(value[0], bool)
        and isinstance(value[1], (int, float)) and not isinstance(value[1], bool)
    ):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _each_position(item)


def validate(data: dict, expected: int, city_search: str) -> dict:
    if data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
        raise ValueError("Source did not return a GeoJSON FeatureCollection")
    features = []
    seen = set()
    for feat in data["features"]:
        props = feat.get("properties") or {}
        ward = props.get("WardNo", props.get("wardno"))
        name = str(props.get("MUNICNAME", props.get("municname", "")))
        if city_search.lower() not in name.lower():
            raise ValueError(f"Unexpected municipality: {name!r}")
        try:
            number = int(ward)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid ward number: {ward!r}")
        if number < 1 or number > expected or number in seen:
            raise ValueError(f"Duplicate or out-of-range ward: {number}")
        seen.add(number)
        geom = feat.get("geometry") or {}
        if geom.get("type") not in ("Polygon", "MultiPolygon"):
            raise ValueError(f"Ward {number} is not a polygon")
        coords = geom.get("coordinates")
        if not isinstance(coords, list) or not coords:
            raise ValueError(f"Ward {number} has no geometry")
        positions = list(_each_position(coords))
        if len(positions) < 4:
            raise ValueError(f"Ward {number} has fewer than four vertices")
        for lon, lat, *_ in positions:
            if not (math.isfinite(lon) and math.isfinite(lat) and 16 <= lon <= 34 and -35 <= lat <= -22):
                raise ValueError(f"Ward {number} has coordinates outside South Africa")
        features.append({
            "type": "Feature",
            "properties": {"ward": number},
            "geometry": geom,
        })
    expected_set = set(range(1, expected + 1))
    if seen != expected_set:
        missing = sorted(expected_set - seen)
        raise ValueError(f"Expected {expected} wards, received {len(seen)}; missing: {missing[:12]}")
    features.sort(key=lambda feat: feat["properties"]["ward"])
    return {"type": "FeatureCollection", "features": features}


def main():
    now = datetime.now(timezone.utc).isoformat()
    OUTDIR.mkdir(exist_ok=True)
    report = {"checked_at": now, "source": "Municipal Demarcation Board 2026 ward boundaries (ArcGIS)", "status": "ok", "checks": {}}
    for metro, (slug, city_search, expected) in METROS.items():
        errors = []
        destination = OUTDIR / f"{slug}.geojson"
        for endpoint in ENDPOINTS:
            try:
                data = validate(request_features(endpoint, city_search), expected, city_search)
                rendered = json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n"
                if not destination.exists() or destination.read_text(encoding="utf-8") != rendered:
                    destination.write_text(rendered, encoding="utf-8")
                    updated = True
                else:
                    updated = False
                report["checks"][metro] = {
                    "status": "ok", "wards": len(data["features"]),
                    "source": endpoint.rsplit("/query", 1)[0],
                    "bytes": len(rendered.encode("utf-8")), "updated": updated,
                }
                break
            except Exception as err:
                errors.append(f"{endpoint.split('/')[2]}: {str(err)[:180]}")
        else:
            report["checks"][metro] = {
                "status": "error", "detail": errors,
                "existing_file_kept": destination.exists(),
            }
            report["status"] = "partial"
    STATUS.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["status"] != "ok":
        raise SystemExit("Not all 2026 ward boundary datasets passed validation")


if __name__ == "__main__":
    main()
