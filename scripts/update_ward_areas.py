"""Import area descriptions from each individual 2026 ward page.

Ward identifiers are the official numbers. These labels are geographic
descriptions ("covers parts of"), never official ward names.
Metro election-night summary pages show vote status, NOT ward names.
"""
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

SOURCES = {
    "Cape Town": ("cape-town", 118),
    "Tshwane": ("tshwane", 107),
    "Johannesburg": ("johannesburg", 135),
    "Hermanus": ("overstrand", 15),
}
SITE = "https://theledgersa.com/metros/{metro}/wards-2026/{ward}/"
OUTPUT = Path("ward-areas.json")
REPORT = Path("ward-area-status.json")
MAX_WORKERS = 6


class WardPage(HTMLParser):
    """Read visible words and paragraph text, excluding script/style content."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts = []
        self.in_paragraph = False
        self.paragraph_parts = []
        self.paragraphs = []
        self.in_h1 = False
        self.h1_parts = []
        self.headings = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if self.skip:
            return
        if tag == "p":
            self.in_paragraph = True
            self.paragraph_parts = []
        elif tag == "h1":
            self.in_h1 = True
            self.h1_parts = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)
            return
        if tag == "p" and self.in_paragraph:
            self.paragraphs.append(" ".join(" ".join(self.paragraph_parts).split()))
            self.in_paragraph = False
        elif tag == "h1" and self.in_h1:
            self.headings.append(" ".join(" ".join(self.h1_parts).split()))
            self.in_h1 = False

    def handle_data(self, data):
        if self.skip:
            return
        cleaned = " ".join(data.split())
        if cleaned:
            self.parts.append(cleaned)
            if self.in_paragraph:
                self.paragraph_parts.append(cleaned)
            if self.in_h1:
                self.h1_parts.append(cleaned)


def parse_ward_label(html, expected_ward):
    page = WardPage()
    page.feed(html)
    if not any(
        re.fullmatch(r"Ward\s+" + str(expected_ward), heading, re.I)
        for heading in page.headings
    ):
        raise ValueError("Wrong ward heading or page structure")
    # Prefer the dedicated description paragraph, which is more trustworthy
    # than any nearby election-night result or candidate-status text.
    candidates = page.paragraphs + [" ".join(page.parts)]
    label = None
    for candidate in candidates:
        match = re.search(r"\bCovers parts of\s+([^.?!]{2,240})\.", candidate, re.I)
        if match:
            label = " ".join(match.group(1).split()).strip()
            break
    if not label or len(label) > 230:
        raise ValueError("2026 ward's area description unavailable")
    if re.search(r"\bnot yet counted\b|\bawaiting\b|\d+(?:\.\d+)?%", label, re.I):
        raise ValueError("Vote results were mistaken for place names")
    if re.search(r"<|>|https?://", label):
        raise ValueError("Invalid characters in place label")
    return label


def download(url):
    last_error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; SA-Metro-Watch/1.0)",
                    "Accept": "text/html",
                },
            )
            with urllib.request.urlopen(request, timeout=22) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}")
                return response.read(900_000).decode("utf-8", "replace")
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(attempt + 1)
    raise ValueError(str(last_error)[:120])


def fetch_one(metro_slug, ward_number):
    url = SITE.format(metro=metro_slug, ward=ward_number)
    return ward_number, parse_ward_label(download(url), ward_number)


def valid_existing(labels, expected):
    if not isinstance(labels, dict) or len(labels) != expected:
        return False
    for number in range(1, expected + 1):
        value = labels.get(str(number))
        if not isinstance(value, str) or not 2 <= len(value) <= 230:
            return False
        if re.search(r"\bnot yet counted\b|\d+(?:\.\d+)?%|[–—]", value, re.I):
            return False
        if value.lower() in {"da", "anc", "eff", "pa", "ifp", "good", "actionsa"}:
            return False
    return True


def main():
    now = datetime.now(timezone.utc).isoformat()
    data = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {"metros": {}}
    data.setdefault("metros", {})
    report = {"checked_at": now, "status": "ok", "checks": {}}
    changed = False

    for metro, (slug, expected) in SOURCES.items():
        existing = data["metros"].get(metro, {})
        if valid_existing(existing, expected):
            report["checks"][metro] = {
                "status": "ok", "wards_named": expected, "from_cache": True
            }
            continue
        labels = {}
        errors = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            jobs = {pool.submit(fetch_one, slug, ward): ward for ward in range(1, expected + 1)}
            for job in as_completed(jobs):
                number = jobs[job]
                try:
                    found_number, label = job.result()
                    labels[str(found_number)] = label
                except Exception as error:
                    errors.append(f"Ward {number}: {str(error)[:90]}")
        if len(labels) != expected:
            report["checks"][metro] = {
                "status": "error",
                "wards_named": len(labels),
                "expected": expected,
                "first_errors": errors[:5],
            }
            report["status"] = "partial"
            # Never publish a partial/mislabelled ward set.
            continue
        labels = {str(n): labels[str(n)] for n in range(1, expected + 1)}
        data["metros"][metro] = labels
        changed = True
        report["checks"][metro] = {
            "status": "ok", "wards_named": expected, "from_cache": False
        }

    if changed or not OUTPUT.exists():
        data["updated_at"] = now
        data["description"] = (
            "Areas covered by 2026 wards (not official ward names). "
            "Suburbs can belong to more than one ward."
        )
        data["source"] = "The Ledger SA individual 2026 ward pages; Stats SA places and MDB boundaries"
        OUTPUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report["areas_updated"] = changed
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
