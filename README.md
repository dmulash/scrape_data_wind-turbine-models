\# Wind Turbine Scraper

&#x20;

Scrapes wind turbine specs from \[en.wind-turbine-models.com](https://en.wind-turbine-models.com) and saves them to a CSV.

&#x20;

The included `wind\_turbines.csv` contains \~2,600 turbines already scraped, with fields like manufacturer, model, rated power, rotor diameter, hub height, weight breakdowns, generator/gearbox type, and more.

&#x20;

\## Files

&#x20;

\- `scrape\_wind\_turbines.py` — the scraper

\- `wind\_turbines.csv` — pre-scraped dataset

\- `turbine\_urls.json` — cached list of turbine URLs (auto-generated on first run)

\## Install dependencies

&#x20;

```bash

pip install requests beautifulsoup4 urllib3

```

&#x20;

\## Run

&#x20;

```bash

python scrape\_wind\_turbines.py

```

&#x20;

The script runs in two phases:

&#x20;

1\. \*\*Collect URLs\*\* — walks all manufacturer pages to build a list of turbine URLs (cached in `turbine\_urls.json` so it won't repeat on subsequent runs)

2\. \*\*Scrape turbines\*\* — visits each turbine page and appends rows to `wind\_turbines.csv`, skipping any already present

Both phases resume safely if interrupted.

