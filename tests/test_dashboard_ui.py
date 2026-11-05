"""Regression checks for dashboard navigation, responsive controls and source honesty.

These are static/structural tests. Dynamic interaction smoke tests are run
separately against the dashboard JavaScript using simulated browser controls.
"""
from __future__ import annotations

import re
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
MOBILE = (ROOT / "mobile.css").read_text(encoding="utf-8")
MAP = (ROOT / "ward-maps.js").read_text(encoding="utf-8")


class PageStructure(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.anchor_targets = []
        self.controls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("href", "").startswith("#"):
            self.anchor_targets.append(attrs["href"][1:])
        if tag in ("button", "input", "select", "output", "details"):
            self.controls.append((tag, attrs))


class DashboardUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = PageStructure()
        cls.page.feed(HTML)

    def test_unique_ids_and_valid_navigation_targets(self):
        duplicates = [key for key, value in Counter(self.page.ids).items() if value > 1]
        self.assertFalse(duplicates, f"Duplicate HTML ids: {duplicates}")
        for target in self.page.anchor_targets:
            self.assertIn(target, self.page.ids,
                          f"Broken internal navigation anchor: #{target}")

    def test_four_navigation_destinations(self):
        for element in ("news-heading", "metro-maps", "metro-votes", "ward-explorer"):
            self.assertIn(element, self.page.ids)
        self.assertIn("function trackSectionNavigation()", HTML)
        self.assertIn("aria-current", HTML)
        self.assertIn("scroll-padding-bottom", MOBILE)

    def test_sharing_restores_city_and_ballot(self):
        self.assertIn("new URL(location.href)", HTML)
        self.assertIn("function updateShareableView()", HTML)
        self.assertIn("url.searchParams.set('city',selectedMetro)", HTML)
        self.assertIn("url.searchParams.set('ballot',selectedBallot)", HTML)
        self.assertIn("window.initialMetro=selectedMetro", HTML)
        self.assertIn("window.initialMetro && spec[window.initialMetro]", MAP)

    def test_news_controls_and_position(self):
        for element in ("news-feed", "news-prev", "news-next", "news-check", "news-position"):
            self.assertIn(element, self.page.ids)
        self.assertIn("position.textContent=count?index+' / '+count:'—'", HTML)
        self.assertIn("feed.querySelectorAll('.news-story')", HTML)

    def test_ward_search_exact_number_and_conditional_clear(self):
        self.assertIn(r"/^(?:(?:ward|w)\s*)?(\d{1,3})$/", HTML)
        self.assertIn("el('clear').hidden=!q", HTML)
        self.assertIn('#clear[hidden]{display:none}', HTML)
        self.assertIn("wardChoiceFingerprint", MAP)

    def test_source_info_reduced_to_a_disclosure(self):
        self.assertIn('id="about-data"', HTML)
        self.assertIn('class="panel source-details"', HTML)
        self.assertIn("2021 comparisons:", HTML)
        self.assertIn("Ward + PR", HTML)
        self.assertIn("ESP", HTML)
        self.assertNotIn("loadOptionalJSON('./results-iec.json')", HTML)

    def test_selected_cape_watch_is_near_vote_results(self):
        self.assertLess(HTML.index('id="metro-votes"'),
                        HTML.index('id="cape-majority"'))
        self.assertLess(HTML.index('id="cape-majority"'),
                        HTML.index('id="ward-explorer"'))

    def test_mobile_map_uses_full_width_result_panel_not_leaflet_popup(self):
        self.assertIn("function compactWardMode()", MAP)
        self.assertIn("if (!compactWardMode()) {", MAP)
        self.assertIn("layer.bindPopup(tipFor(id, true)", MAP)
        self.assertIn("chooseWard(id, false);\n            scrollWardPanelIntoView();", MAP)
        self.assertIn("function scrollWardPanelIntoView()", MAP)
        self.assertIn("els.side.scrollIntoView(", MAP)
        self.assertIn('id="ward-map-back"', MAP)
        self.assertIn("els.map.scrollIntoView(", MAP)
        self.assertIn("#ward-detail-map .leaflet-popup.ward-map-popup{display:none!important}", MOBILE)
        self.assertIn("@media(max-width:760px),(pointer:coarse)", MOBILE)
        self.assertIn("ward-maps.js?v=20261105-map-panel-fix", HTML)
        self.assertIn("mobile.css?v=20261105-map-panel-fix", HTML)

    def test_mobile_css_balanced_and_minimum_touch_targets(self):
        css = re.sub(r"/\*[\s\S]*?\*/", "", MOBILE)
        self.assertEqual(css.count("{"), css.count("}"))
        self.assertIn("min-height:48px", MOBILE)
        self.assertIn("env(safe-area-inset-bottom)", MOBILE)
        self.assertIn("prefers-reduced-motion", MOBILE)


if __name__ == "__main__":
    unittest.main()
