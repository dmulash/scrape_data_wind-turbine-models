import requests
import csv
import time
import os
import re
import json
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Configuration ──────────────────────────────────────────────────────────────
BASE          = "https://en.wind-turbine-models.com"
DELAY         = 1.0          # seconds between requests
OUTPUT_CSV    = "wind_turbines.csv"
URL_CACHE     = "turbine_urls.json"   # cache of discovered turbine URLs
# ──────────────────────────────────────────────────────────────────────────────

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

CSV_FIELDS = [
    "id", "url", "manufacturer", "model",
    "rated_power_kw", "rotor_diameter_m", "rotor_area_m2", "num_blades",
    "hub_height_m", "cut_in_wind_speed_ms", "cut_out_wind_speed_ms",
    "rated_wind_speed_ms", "rotor_speed_rpm",
    "generator_type", "gearbox_type", "tower_type",
    "nacelle_weight_kg", "rotor_weight_kg", "tower_weight_kg", "blade_weight_kg", "total_weight_kg",
    "voltage_v", "frequency_hz",
    "installation", "offshore", "onshore",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def get(url, retries=3):
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=20, verify=False)
            return r
        except requests.RequestException as e:
            print(f"    Network error ({attempt+1}/{retries}): {e}")
            time.sleep(3)
    return None


def clean(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_first_number(text):
    """
    Extracts the first valid integer or float from a text string.
    Handles thousands separated by commas (e.g., '1,100.0 t' -> 11000.0)
    Converts tons (t) to kilograms (kg) if a mass field is detected.
    """
    if not text:
        return ""
    
    raw_val = text.strip()
    
    # Remove commas used as thousand-separators
    normalized = raw_val.replace(",", "")
    match = re.search(r"[-+]?\d*\.\d+|\d+", normalized)
    if not match:
        return ""
        
    val = float(match.group(0))
    
    # If the text indicates metric tons 't', convert to kg natively for your schema
    if " t" in raw_val or raw_val.endswith("t"):
        val = val * 1000.0
        
    # Format back cleanly to strip trailing zeroes if it's a whole number
    return str(int(val)) if val.is_integer() else str(val)


# ── Phase 1: collect all turbine URLs ────────────────────────────────────────

def get_manufacturer_ids():
    """Scrape all manufacturer IDs from the paginated manufacturers list."""
    ids = []
    page = 1
    while True:
        url = f"{BASE}/manufacturers?p={page}"
        print(f"  Fetching manufacturer list page {page} …")
        r = get(url)
        if not r or r.status_code != 200:
            break
        soup = BeautifulSoup(r.text, "html.parser")
        found = 0
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = re.search(r"/manufacturers/(\d+)", href)
            if m:
                mid = int(m.group(1))
                if mid not in ids:
                    ids.append(mid)
                    found += 1
                    
        if found == 0:
            break
            
        page_links = soup.find_all("a", href=re.compile(r"\?.*p=\d+"))
        max_p = page
        for link in page_links:
            pm = re.search(r"p=(\d+)", link["href"])
            if pm:
                max_p = max(max_p, int(pm.group(1)))
                
        if max_p <= page:
            break
            
        page += 1
        time.sleep(DELAY)
        
    print(f"  Found {len(ids)} manufacturers.")
    return ids


def get_turbine_urls_for_manufacturer(mid):
    """Return all turbine page URLs for a given manufacturer ID."""
    urls = []
    page = 1
    while True:
        url = f"{BASE}/turbines?manufacturer={mid}&p={page}"
        r = get(url)
        if not r or r.status_code != 200:
            break
        soup = BeautifulSoup(r.text, "html.parser")
        found = 0
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/turbines/" in href:
                m = re.search(r"/turbines/(\d+)-", href)
                if m:
                    full = href if href.startswith("http") else BASE + href
                    if full not in urls:
                        urls.append(full)
                        found += 1
        if found == 0:
            break
            
        has_next = False
        page_links = soup.find_all("a", href=re.compile(rf"p={page+1}"))
        if page_links:
            has_next = True
            
        if not has_next:
            break
            
        page += 1
        time.sleep(DELAY * 0.5)
    return urls


def collect_all_turbine_urls():
    """Phase 1: return list of all turbine URLs (with caching)."""
    if os.path.exists(URL_CACHE):
        with open(URL_CACHE) as f:
            data = json.load(f)
        print(f"Loaded {len(data['urls'])} turbine URLs from cache ({URL_CACHE}).")
        print(f"  Manufacturers already done: {len(data['done_mfr'])}")
        return data["urls"], set(data["done_mfr"])

    return [], set()


def save_url_cache(urls, done_mfr):
    with open(URL_CACHE, "w") as f:
        json.dump({"urls": urls, "done_mfr": list(done_mfr)}, f)


def build_url_list():
    all_urls, done_mfr = collect_all_turbine_urls()

    print("\n── Phase 1: Collecting turbine URLs ──────────────────────────────")
    mfr_ids = get_manufacturer_ids()

    new_mfr = [mid for mid in mfr_ids if mid not in done_mfr]
    print(f"  {len(new_mfr)} manufacturers left to scan …")

    for i, mid in enumerate(new_mfr, 1):
        urls = get_turbine_urls_for_manufacturer(mid)
        before = len(all_urls)
        for u in urls:
            if u not in all_urls:
                all_urls.append(u)
        added = len(all_urls) - before
        done_mfr.add(mid)
        print(f"  [{i}/{len(new_mfr)}] mfr={mid}  {added} new URLs  (total {len(all_urls)})")
        save_url_cache(all_urls, done_mfr)
        time.sleep(DELAY)

    print(f"\n  Total turbine URLs collected: {len(all_urls)}")
    return all_urls


# ── Phase 2: scrape each turbine page ─────────────────────────────────────────

def apply_field_with_context(row, label_text, value_text, parent_section):
    """
    Normalizes input labels and combines context keywords to properly match fields
    even when labels are nested under headers (e.g., 'Type' under Gearbox vs Tower).
    """
    lbl = re.sub(r"[^\w\s]", "", label_text.lower().strip())
    val = value_text.strip()
    sec = parent_section.lower().strip()
    
    if not val or val in ("-", "unknown"):
        return

    # 1. Power Parameters
    if "rated power" in lbl or "nominal power" in lbl:
        row["rated_power_kw"] = extract_first_number(val)
    elif "cutin" in lbl:
        row["cut_in_wind_speed_ms"] = extract_first_number(val)
    elif "cutout" in lbl:
        row["cut_out_wind_speed_ms"] = extract_first_number(val)
    elif "rated wind speed" in lbl:
        row["rated_wind_speed_ms"] = extract_first_number(val)
        
    # 2. Rotor Parameters
    elif "diameter" in lbl and ("rotor" in sec or "rotor" in lbl):
        row["rotor_diameter_m"] = extract_first_number(val)
    elif "swept area" in lbl or "rotor area" in lbl:
        row["rotor_area_m2"] = extract_first_number(val)
    elif "number of blades" in lbl or "rotor blades" in lbl:
        row["num_blades"] = extract_first_number(val)
    elif "rotor speed" in lbl or ("speed max" in lbl and "rotor" in sec):
        row["rotor_speed_rpm"] = extract_first_number(val)
        
    # 3. Component Details
    elif "generator" in sec and "type" in lbl:
        row["generator_type"] = val
    elif "generator type" in lbl:
        row["generator_type"] = val
    elif ("gear box" in sec or "gearbox" in sec) and "type" in lbl:
        row["gearbox_type"] = val
    elif "gearbox type" in lbl or "drive type" in lbl:
        row["gearbox_type"] = val
    elif ("tower" in sec or "turm" in sec) and "type" in lbl:
        row["tower_type"] = val
    elif "tower type" in lbl:
        row["tower_type"] = val
    elif "hub height" in lbl:
        row["hub_height_m"] = extract_first_number(val)
        
    # 4. Comprehensive Weight Allocations (Matches raw titles under 'weight' heading)
    elif "weight" in sec or "gewichte" in sec or "weight" in lbl:
        if "nacelle" in lbl or "gondel" in lbl:
            row["nacelle_weight_kg"] = extract_first_number(val)
        elif "rotor" in lbl and "blade" not in lbl:
            row["rotor_weight_kg"] = extract_first_number(val)
        elif "tower" in lbl or "turm" in lbl:
            row["tower_weight_kg"] = extract_first_number(val)
        elif "single blade" in lbl or "per blade" in lbl or "blade weight" in lbl:
            row["blade_weight_kg"] = extract_first_number(val)
        elif "total weight" in lbl or "overall weight" in lbl or lbl == "weight":
            row["total_weight_kg"] = extract_first_number(val)
            
    # 5. Grid/Electrical Specifications
    elif "voltage" in lbl:
        row["voltage_v"] = extract_first_number(val)
    elif "grid frequency" in lbl or "frequency" in lbl:
        row["frequency_hz"] = val

    # 6. Miscellaneous (data-tabname="sonstiges")
    elif "installation" in lbl:
        row["installation"] = val
    elif "offshore" in lbl:
        row["offshore"] = val
    elif "onshore" in lbl:
        row["onshore"] = val


def parse_turbine_page(html, url):
    soup = BeautifulSoup(html, "html.parser")
    row = {f: "" for f in CSV_FIELDS}

    m = re.search(r"/turbines/(\d+)-", url)
    row["id"]  = m.group(1) if m else ""
    row["url"] = url

    # Extract Model Name
    h1 = soup.find("h1")
    if h1:
        row["model"] = clean(h1.get_text())

    # Extract Manufacturer Name
    for a in soup.select("ol.breadcrumb a, ul.breadcrumb a, .breadcrumb a"):
        txt = clean(a.get_text())
        if txt and txt not in ("Start", "Turbines", row["model"], ""):
            row["manufacturer"] = txt
            break
    if not row["manufacturer"]:
        a = soup.find("a", href=re.compile(r"/turbines\?manufacturer="))
        if a:
            row["manufacturer"] = clean(a.get_text())

    # Find and cross-reference all structured rows across the entire tree
    for block in soup.find_all(["div", "tr"]):
        label_text = ""
        val_text = ""
        
        # Grid Architecture Check
        if block.name == "div" and "col-left" in block.get("class", []):
            label_text = block.get_text()
            sib = block.find_next_sibling("div", class_="col-right")
            if sib:
                val_text = sib.get_text()
        # Table Architecture Check
        elif block.name == "tr":
            cells = block.find_all(["td", "th"])
            if len(cells) >= 2:
                label_text = cells[0].get_text()
                val_text = cells[1].get_text()
                
        if not label_text or not val_text:
            continue

        # Look up parent components to provide section context
        parent_section = ""
        parent_tab = block.find_parent("div", class_="TabContent")
        if parent_tab and parent_tab.get("data-tabname"):
            parent_section = parent_tab["data-tabname"]
        
        if not parent_section:
            prev_h3 = block.find_previous("h3")
            if prev_h3:
                parent_section = prev_h3.get_text()

        apply_field_with_context(row, label_text, val_text, parent_section)

    return row


def load_done_urls():
    done = set()
    if os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("url"):
                    done.add(r["url"])
    return done


def scrape_turbines(all_urls):
    done_urls = load_done_urls()
    remaining = [u for u in all_urls if u not in done_urls]
    print(f"\n── Phase 2: Scraping turbine pages ───────────────────────────────")
    print(f"  {len(done_urls)} already done, {len(remaining)} remaining.")

    file_exists = os.path.exists(OUTPUT_CSV)
    out = open(OUTPUT_CSV, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(out, fieldnames=CSV_FIELDS)
    if not file_exists:
        writer.writeheader()

    saved = 0
    try:
        for i, url in enumerate(remaining, 1):
            r = get(url)
            if not r:
                print(f"  [{i}/{len(remaining)}] FAILED: {url}")
                time.sleep(DELAY)
                continue
            if r.status_code == 404:
                print(f"  [{i}/{len(remaining)}] 404: {url}")
                time.sleep(DELAY * 0.3)
                continue
            if r.status_code != 200:
                print(f"  [{i}/{len(remaining)}] HTTP {r.status_code}: {url}")
                time.sleep(DELAY)
                continue

            row = parse_turbine_page(r.text, url)
            if not row["model"]:
                time.sleep(DELAY * 0.5)
                continue

            writer.writerow(row)
            out.flush()
            saved += 1

            weight_parts = " ".join(
                f"{k.replace('_weight_kg','')}={row[k]}"
                for k in ("nacelle_weight_kg", "rotor_weight_kg", "tower_weight_kg", "blade_weight_kg", "total_weight_kg")
                if row[k]
            )
            print(f"  [{i}/{len(remaining)}] {row['manufacturer']} {row['model']}  "
                  f"{row['rated_power_kw']} kW  {weight_parts}")

            time.sleep(DELAY)
    finally:
        out.close()
        print(f"\nDone. {saved} new turbines saved to '{OUTPUT_CSV}'.")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    all_urls = build_url_list()
    scrape_turbines(all_urls)