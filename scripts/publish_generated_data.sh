#!/usr/bin/env bash
# Publish freshly generated data against the CURRENT main branch, even when
# this Actions run started from an older commit. Never force-push or rebase
# generated JSON over edited JSON: restore the files after fetching main.
set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "Usage: $0 <status-json> <commit-message> <generated-file...>" >&2
  exit 2
fi
status_file="$1"
message="$2"
shift 2

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

bundle="$(mktemp -d)"
trap 'rm -rf "$bundle"' EXIT
for file in "$@"; do
  if [ ! -f "$file" ]; then
    echo "Missing expected generated file: $file" >&2
    exit 1
  fi
  mkdir -p "$bundle/$(dirname "$file")"
  cp "$file" "$bundle/$file"
done

for attempt in 1 2 3 4 5; do
  echo "Publishing against latest origin/main (attempt $attempt/5)"
  git fetch origin main
  # Reset is safe: generated output is preserved in the temporary bundle.
  # Unlike rebasing an old generated commit, this cannot conflict with later
  # changes to those same data files.
  git reset --hard origin/main

  python - "$bundle" "$status_file" "$@" <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import json
import shutil
import sys

bundle = Path(sys.argv[1])
status_name = sys.argv[2]
files = sys.argv[3:]

def checked_at(path):
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    value = data.get("checked_at")
    if not isinstance(value, str) or not value:
        raise ValueError("Missing checked_at in " + str(path))
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Source timestamp must have a timezone")
    return parsed.astimezone(timezone.utc)

incoming = checked_at(bundle / status_name)
existing = checked_at(Path(status_name))
if incoming is None:
    raise SystemExit("Missing incoming status timestamp")
if existing is not None and existing >= incoming:
    print("Newer or same-age data already published; do not regress.")
else:
    for name in files:
        source = bundle / name
        target = Path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    print("Applying validated data, checked at", incoming.isoformat())
PY

  git add -- "$@"
  if git diff --cached --quiet; then
    echo "Published data is already current."
    exit 0
  fi
  git commit -m "$message"
  if git push origin HEAD:main; then
    echo "Published current data successfully."
    exit 0
  fi
  echo "main advanced during push; retrying safely."
  sleep 2
done
echo "Failed to publish after 5 safe retries." >&2
exit 1
