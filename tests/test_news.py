"""Headline importer regression tests: RSS attribution, freshness and metro balance."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_news import parse_rss, select_stories, choose_metro

NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item><title>Coalition parties prepare for Tshwane municipal election results - Eyewitness News</title>
<link>https://news.google.com/rss/articles/example1</link>
<pubDate>Thu, 05 Nov 2026 09:00:00 GMT</pubDate><source url="https://www.ewn.co.za">Eyewitness News</source>
<description>Counting continues in Pretoria after the local government election.</description></item>
<item><title>Johannesburg municipal election counting continues - Reuters</title>
<link>https://news.google.com/rss/articles/example2</link>
<pubDate>Thu, 05 Nov 2026 09:01:00 GMT</pubDate><source url="https://www.reuters.com">Reuters</source>
<description>South African election results in Johannesburg.</description></item>
<item><title>Football results in South Africa - Mystery Site</title>
<link>https://news.google.com/rss/articles/example3</link>
<pubDate>Thu, 05 Nov 2026 09:00:00 GMT</pubDate><source>Mystery Site</source>
<description>Not an election.</description></item>
<item><title>Old South Africa local government election results - Reuters</title>
<link>https://news.google.com/rss/articles/example4</link>
<pubDate>Thu, 05 Nov 2020 09:00:00 GMT</pubDate><source>Reuters</source>
<description>Old elections.</description></item>
</channel></rss>"""


class NewsImporterTests(unittest.TestCase):
    def test_rss_attribution_and_time(self):
        articles = parse_rss(RSS, NOW)
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0]["publisher"], "Eyewitness News")
        self.assertNotIn("- Eyewitness News", articles[0]["title"])
        self.assertEqual(articles[0]["metro"], "Tshwane")
        self.assertEqual(articles[1]["metro"], "Johannesburg")

    def test_city_identity(self):
        self.assertEqual(choose_metro("Cape Town voting"), "Cape Town")
        self.assertEqual(choose_metro("Johannesburg and Tshwane coalitions"), "South Africa")

    def test_selection_prefers_three_metros_and_deduplicates(self):
        a = parse_rss(RSS, NOW)
        cape = {**a[0], "title": "Cape Town municipal election results are coming in", "metro": "Cape Town"}
        selection = select_stories(a + [cape, a[0]], NOW)
        self.assertEqual(len(selection), 3)
        self.assertEqual({s["metro"] for s in selection}, {"Cape Town", "Tshwane", "Johannesburg"})

    def test_bad_links_and_stale_articles_rejected(self):
        a = parse_rss(RSS, NOW)[0]
        bad = {**a, "url": "javascript:alert(1)", "title": "Unexpected fake headline"}
        stale = {**a, "published_date": "2018-01-01", "published_at": "", "title": "Outdated stale headline"}
        self.assertEqual(select_stories([bad, stale], NOW), [])


if __name__ == "__main__":
    unittest.main()
