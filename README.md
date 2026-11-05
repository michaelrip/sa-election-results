# SA Metro Election Watch

Public mobile-friendly dashboard for Cape Town, Tshwane and Johannesburg, with ward search and expandable ward details.

## Enable GitHub Pages
Open **Settings → Pages** in this repository. Under **Build and deployment**, choose **Deploy from a branch**, select **main** and **/(root)**, then **Save**. URL: https://michaelrip.github.io/sa-election-results/

## Data
The website checks `results.json` every five minutes. **There is not yet an automatic verified election-results feed.** The initial data is intentionally empty. Never present unverified or outdated results as live. Each metro may have `status`, `ballot_type`, `districts_reported`, `districts_total`, `parties` (`name`, `share`), `seats` (`name`, `count`), `wards` (array), `snapshot_at` and `source_url`. Each ward may have `number`, `status`, `ballot_type`, `reporting`, `parties`, `winner`, `snapshot_at`, `source_url`. Do not infer seats from preliminary vote shares. Official source: https://results.elections.org.za/
