# Mzanzi Key Metro Watch

Mobile-friendly public dashboard with a South African flag-inspired background for Cape Town, Tshwane and Johannesburg: preliminary municipal ward-ballot results, sourced vote counts, district-counting progress, and ward drill-down.

## Website

Enable GitHub Pages in **Settings → Pages**: select **Deploy from a branch**, **main**, and **/(root)**, then Save.

Intended website: https://michaelrip.github.io/sa-election-results/

## Mobile usability improvements

Mobile screens (up to 760 px wide) load `mobile.css` after the main styles. The live website URL does not change. Recent changes include:

- Fixed, safe-area-aware bottom links to **News**, **Map**, **Votes** and **Wards**, plus a fast **View votes by city** link in the header.
- Larger touch targets for map zoom, city selectors, search fields, news arrows, source links, ward actions and the ward popup's **See full ward breakdown** link.
- On touch devices, map dragging starts disabled so a finger swipe scrolls the page normally. Press **Move map** to enable dragging and **Done moving map** to restore page scrolling. Tap-to-select wards and zoom controls stay available either way.
- Collapsed party-colour legend and compact map controls on mobile; larger, more legible ward cards and a stacked single-column result view. The desktop presentation is unaffected.
- An initial batch of **24 wards**, followed by **Show more wards**. Search still checks every ward immediately, and rerendering preserves any expanded ward cards.
- News arrows activate only when their carousel genuinely overflows. Headline scrolling is preserved during refreshes.
- The main result snapshot renders first; optional ward details, labels and 2021 comparisons load concurrently and enrich it afterward. Polling is paused in hidden tabs and refreshed when the tab becomes visible to reduce background phone data/battery usage.
- Reduced-motion support and iPhone safe-area spacing.

No source counts, vote percentages, 2021 historical comparisons, maps or publisher attribution are altered by these layout changes.

## Mobile-friendly city selection

The **Vote details by city** section displays **one metro at a time** instead of stacking all three metro party cards. A three-button city selector switches Cape Town, Tshwane, or Johannesburg without a page reload. The selected city synchronizes with the 2026 interactive map and searchable ward list in both directions.

The overview highlights voting-district progress and sourced valid ward-ballot vote totals, with the top five party results visible. Remaining reported parties are available in an accessible **Show more parties** expander. Bracketed 2021 ward-ballot comparisons remain available next to the corresponding current percentages. The header includes a **View votes by city** shortcut to the section, and the Cape Town-only DA majority watch is hidden when another metro is selected. The choice persists across the dashboard's regular data refreshes (within the current page visit).

## Theme and vote totals

The site title and sharing title are **Mzanzi Key Metro Watch**. Its background uses a locally hosted South African flag vector (`assets/sa-flag.svg`) behind a dark overlay, preserving contrast and legibility on phones.

Each metro card shows **valid ward-ballot votes counted** when the ESP source publishes that value. The party rows show **actual party vote counts** when those votes appear as individually sourced, mathematically consistent vote rows. Numbers are stored as integers in `results.json` under `metros[city].valid_votes` and `metros[city].parties[].votes`. Figures are refreshed by the existing importer.

**No vote numbers are estimated from rounded party percentages.** If the source contains only percentages, the corresponding party vote count is shown as unavailable. Individual ward vote totals are not currently available from the ward summary feed and remain unreported, rather than fabricated. These ward-ballot figures are not PR ballot totals or final seat allocations.

## Sourced election headlines

The website displays a scrollable, mobile-friendly news strip **above the ward map**, including publisher names, dates, direct story links where available, and topical labels for Cape Town, Tshwane, Johannesburg and national election coverage.

`news.json` provides up to six attributed news links. `scripts/update_news.py` checks recent Google News RSS search feeds on an hourly GitHub Actions schedule (`.github/workflows/update-news.yml`), filters for relevant recent articles from established newsrooms, removes duplicates and prioritises at least one story for each metro where available. `news-status.json` records feed errors and accepted story counts. The browser rechecks `news.json` every 15 minutes. Older headlines are labelled by publication date, not presented as breaking news.

News reporting is **independent journalism, not certified IEC election data**. Feed failures retain recent previously sourced links instead of inventing headlines. Tests are in `tests/test_news.py`.

## Top-three parties in every ward drill-down

The election map and expandable ward cards show the **top three parties on the 2026 ward ballot**, with reported vote shares and actual vote counts whenever independently validated. This is not an estimate based on metro-wide results.

The normal `results.json` metro summary contains only each ward's leading party. `scripts/update_ward_details.py` collects the individual ESP ward-ballot pages, validates the first three ranked rows and vote counts, and checks that each detail matches its metro summary's leader, percentage and number of voting districts reported. It writes `ward-details.json` and a transparent `ward-detail-status.json` report. The main updater runs this after each metro feed refresh, with an upper limit of 180 new ward page requests per cycle to avoid overloading the source. Cached details are reused where the summary has not changed.

The browser merges ward details only if they still match the current summary and are no more than 24 hours old. If a ward has only its verified leading party or its detailed page cannot be validated, the UI **shows only available parties and says the rest are pending**. It never fills second or third place using metro estimates or outdated data. Tests: `tests/test_ward_top_three.py`.

## 2021 percentages in brackets

The current 2026 ward-ballot percentage is emphasized on every metro party card, ward card and ward-map drill-down. If a **sourced 2021 ward-ballot percentage** exists for the same party, it appears in muted brackets, for example **59.6% (2021: 57.8%)**.

The source is kept separately in `history-2021.json` and imported using `scripts/update_history_2021.py` with regression tests `tests/test_history_2021.py`. An independent weekly workflow (`.github/workflows/update-history-2021.yml`) checks the underlying historical sources:

- **Metro shares:** complete 2021 local-election *ward-ballot* results, via ESP's IEC-derived 2021 metro pages.
- **Ward shares:** the 2021 ward-ballot votes of voting districts now included in each **2026 ward**, from The Ledger SA individual `wards-2026/` pages. These are **not necessarily the official 2021 ward-area boundaries**, and new or changed voting districts may have no 2021 match. The importer retains how many districts were matched.
- Percentages are compared **only against the same ballot type**, and a party absent from the published 2021 top shares is **unknown, never zero**. Current 2026 values remain preliminary, so no percentage-point swing is presented as final.

The browser loads historical data alongside current results; if historical data is missing, the brackets are omitted without affecting current election results. The map and ward cards explain the boundary difference.

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
