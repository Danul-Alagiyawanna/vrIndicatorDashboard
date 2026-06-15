"""
World Bank / Trading Economics scraper — non-US macro indicators.

  G1  EA, SG, CN, IN, SL   GDP Growth YoY % (quarterly) — Trading Economics
  L1  EA, SG, CN, IN, SL   Unemployment rate % (annual)  — World Bank

Usage:
  python worldbank_scraper.py --local     # save to ../../data/worldbank.csv
  python worldbank_scraper.py --dry-run   # print only, no write
  python worldbank_scraper.py             # write to Supabase
"""

import re
import calendar
import argparse
import csv
from datetime import date, datetime
from pathlib import Path

import requests
from scrapling.fetchers import StealthyFetcher

SOURCE_WB = "World Bank"
SOURCE_TE = "Trading Economics"

# ── Trading Economics — quarterly GDP YoY% ────────────────────────────────────

GDP_URLS = {
    "EA": "https://tradingeconomics.com/euro-area/gdp-growth-annual",
    "SG": "https://tradingeconomics.com/singapore/gdp-growth-annual",
    "CN": "https://tradingeconomics.com/china/gdp-growth-annual",
    "IN": "https://tradingeconomics.com/india/gdp-growth-annual",
    "SL": "https://tradingeconomics.com/sri-lanka/gdp-growth-annual",
}

# Quarter label -> (start_month, end_month)
QUARTER_MONTHS = {"Q1": (1, 3), "Q2": (4, 6), "Q3": (7, 9), "Q4": (10, 12)}

# ── World Bank — annual unemployment ─────────────────────────────────────────

WB_BASE = "https://api.worldbank.org/v2/country/{iso}/indicator/{series}?format=json&mrv=10&per_page=10"

WB_ISO = {
    "EA": "EUU",
    "SG": "SGP",
    "CN": "CHN",
    "IN": "IND",
    "SL": "LKA",
}

CSV_PATH = Path(__file__).parent.parent / "data" / "worldbank.csv"
COLUMNS = ["indicator_id", "country_id", "quarter", "date", "value", "source", "source_series_id", "ingested_at"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_value(text: str):
    cleaned = re.sub(r"[^\d.\-]", "", text.strip())
    try:
        return float(cleaned)
    except ValueError:
        return None


def _quarter_end_date(release_date_str: str, period_str: str):
    """
    Derive the quarter-end date from the period label (Q1/Q2/Q3/Q4)
    and the release date.

    The release date tells us the year the data was published.
    The quarter end is always the last day of the quarter's end month.

    e.g. period='Q1', release='2026-05-13' -> date(2026, 3, 31)
         period='Q4', release='2026-01-19' -> date(2025, 12, 31)  <- prior year
    """
    period = period_str.strip()
    if period not in QUARTER_MONTHS:
        return date.today().replace(day=1), period

    _, end_month = QUARTER_MONTHS[period]
    try:
        release_year = int(release_date_str[:4])
        release_month = int(release_date_str[5:7])
    except (ValueError, IndexError):
        return date.today(), period

    # If quarter end month is after the release month, the quarter belongs to prior year
    # e.g. Q4 ends in Dec, released in Jan -> prior year
    year = release_year if end_month <= release_month else release_year - 1
    last_day = calendar.monthrange(year, end_month)[1]
    return date(year, end_month, last_day), period


def _fetch_gdp_te(country_id: str) -> list[dict]:
    """Scrape quarterly GDP YoY% from Trading Economics calendar table."""
    url = GDP_URLS[country_id]
    page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
    rows = page.css("table#p tr") or page.css("table tr")
    now = datetime.utcnow().isoformat()
    results = []

    for row in rows[1:]:
        cells = row.css("td")
        if len(cells) != 8:
            continue
        actual_text = cells[4].css("::text").get("").strip()
        val = _parse_value(actual_text)
        if val is None:
            continue
        release_date = cells[0].css("::text").get("").strip()
        period = cells[3].css("::text").get("").strip()
        ref_date, quarter = _quarter_end_date(release_date, period)
        results.append({
            "indicator_id": "G1",
            "country_id": country_id,
            "quarter": quarter,
            "date": ref_date.isoformat(),
            "value": val,
            "source": SOURCE_TE,
            "source_series_id": url,
            "ingested_at": now,
        })

    # Sort by date ascending, deduplicate on date (keep last)
    seen = {}
    for r in sorted(results, key=lambda x: x["date"]):
        seen[r["date"]] = r
    return list(seen.values())


def _fetch_unemployment_wb(country_id: str) -> list[dict]:
    """Fetch annual unemployment from World Bank API."""
    iso3 = WB_ISO[country_id]
    series_id = "SL.UEM.TOTL.ZS"
    url = WB_BASE.format(iso=iso3, series=series_id)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if len(data) < 2 or not data[1]:
        return []

    now = datetime.utcnow().isoformat()
    results = []
    for entry in data[1]:
        if entry.get("value") is None:
            continue
        results.append({
            "indicator_id": "L1",
            "country_id": country_id,
            "quarter": "",
            "date": date(int(entry["date"]), 12, 31).isoformat(),
            "value": float(entry["value"]),
            "source": SOURCE_WB,
            "source_series_id": series_id,
            "ingested_at": now,
        })
    return sorted(results, key=lambda r: r["date"])


def _write_csv(rows: list[dict]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


# ── Main ──────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False, local: bool = False) -> None:
    from db import upsert_reading, log_etl_run

    all_rows = []

    # G1 — quarterly GDP from Trading Economics
    for country_id in GDP_URLS:
        try:
            rows = _fetch_gdp_te(country_id)
            if not rows:
                print(f"[TE] G1/{country_id} -- no data parsed")
                continue
            latest = rows[-1]
            if dry_run:
                print(f"  G1/{country_id}  {latest['quarter']}  {latest['date']}  {latest['value']}%  ({len(rows)} releases)")
            else:
                for r in rows:
                    if local:
                        all_rows.append(r)
                    else:
                        upsert_reading("G1", country_id, r["value"],
                                       date.fromisoformat(r["date"]), SOURCE_TE, r["source_series_id"])
                mode = f"-> {CSV_PATH.name}" if local else "written to Supabase"
                print(f"[TE] G1/{country_id} -- {len(rows)} quarterly rows {mode}")
        except Exception as exc:
            print(f"[TE] ERROR G1/{country_id}: {exc}")

    # L1 — annual unemployment from World Bank
    for country_id in WB_ISO:
        try:
            rows = _fetch_unemployment_wb(country_id)
            if not rows:
                print(f"[WB] L1/{country_id} -- no data")
                continue
            latest = rows[-1]
            if dry_run:
                print(f"  L1/{country_id}  {latest['date']}  {latest['value']}%  ({len(rows)} years)")
            else:
                for r in rows:
                    if local:
                        all_rows.append(r)
                    else:
                        upsert_reading("L1", country_id, r["value"],
                                       date.fromisoformat(r["date"]), SOURCE_WB, r["source_series_id"])
                mode = f"-> {CSV_PATH.name}" if local else "written to Supabase"
                print(f"[WB] L1/{country_id} -- {len(rows)} annual rows {mode}")
        except Exception as exc:
            print(f"[WB] ERROR L1/{country_id}: {exc}")

    if local and all_rows:
        _write_csv(all_rows)
        print(f"\nSaved {len(all_rows)} rows -> {CSV_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print only, no write")
    parser.add_argument("--local", action="store_true", help="Save to local CSV instead of Supabase")
    args = parser.parse_args()
    run(dry_run=args.dry_run, local=args.local)
