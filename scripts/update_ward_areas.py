"""Import factual area labels for all 2026 metro wards.

These are names of areas a ward covers, not official ward names.
The numbers remain the canonical election identifiers.
"""
import json
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

SOURCES = {
    "Cape Town": ("https://theledgersa.com/metros/cape-town/elections/2026/", 118),
    "Tshwane": ("https://theledgersa.com/metros/tshwane/elections/2026/", 107),
    "Johannesburg": ("https://theledgersa.com/metros/johannesburg/elections/2026/", 135),
}
OUTPUT = Path("ward-areas.json")
REPORT = Path("ward-area-status.json")


class TableRows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.current = None
        self.cell = None
        self.ignore = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.ignore += 1
        if self.ignore:
            return
        if tag == "tr":
            self.current = []
        if tag in ("td", "th") and self.current is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.ignore = max(0, self.ignore - 1)
            return
        if tag in ("td", "th") and self.current is not None and self.cell is not None:
            self.current.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if tag == "tr" and self.current is not None:
            self.rows.append(self.current)
            self.current = None

    def handle_data(self, data):
        if not self.ignore and self.cell is not None:
            self.cell.append(data)


class EveryWardSection(HTMLParser):
    """Text within the 2026 'Every ward' heading only.

    The same page has an earlier ward-results section, which must never
    provide place labels.
    """
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_h2 = False
        self.heading = []
        self.collect = False
        self.parts = []
        self.ignore = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.ignore += 1
        if self.ignore:
            return
        if tag == "h2":
            self.in_h2 = True
            self.heading = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.ignore = max(0, self.ignore - 1)
        if tag == "h2" and self.in_h2:
            title = " ".join("".join(self.heading).split()).lower()
            self.collect = title.startswith("every ward")
            self.in_h2 = False

    def handle_data(self, text):
        if self.ignore:
            return
        if self.in_h2:
            self.heading.append(text)
        elif self.collect and text.strip():
            self.parts.append(text.strip())


def parse_ward_areas(html, expected):
    parser = EveryWardSection()
    parser.feed(html)
    body = " ".join(" ".join(parser.parts).split())
    if not body:
        raise ValueError("2026 'Every ward' section was not found")
    markers = list(re.finditer(r"\bWard\s+(\d{1,3})\b", body, flags=re.I))
    areas = {}
    for index, marker in enumerate(markers):
        number = int(marker.group(1))
        stop = markers[index + 1].start() if index + 1 < len(markers) else len(body)
        label = body[marker.end():stop].strip()
        if not 1 <= number <= expected or not 2 <= len(label) <= 250:
            continue
        if label.lower() in {
            "—", "-", "not available", "no data", "not yet counted",
            "not reported", "awaiting results", "results pending",
            "da", "anc", "eff", "pa", "actionsa", "mkp", "ifp", "good",
        }:
            continue
        if re.search(r"<|>|https?://", label):
            continue
        if str(number) in areas and areas[str(number)] != label:
            raise ValueError(f"Conflicting area labels for ward {number}")
        areas[str(number)] = label
    if len(areas) != expected:
        raise ValueError(
            f"Expected {expected} 2026 ward labels, found {len(areas)}; "
            f"section chars {len(body)}; examples {list(areas.items())[:2]}"
        )
    return {str(n): areas[str(n)] for n in range(1, expected + 1)}


def get(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SA-Metro-Watch/1.0)", "Accept": "text/html"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}")
        return response.read(3_000_000).decode("utf-8", "replace")


def main():
    now = datetime.now(timezone.utc).isoformat()
    if OUTPUT.exists():
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    else:
        data = {"metros": {}}
    data.setdefault("metros", {})
    report = {"checked_at": now, "status": "ok", "checks": {}}
    changed = False
    for metro, (url, expected) in SOURCES.items():
        try:
            labels = parse_ward_areas(get(url), expected)
            if data["metros"].get(metro) != labels:
                data["metros"][metro] = labels
                changed = True
            report["checks"][metro] = {"status": "ok", "wards_named": len(labels), "source_url": url}
        except Exception as error:
            report["checks"][metro] = {"status": "error", "detail": str(error)[:200], "source_url": url}
            report["status"] = "partial"
    if changed or not OUTPUT.exists():
        data["updated_at"] = now
        data["description"] = "Geographic areas covered by 2026 wards, NOT official ward names; some places span several wards."
        data["source"] = "The Ledger SA, 2026 metro ward lists (Stats SA place names / MDB boundaries)"
        OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["areas_updated"] = changed
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
