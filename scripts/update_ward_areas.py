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


def parse_ward_areas(html, expected):
    parser = TableRows()
    parser.feed(html)
    # Pages also contain a provisional vote-results table with rows like
    # "Ward 1 | Not yet counted". Never mistake those for area descriptions.
    # Only read the table headed "Ward | Covers parts of".
    start = next(
        (
            index + 1
            for index, row in enumerate(parser.rows)
            if len(row) >= 2
            and row[0].strip().lower() == "ward"
            and "covers parts of" in row[1].strip().lower()
        ),
        None,
    )
    if start is None:
        raise ValueError("2026 'Ward | Covers parts of' table was not found")
    areas = {}
    for cells in parser.rows[start:]:
        if len(cells) < 2:
            continue
        match = re.fullmatch(r"Ward\s+(\d{1,3})", cells[0], flags=re.I)
        if not match:
            continue
        number = int(match.group(1))
        label = cells[1].strip()
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
        raise ValueError(f"Expected {expected} 2026 ward labels, found {len(areas)}")
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
