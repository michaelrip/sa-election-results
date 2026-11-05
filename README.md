# Mzanzi Key Metro Watch

Mobile-friendly public dashboard with a South African flag-inspired background for Cape Town, Tshwane, Johannesburg and Hermanus / Overstrand: preliminary municipal ward-ballot results, sourced vote counts, district-counting progress, and ward drill-down.

## Website

Enable GitHub Pages in **Settings → Pages**: select **Deploy from a branch**, **main**, and **/(root)**, then Save.

Intended website: https://michaelrip.github.io/sa-election-results/

## Manual refresh and persistent navigation

The **Refresh** button checks the newest `results.json` published to GitHub Pages. It now gives an immediate checking state and then explicitly confirms whether a newer published snapshot was loaded, whether the publication is unchanged, or whether the network request failed. An unchanged result after pressing Refresh is not a broken button: **upstream ESP/IEC-derived imports run on the GitHub Actions schedule (roughly every 15 minutes)**, and the button does **not** force those upstream sources to update. The message shows the latest published snapshot and any recently failed source checks from `feed-status.json`. Failed network requests preserve the last downloaded figures.

The four-link bottom navigation (**News, Map, Votes, Wards**) is visible at both mobile and larger landscape/in-app browser viewports, with safe-area spacing and a self-contained CSS fallback even if `mobile.css` loads late. The stylesheet URL is versioned to avoid showing a cached earlier style that hid the dock. The malformed mobile city-selector CSS declaration was repaired.

For source robustness, the importer accepts the ward-ballot heading with or without a decorative question mark. If one ESP hostname omits the detailed ward-ballot table, it checks the alternate ESP hostname; the alternate source must still satisfy the existing municipality, date, party-vote and district-count validation. It never substitutes a vote-share estimate for ballot counts.

## Sources: ESP for live 2026, IEC for historical comparisons

**Live 2026 election results remain sourced through ESP's IEC-derived public election pages.** The website does not automatically switch to direct IEC 2026 reports; `.github/workflows/update-direct-iec.yml` is manual-only, solely as a technical diagnostic. Results, source labels and source URLs continue to identify ESP honestly. Automatic imports run every 15 minutes through `.github/workflows/check-iec.yml`.

The four 2021 municipality-wide **Ward, municipal PR and combined Ward + PR percentages** use real integer votes in directly verified official IEC CSVs (`history-iec-2021.json`). Combined historic shares are calculated from each party's Ward votes + municipal PR votes divided by the sum of all valid ballots across both; they are not an average of two percentages. Each party shows the corresponding 2021 percentage in brackets on the **Ward, PR and All local ballots** cards. Historic ward-area comparisons remain separate because voting-district boundaries may have changed. The Overberg district PR view does not receive an unrelated municipal 2021 comparison. Non-election sources are distinct: Municipal Demarcation Board boundaries, municipality/The Ledger geographic descriptions, and attributed news headlines. This is an independent dashboard, not an IEC service.

## PR, Ward, combined and district ballot views

All city vote cards have a four-way ballot selector (three choices for metros):

- **All local ballots (default):** for each party, add actual counted **Ward + municipal PR** votes, then divide by total valid Ward + PR ballot papers. The **2021 bracket** is the same Ward + municipal PR calculation applied to the complete 2021 election (from source vote counts). Both vote counts and residual unlisted parties/candidates are included in the current denominator. This reports **ballot papers, not unique voters**, and is **not** a prediction of seats. If the two source snapshots differ by more than 90 minutes, the combined figure is suppressed rather than mixing incompatible partial counts.
- **PR · Party vote:** each party's actual proportional-representation votes and percentage on the separate municipal PR ballot, with its **2021 municipal PR percentage in brackets** where available. The simplest direct view of voting for parties rather than ward candidates.
- **Ward vote:** each party's reported ward-candidate votes; independent candidates may also receive ward votes. Source-verified 2021 Ward ballot percentages are shown in brackets in this view (as they were previously).
- **District PR (Hermanus/Overstrand only):** a third, separate ballot electing representation on the **Overberg district council**. This ballot is explicitly excluded from the two-ballot local-council combined view because it elects a different council.

`scripts/update_party_ballots.py` fetches actual numbered party-vote rows from ESP's `?ballot=pr` and `?ballot=dc` pages; results are published in `ballots.json` and diagnostics in `ballot-status.json`. No party counts are reverse-engineered from rounded percentages. Unrecognised/unlisted candidate votes are grouped as **Other/unlisted** using the verified source ballot total minus individually recognised vote counts. The importer validates the municipality, 2026 year, timestamp, vote totals and shares, and retains recent validated cached figures only when live source checks are temporarily unavailable.

2021 comparisons use the completed 2021 election, while 2026 results remain provisional and partly counted. Party names absent from the 2021 source are **unknown**, not zero; no percentage-point change is presented as a final swing.

The existing interactive ward map remains colour-coded by **Ward** ballot. Individual ward result cards and map panels also link to their original ESP Ward and PR ballot pages, without claiming that the PR ballot elects a ward councillor. Source status and refresh messages track both Ward and PR updates.

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

The **Vote details by city** section displays **one municipality at a time** instead of stacking all four municipality party cards. A four-option city selector switches Cape Town, Tshwane, Johannesburg or Hermanus / Overstrand without a page reload. The selected city synchronizes with the 2026 interactive map and searchable ward list in both directions.

The overview shows voting-district progress and the selected ballot's sourced valid votes, with the top five parties/groups visible and a ballot-type switcher above it. Remaining reported parties are available in an accessible **Show more parties** expander. Bracketed 2021 ward-ballot comparisons remain available next to the corresponding current percentages. The header includes a **View votes by city** shortcut to the section, and the Cape Town-only DA majority watch is hidden when another metro is selected. The choice persists across the dashboard's regular data refreshes (within the current page visit).

## Hermanus / Overstrand (fourth location)

Hermanus is a town **within Overstrand Local Municipality**, not a metropolitan municipality. The fourth tab is labelled **Hermanus**, but the reported vote shares and counts always refer to **the whole Overstrand municipality**, including Hermanus, Gansbaai and Kleinmond, not the town alone. The results source is [ESP's 2026 Overstrand municipality page](https://go.esp.info/elections/local/2026/western-cape/overstrand).

The 2026 map uses the **15 official Overstrand ward polygons** from the Municipal Demarcation Board, verified against ward IDs 1–15. Ward-area names in `ward-areas.json` are from the [municipality's official new ward boundaries effective 4 November 2026](https://www.overstrand.gov.za/about-us/wards/). Overstrand's municipal 2021 ward-ballot percentages are sourced from ESP; no fabricated 2021 percentages are shown for individual 2026 Overstrand wards, because the boundaries have changed and the existing district-matching archive covers only the eight metros. When no verified 2026 results are available, the UI shows that data as pending rather than estimating votes.

## Theme and vote totals

The site title and sharing title are **Mzanzi Key Metro Watch**. Its background uses a locally hosted South African flag vector (`assets/sa-flag.svg`) behind a dark overlay, preserving contrast and legibility on phones.

Each city card shows **valid votes for the selected ballot(s)** when the ESP source publishes that count. The party rows show **actual party vote counts** where sourced and verified by ballot type; the combined view adds the Ward and municipal PR paper ballots rather than treating them as unique voters. Numbers are stored as integers in `results.json` under `metros[city].valid_votes` and `metros[city].parties[].votes`. Figures are refreshed by the existing importer.

**No vote numbers are estimated from rounded party percentages.** If the source contains only percentages, the corresponding party vote count is shown as unavailable. Individual ward vote totals are not currently available from the ward summary feed and remain unreported, rather than fabricated. These ward-ballot figures are not PR ballot totals or final seat allocations.

## Sourced election headlines

The website displays a scrollable, mobile-friendly news strip **above the ward map**, including publisher names, dates, direct story links where available, and topical labels for Cape Town, Tshwane, Johannesburg, Hermanus / Overstrand and national election coverage.

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

The page opens with one large interactive map and four location tabs: **Cape Town (118 wards), Tshwane (107), Johannesburg (135), and Hermanus / Overstrand (15)**. The map uses validated 2026 polygons from the [Municipal Demarcation Board's MDBWards2026 ArcGIS service](https://services7.arcgis.com/oeoyTUJC8HEeYsRB/arcgis/rest/services/MDBWards2026/FeatureServer/0).

- **Leading party** mode colours each ward by the current reported leader on the ward ballot. Grey means no result yet. These are **preliminary leaders, not declared councillors or final ward winners**.
- **Counting progress** mode shades wards by complete/partial/no reported district counts.
- Select any shaded ward to display its number, suburb/area labels, reported leading party, vote share, count progress and source timestamp. Open the same ward in the searchable result list.
- A municipality switcher, ward/suburb selector, full-area reset and hover labels work across desktop and mobile screens.
- The shapes live under `ward-boundaries/*.geojson` and are verified against the exact 2026 ward-number set before publication. The workflow `.github/workflows/update-ward-maps.yml` checks the MDB source and refreshes them.
- `ward-maps.js` handles the Leaflet drill-down. If a GeoJSON file is temporarily unavailable, it also tries the MDB ArcGIS service in the browser, and provides a clear error message if the service cannot be reached.

Map boundaries are **not** inferred from suburb-name strings. Neighbourhood descriptions come from the separate `ward-areas.json` file and are secondary labels only. Vote reporting remains independently sourced through ESP and shown with its own timestamp. Map tiles are provided by OpenStreetMap and may not load when offline.

## Automated data

GitHub Actions checks ESP's public 2026 local-election pages every **15 minutes**, and the browser reloads the published `results.json` every five minutes. The source is **IEC-derived through ESP**, **not** a direct official IEC API or a certified IEC declaration.

- `results.json`: latest validated provisional ward-ballot data for the four selected municipality areas, with a timestamp and source URLs.
- `feed-status.json`: last check and success/error details for each metro. A GitHub Actions green tick means *all four* municipality feeds passed validation.
- `scripts/fetch_results.py`: guarded importer. Source mismatch, stale timestamp, invalid vote shares, and lower district counts do not replace the last valid snapshot.
- `tests/test_fetch_results.py`: offline results parsing regression tests.
- `scripts/update_ward_areas.py`: imports factual area descriptions from each **individual 2026 ward page** at The Ledger SA, not from the election-night ward-status list. It validates each ward identity and rejects missing/incorrect area labels.
- `ward-areas.json`: geographic areas covered by each ward. The website displays these prominently and keeps the official ward number as a secondary identifier. Suburbs can span several wards; these are **not official names**.
- `ward-area-status.json`: validation and import status for all 118 Cape Town, 107 Tshwane, 135 Johannesburg and 15 Overstrand wards.
- `tests/test_ward_areas.py`: regression tests preventing party names and counting statuses from being mistaken for place names.

Ward cards display the **leading party** and reported percentage, *not* a declared ward councillor or winner. Council seats are intentionally not estimated from early ward votes. The website marks outdated snapshots and keeps unavailable data unavailable.

**Official results and declarations:** https://results.elections.org.za/

**Independent IEC-derived pages:** https://go.esp.info/elections/local/2026/

## Run manually

Open **Actions → Update four-area election results → Run workflow**.

For troubleshooting, inspect the `feed-status.json` report and the workflow's validation step. A source-format change may require updating the parser; the importer must not guess missing election results.
