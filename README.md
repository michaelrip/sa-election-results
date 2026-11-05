# SA Metro Election Watch

Mobile-friendly public dashboard for Cape Town, Tshwane and Johannesburg: preliminary municipal ward-ballot vote shares, district-counting progress, and ward drill-down.

## Website

Enable GitHub Pages in **Settings → Pages**: select **Deploy from a branch**, **main**, and **/(root)**, then Save.

Intended website: https://michaelrip.github.io/sa-election-results/

## Automated data

GitHub Actions checks ESP's public 2026 local-election pages every **15 minutes**, and the browser reloads the published `results.json` every five minutes. The source is **IEC-derived through ESP**, **not** a direct official IEC API or a certified IEC declaration.

- `results.json`: latest validated provisional ward-ballot data for the three metros, with a timestamp and source URLs.
- `feed-status.json`: last check and success/error details for each metro. A GitHub Actions green tick means *all three* feeds passed validation.
- `scripts/fetch_results.py`: guarded importer. Source mismatch, stale timestamp, invalid vote shares, and lower district counts do not replace the last valid snapshot.
- `tests/test_fetch_results.py`: offline results parsing regression tests.
- `scripts/update_ward_areas.py`: imports factual area descriptions from each **individual 2026 ward page** at The Ledger SA, not from the election-night ward-status list. It validates each ward identity and rejects missing/incorrect area labels.
- `ward-areas.json`: geographic areas covered by each ward. The website displays these prominently and keeps the official ward number as a secondary identifier. Suburbs can span several wards; these are **not official names**.
- `ward-area-status.json`: validation and import status for all 118 Cape Town, 107 Tshwane, and 135 Johannesburg wards.
- `tests/test_ward_areas.py`: regression tests preventing party names and counting statuses from being mistaken for place names.

Ward cards display the **leading party** and reported percentage, *not* a declared ward councillor or winner. Council seats are intentionally not estimated from early ward votes. The website marks outdated snapshots and keeps unavailable data unavailable.

**Official results and declarations:** https://results.elections.org.za/

**Independent IEC-derived pages:** https://go.esp.info/elections/local/2026/

## Run manually

Open **Actions → Update three-metro election results → Run workflow**.

For troubleshooting, inspect the `feed-status.json` report and the workflow's validation step. A source-format change may require updating the parser; the importer must not guess missing election results.
