# Wind Turbine Scraper

Scrapes wind turbine specs from \[en.wind-turbine-models.com](https://en.wind-turbine-models.com) and saves them to a CSV.

The included `wind_turbines.csv` contains \~2,600 turbines already scraped, with fields like manufacturer, model, rated power, rotor diameter, hub height, weight breakdowns, generator/gearbox type, and more.

## Files

- `scrape_wind_turbines.py` — the scraper

- `wind_turbines.csv` — scraped dataset

- `turbine_urls.json` — cached list of turbine URLs (auto-generated on first run)

## Install dependencies

```bash

pip install requests beautifulsoup4 urllib3

```

## Run

```bash

python scrape_wind_turbines.py

```

The script runs in two phases:

1. **Collect URLs** — walks all manufacturer pages to build a list of turbine URLs (cached in `turbine_urls.json` so it won't repeat on subsequent runs)

2. **Scrape turbines** — visits each turbine page and appends rows to `wind_turbines.csv`, skipping any already present

Both phases resume safely if interrupted.

