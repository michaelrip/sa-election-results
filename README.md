# SA Metro Election Watch

Mobile-friendly public dashboard for Cape Town, Tshwane and Johannesburg: preliminary municipal ward-ballot vote shares, district-counting progress, and ward drill-down.

## Website

Enable GitHub Pages in **Settings → Pages**: select **Deploy from a branch**, **main**, and **/(root)**, then Save.

Intended website: https://michaelrip.github.io/sa-election-results/

## Sourced election headlines

The website displays a scrollable, mobile-friendly news strip **above the ward map**, including publisher names, dates, direct story links where available, and topical labels for Cape Town, Tshwane, Johannesburg and national election coverage.

`news.json` provides up to six attributed news links. `scripts/update_news.py` checks recent Google News RSS search feeds on an hourly GitHub Actions schedule (`.github/workflows/update-news.yml`), filters for relevant recent articles from established newsrooms, removes duplicates and prioritises at least one story for each metro where available. `news-status.json` records feed errors and accepted story counts. The browser rechecks `news.json` every 15 minutes. Older headlines are labelled by publication date, not presented as breaking news.

News reporting is **independent journalism, not certified IEC election data**. Feed failures retain recent previously sourced links instead of inventing headlines. Tests are in `tests/test_news.py`.

## Interactive 2026 ward map

The page opens with one large interactive map and three metro tabs: **Cape Town (118 wards), Tshwane (107), and Johannesburg (135)**. The map uses validated 2026 polygons from the [Municipal Demarcation Board's MDBWards2026 ArcGIS service](https://services7.arcgis.com/oeoyTUJC8HEeYsRB/arcgis/rest/services/MDBWards2026/FeatureServer/0).

- **Leading party** mode colours each ward by the current reported leader on the ward ballot. Grey means no result yet. These are **preliminary leaders, not declared councillors or final ward winners**.
- **Counting progress** mode shades wards by complete/partial/no reported district counts.
- Select any shaded ward to display its number, suburb/area labels, reported leading party, vote share, count progress and source timestamp. Open the same ward in the searchable result list.
- A metro switcher, ward/suburb selector, full-area reset and hover labels work across desktop and mobile screens.
- The shapes live under `ward-boundaries/*.geojson` and are verified against the exact 2026 ward-number set before publication. The workflow `.github/workflows/update-ward-maps.yml` checks the MDB source and refreshes them.
- `ward-maps.js` handles the Leaflet drill-down. If a GeoJSON file is temporarily unavailable, it also tries the MDB ArcGIS service in the browser, and provides a clear error message if the service cannot be reached.

Map boundaries are **not** inferred from suburb-name strings. Neighbourhood descriptions come from the separate `ward-areas.json` file and are secondary labels only. Vote reporting remains independently sourced through ESP and shown with its own timestamp. Map tiles are provided by OpenStreetMap and may not load when offline.

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
