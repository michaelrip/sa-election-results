"""Refresh national 2026 ward-ballot figures from the same IEC-derived ESP pages as metro results."""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fetch_results import get, WARD_BALLOT_HEADER

URLS = [
    "https://go.esp.info/elections/local/2026",
    "https://esp.info/elections/local/2026",
]
DEST = Path("national-results.json")
STATUS = Path("national-status.json")
PARTY_NAMES = [
    ("African National Congress", "ANC"),
    ("Democratic Alliance", "DA"),
    ("Umkhonto Wesizwe Party", "MK"),
    ("Economic Freedom Fighters", "EFF"),
    ("Inkatha Freedom Party", "IFP"),
    ("ActionSA", "ActionSA"),
    ("Vryheidsfront Plus", "FF+"),
    ("Freedom Front Plus", "FF+"),
    ("Patriotic Alliance", "PA"),
    ("South African Communist Party", "SACP"),
    ("United Democratic Movement", "UDM"),
    ("African Transformation Movement", "ATM"),
    ("National Coloured Congress", "CCC"),
    ("Rise Mzansi", "RISE"),
]
PARTY_CODES = {"MKP": "MK", "VF PLUS": "FF+", "ANC": "ANC", "DA": "DA", "EFF": "EFF",
               "IFP": "IFP", "PA": "PA", "SACP": "SACP", "UDM": "UDM", "ATM": "ATM",
               "ActionSA": "ActionSA", "RISE": "RISE"}


def party_name(fragment):
    for label, code in PARTY_NAMES:
        if re.search(r"(?<![A-Za-z])" + re.escape(label) + r"(?![A-Za-z])", fragment, re.I):
            return code
    for label, code in PARTY_CODES.items():
        if re.search(r"(?<![A-Za-z])" + re.escape(label) + r"(?![A-Za-z])", fragment, re.I):
            return code
    return None


def parse(text, url, now):
    if "2026" not in text or "National" not in text:
        raise ValueError("Not the national 2026 election page")
    m = re.search(r"Counting\s+([\d\s]+)\s+of\s+([\d\s]+)\s+voting districts in", text, re.I)
    if not m:
        raise ValueError("National district count missing")
    count, total = [int(re.sub(r"\s", "", x)) for x in m.groups()]
    if total != 23696 or not 0 < count <= total:
        raise ValueError("Unexpected district denominator or count")
    timestamp = re.search(r"IEC data last fetched\s+(\d{1,2}\s+\w+\s+2026,\s*\d{2}:\d{2})\s*SAST", text)
    if not timestamp:
        raise ValueError("Source timestamp missing")
    stamp = None
    for fmt in ("%d %b %Y, %H:%M", "%d %B %Y, %H:%M"):
        try:
            stamp = datetime.strptime(timestamp.group(1), fmt).replace(
                tzinfo=timezone(timedelta(hours=2))).astimezone(timezone.utc)
            break
        except ValueError:
            pass
    if stamp is None or stamp > now + timedelta(minutes=10) or now - stamp > timedelta(hours=24):
        raise ValueError("Source timestamp invalid or stale")
    header = WARD_BALLOT_HEADER.search(text)
    if not header:
        raise ValueError("Ward ballot valid-vote header missing")
    valid = int(re.sub(r"\D", "", header.group(1)))
    if valid < 1000:
        raise ValueError("Unexpected national valid votes")
    tail = text[header.end():]
    end = re.search(r"\b(?:Provinces\s*[·•]|How long is the queue|About these figures)\b", tail, re.I)
    section = tail[:end.start()] if end else tail[:25000]
    parties = []
    previous = 0
    for match in re.finditer(r"(?<!\d)(\d{1,3}(?:\s+\d{3})*)\s+(\d{1,3}\.\d)\s*%", section):
        fragment = section[previous:match.start()]
        previous = match.end()
        name = party_name(fragment[-180:])
        votes = int(re.sub(r"\s", "", match.group(1)))
        share = float(match.group(2))
        if not name or name in {p["name"] for p in parties}:
            continue
        if votes > valid or abs(100 * votes / valid - share) > 0.21:
            continue
        parties.append({"name": name, "votes": votes, "share": share})
    parties.sort(key=lambda p: -p["votes"])
    if len(parties) < 7 or not {"ANC", "DA", "MK", "EFF", "IFP", "ActionSA"}.issubset(
        {p["name"] for p in parties}
    ):
        raise ValueError("National party-vote rows incomplete")
    if sum(p["votes"] for p in parties) > valid:
        raise ValueError("Party votes exceed valid ballots")
    return {
        "updated_at": stamp.isoformat(),
        "source": "Provisional IEC-derived national ward-ballot results via ESP (unofficial)",
        "source_url": url,
        "districts_reported": count,
        "districts_total": total,
        "valid_votes": valid,
        "parties": parties,
    }


def main():
    now = datetime.now(timezone.utc)
    existing = json.loads(DEST.read_text(encoding="utf-8")) if DEST.exists() else {}
    status = {"checked_at": now.isoformat(), "status": "error"}
    errors = []
    for url in URLS:
        try:
            incoming = parse(get(url), url, now)
            if incoming["districts_reported"] < existing.get("districts_reported", 0):
                raise ValueError("District count regressed")
            previous_stamp = existing.get("updated_at")
            if previous_stamp and datetime.fromisoformat(incoming["updated_at"]) < datetime.fromisoformat(
                previous_stamp.replace("Z", "+00:00")
            ):
                raise ValueError("Source timestamp regressed")
            # Always write the verified payload, even if an earlier run published a status
            # without the corresponding national-results.json change.
            DEST.write_text(json.dumps(incoming, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            published = json.loads(DEST.read_text(encoding="utf-8"))
            if published["districts_reported"] != incoming["districts_reported"] or published["updated_at"] != incoming["updated_at"]:
                raise ValueError("National results write verification failed")
            status.update(status="ok", source_url=url,
                          districts_reported=incoming["districts_reported"],
                          source_updated_at=incoming["updated_at"])
            break
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    if status["status"] != "ok":
        status["errors"] = errors
        print("National results unchanged:", "; ".join(errors))
    STATUS.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
