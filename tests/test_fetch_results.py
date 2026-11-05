"""Offline source-format regression tests; no invented real-world result values."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_results as feed

SAMPLE = """<html><head><script>ignore 999% synthetic script</script></head><body>
<h1>City of Cape Town</h1><p>2026</p>
<div>Vote breakdown · Ward ballot <span>DA 41.8%</span> <span>PA 36.4%</span> <span>H.O.I. 4.3%</span> <span>Others 17.6%</span></div>
<div>Stations open 7am–9pm</div>
<div>City of Cape Town 1 of 829 voting districts in 0 of 118 wards complete</div>
<h2>Ward ballot ? · 729 valid votes</h2>
<ol><li><img alt="DA"/> Democratic Alliance 305 41.8%</li>
<li><img alt="PA"/> Patriotic Alliance 265 36.4%</li>
<li><img alt="ANC"/> African National Congress 20 2.7%</li></ol>
<h2>How did City of Cape Town vote?</h2>
<h2>Wards · 118</h2><li>Ward 31 1 of 9 voting districts in DA 41.8%</li><li>Ward 1 Not in yet</li>
<h2>About these figures</h2><p>IEC data last fetched 05 Nov 2026, 09:05 SAST.</p>
</body></html>"""

NOW = datetime(2026, 11, 5, 10, tzinfo=timezone.utc)
ARGS = ("Cape Town", "western-cape/city-of-cape-town", 829, 118, NOW)

class ScrapingTests(unittest.TestCase):
    def test_list_without_text_numbering(self):
        txt = feed.get.__globals__["Text"]()
        txt.feed(SAMPLE)
        source = " ".join(" ".join(txt.parts).split())
        with patch.object(feed, "get", return_value=source):
            metro, found = feed.parse(*ARGS)
        self.assertEqual(metro["districts_reported"], 1)
        self.assertEqual(metro["parties"][0], {"name": "DA", "share": 41.8})
        self.assertEqual(metro["parties"][1], {"name": "PA", "share": 36.4})
        self.assertEqual(found, 1)
        self.assertEqual(metro["wards"][30]["winner"], "DA")
        self.assertEqual(metro["wards"][0]["status"], "Not yet reported")

    def test_invalid_district_total_rejected(self):
        txt = feed.Text()
        txt.feed(SAMPLE.replace("1 of 829 voting", "1 of 828 voting"))
        with patch.object(feed, "get", return_value=" ".join(" ".join(txt.parts).split())):
            with self.assertRaisesRegex(ValueError, "invalid"):
                feed.parse(*ARGS)

    def test_stale_source_rejected(self):
        txt = feed.Text()
        txt.feed(SAMPLE.replace("05 Nov 2026", "01 Nov 2026"))
        with patch.object(feed, "get", return_value=" ".join(" ".join(txt.parts).split())):
            with self.assertRaisesRegex(ValueError, "stale"):
                feed.parse(*ARGS)

if __name__ == "__main__":
    unittest.main()
