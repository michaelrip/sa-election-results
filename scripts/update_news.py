"""Curate recent South African 2026 municipal election headlines via RSS.

Shows attributed links to original reporting, not copied articles. Feed failures
keep existing links rather than inventing stories. Headlines are not live results.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

DEST = Path("news.json")
STATUS = Path("news-status.json")
NEWS_HOME = "https://news.google.com/rss/search"
QUERIES = [
    "Cape Town 2026 local government election when:3d",
    "Tshwane Pretoria 2026 local government election when:3d",
    "Johannesburg 2026 local government election when:3d",
    "South Africa municipal election 2026 results when:3d",
    "Hermanus Overstrand 2026 municipal election results when:3d",
]
TRUSTED = {
    "reuters", "associated press", "ap news", "sabc news",
    "eyewitness news", "ewn", "news24", "daily maverick",
    "timeslive", "the guardian", "financial times",
    "mail & guardian", "groundup", "the citizen",
    "businesslive", "business day", "enca", "iol",
    "sowetanlive", "city press", "the outlier",
}
CITY_TERMS = {
    "Cape Town": ("cape town", "city of cape town"),
    "Tshwane": ("tshwane", "pretoria"),
    "Johannesburg": ("johannesburg", "joburg", "soweto"),
    "Hermanus": ("hermanus", "overstrand", "gansbaai", "kleinmond"),
}
ELECTION_TERMS = re.compile(
    r"\b(election|electoral|municipal|ward|coalition|counting|"
    r"ballot|vote|voting|polls|mayor|council|IEC)\b", re.I
)
LOCAL_TERMS = re.compile(
    r"\b(south africa|south african|cape town|tshwane|pretoria|"
    r"johannesburg|joburg|soweto|IEC|ANC|DA|ActionSA|EFF|"
    r"local govt|local government)\b", re.I
)
MAX_STORIES = 10
MAX_AGE = timedelta(days=5)


def clean(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", "", str(value or "")).split())


def published(value: str, now: datetime) -> datetime | None:
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
    except (ValueError, TypeError, IndexError):
        return None
    if dt < now - MAX_AGE or dt > now + timedelta(minutes=15):
        return None
    return dt


def choose_metro(text: str) -> str:
    normalized = text.casefold()
    matches = [
        name for name, terms in CITY_TERMS.items()
        if any(term in normalized for term in terms)
    ]
    return matches[0] if len(matches) == 1 else "South Africa"


def safe_link(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and not parsed.username
        and not parsed.password
        and parsed.hostname.lower() not in ("localhost", "127.0.0.1")
        and len(url) <= 2000
    )


def parse_rss(xml_bytes: bytes, now: datetime) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    if root.tag != "rss":
        raise ValueError("Not an RSS document")
    articles = []
    for item in root.findall("./channel/item"):
        title = clean(item.findtext("title"))
        url = clean(item.findtext("link"))
        publisher = clean(item.findtext("source"))
        source = publisher.casefold().strip()
        if source not in TRUSTED:
            continue
        suffix = " - " + publisher
        if title.casefold().endswith(suffix.casefold()):
            title = title[:-len(suffix)].strip()
        if not 15 <= len(title) <= 220 or not safe_link(url):
            continue
        dt = published(item.findtext("pubDate"), now)
        if dt is None:
            continue
        description = clean(item.findtext("description"))[:900]
        topic = title + " " + description
        if not ELECTION_TERMS.search(topic) or not LOCAL_TERMS.search(topic):
            continue
        articles.append({
            "title": title,
            "publisher": publisher,
            "url": url,
            "published_at": dt.isoformat().replace("+00:00", "Z"),
            "published_date": dt.date().isoformat(),
            "metro": choose_metro(title),
        })
    return articles


def fetch_rss(query: str) -> bytes:
    args = urllib.parse.urlencode({
        "q": query, "hl": "en-ZA", "gl": "ZA", "ceid": "ZA:en",
    })
    req = urllib.request.Request(
        NEWS_HOME + "?" + args,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SA-Metro-Watch/1.0)",
            "Accept": "application/rss+xml,application/xml,text/xml",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        if resp.status != 200:
            raise ValueError(f"RSS HTTP {resp.status}")
        payload = resp.read(1_500_001)
        if len(payload) > 1_500_000:
            raise ValueError("RSS feed too large")
        return payload


def when(article: dict) -> datetime:
    raw = article.get("published_at") or article.get("published_date") or ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def valid_existing(article: dict, now: datetime) -> bool:
    if not isinstance(article, dict):
        return False
    date = when(article)
    return (
        now - MAX_AGE <= date <= now + timedelta(days=1)
        and 15 <= len(str(article.get("title", ""))) <= 220
        and 2 <= len(str(article.get("publisher", ""))) <= 80
        and safe_link(str(article.get("url", "")))
        and article.get("metro") in (*CITY_TERMS.keys(), "South Africa")
    )


def select_stories(articles: list[dict], now: datetime) -> list[dict]:
    unique = {}
    for article in articles:
        if not valid_existing(article, now):
            continue
        key = re.sub(r"\W+", "", article["title"].casefold())
        if not key:
            continue
        if key not in unique or when(article) > when(unique[key]):
            unique[key] = article
    latest = sorted(unique.values(), key=when, reverse=True)
    chosen = []
    used = set()
    # A top-story slot for each metro, where a recent headline is available.
    for metro in CITY_TERMS:
        for article in latest:
            key = article["title"]
            if article["metro"] == metro and key not in used:
                chosen.append(article)
                used.add(key)
                break
    for article in latest:
        if len(chosen) >= MAX_STORIES:
            break
        if article["title"] not in used:
            chosen.append(article)
            used.add(article["title"])
    return chosen[:MAX_STORIES]


def main() -> None:
    now = datetime.now(timezone.utc)
    prev = json.loads(DEST.read_text(encoding="utf-8")) if DEST.exists() else {"articles": []}
    old = prev.get("articles") if isinstance(prev.get("articles"), list) else []
    found = []
    checks = []
    for query in QUERIES:
        try:
            items = parse_rss(fetch_rss(query), now)
            found.extend(items)
            checks.append({"query": query, "status": "ok", "eligible": len(items)})
        except Exception as exc:
            checks.append({"query": query, "status": "error", "detail": str(exc)[:150]})
    articles = select_stories(found + old, now)
    status = "ok" if found else "unavailable"
    output = {
        "checked_at": now.isoformat().replace("+00:00", "Z"),
        "source": "Publisher-attributed headlines discovered through Google News RSS",
        "feed_status": status,
        "articles": articles,
    }
    DEST.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    STATUS.write_text(json.dumps({
        "checked_at": output["checked_at"],
        "status": status,
        "new_eligible_items": len(found),
        "published_items": len(articles),
        "checks": checks,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "eligible": len(found), "published": len(articles), "checks": checks}, indent=2))


if __name__ == "__main__":
    main()
