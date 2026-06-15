"""
CBSL scraper — Sri Lanka-specific indicators via Trading Economics.

Indicators:
  F1  SL  ASPI equity index level
  I1  SL  Headline CPI YoY %
  I3  SL  Food CPI YoY %
  M1  SL  Policy rate %
  E2  SL  Gross official reserves USD bn
  E3  SL  Remittances USD mn

Usage:
  python cbsl_scraper.py --local     # save to ../../data/cbsl.csv
  python cbsl_scraper.py --dry-run   # print only, no write
  python cbsl_scraper.py             # write to Supabase
"""

import re
import argparse
import csv
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from scrapling.fetchers import StealthyFetcher

SOURCE = "CBSL"
COUNTRY_ID = "SL"

TE_URLS = {
    "F1": "https://tradingeconomics.com/sri-lanka/stock-market",
    "I1": "https://tradingeconomics.com/sri-lanka/inflation-cpi",
    "I3": "https://tradingeconomics.com/sri-lanka/food-inflation",
    "M1": "https://tradingeconomics.com/sri-lanka/interest-rate",
    "E2": "https://tradingeconomics.com/sri-lanka/foreign-exchange-reserves",
    "E3": "https://tradingeconomics.com/sri-lanka/remittances",
}

# Page layout types:
#   "calendar" — event/release table: [date, time, event, period, actual, prev, ...]
#                value = cells[4], date parsed from cells[0]
#                Only rows with exactly 8 cells are calendar rows (stats table rows have 5/9)
#   "simple"   — single-metric history: [date, value, prev, ...]
#                value = cells[1], date = cells[0]
#   "multi"    — multiple metrics per page: scan rows for matching unit keyword
#                unit_row: which matching row to pick (0=first, 1=second, ...)
PAGE_CONFIG = {
    "F1": {"layout": "simple",   "unit_filter": None,          "unit_row": 0, "scale": 1},
    "I1": {"layout": "calendar", "unit_filter": None,          "unit_row": 0, "scale": 1},
    "I3": {"layout": "multi",    "unit_filter": "percent",     "unit_row": 0, "scale": 1},     # row[0] = food CPI YoY%
    "M1": {"layout": "calendar", "unit_filter": None,          "unit_row": 0, "scale": 1},
    "E2": {"layout": "multi",    "unit_filter": "USD Million", "unit_row": 0, "scale": 1e-3},  # USD mn -> USD bn
    "E3": {"layout": "multi",    "unit_filter": "USD Million", "unit_row": 6, "scale": 1},     # row[6] = Remittances (767.90)
}

CSV_PATH = Path(__file__).parent.parent / "data" / "cbsl.csv"
COLUMNS = ["indicator_id", "country_id", "date", "value", "source", "source_series_id", "ingested_at"]


def _parse_value(text: str) -> Optional[float]:
    cleaned = re.sub(r"[^\d.\-]", "", text.strip())
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_date(text: str) -> date:
    for fmt in ("%Y-%m-%d", "%b %Y", "%Y-%m", "%m/%Y", "%Y"):
        try:
            dt = datetime.strptime(text.strip(), fmt)
            return date(dt.year, dt.month, 1)
        except ValueError:
            continue
    return date.today().replace(day=1)


def _parse_month_name(text: str) -> Optional[date]:
    """Parse month abbreviations like 'May', 'Apr' using current year."""
    text = text.strip()
    for fmt in ("%b", "%B"):
        try:
            dt = datetime.strptime(text, fmt)
            return date(date.today().year, dt.month, 1)
        except ValueError:
            continue
    return None


def _fetch_te(indicator_id: str) -> Optional[tuple[float, date]]:
    url = TE_URLS[indicator_id]
    cfg = PAGE_CONFIG[indicator_id]
    page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
    rows = page.css("table#p tr") or page.css("table tr")

    if cfg["layout"] == "simple":
        # single-metric history table: date | value | prev | ...
        for row in rows[1:]:
            cells = row.css("td")
            if len(cells) < 2:
                continue
            val = _parse_value(cells[1].css("::text").get() or "")
            if val is None:
                continue
            ref_date = _parse_date(cells[0].css("::text").get() or "")
            return round(val * cfg["scale"], 4), ref_date

    elif cfg["layout"] == "calendar":
        # event/release table: date | time | event | period | actual | prev | ...
        # Only 8-cell rows are calendar rows — stats/summary rows have 5 or 9 cells
        best = None
        for row in rows[1:]:
            cells = row.css("td")
            if len(cells) != 8:
                continue
            actual_text = cells[4].css("::text").get() or ""
            val = _parse_value(actual_text)
            if val is None:
                continue
            date_text = cells[0].css("::text").get() or ""
            ref_date = _parse_date(date_text)
            best = (round(val * cfg["scale"], 4), ref_date)
        return best

    elif cfg["layout"] == "multi":
        # multi-metric table: row structure: [blank, value, prev, unit, date]
        # unit_row selects which matching row to use (0=first match, 1=second, ...)
        unit_filter = cfg["unit_filter"]
        match_count = 0
        for row in rows:
            cells = row.css("td")
            if len(cells) < 4:
                continue
            texts = [c.css("::text").get("").strip() for c in cells]
            unit_col = texts[3] if len(texts) > 3 else ""
            if unit_filter and unit_filter not in unit_col:
                continue
            if match_count < cfg["unit_row"]:
                match_count += 1
                continue
            val = _parse_value(texts[1])
            if val is None:
                continue
            date_text = texts[4] if len(texts) > 4 else ""
            ref_date = _parse_date(date_text)
            return round(val * cfg["scale"], 4), ref_date

    return None


def _write_csv(rows: list[dict]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_exists = CSV_PATH.exists()
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def run(dry_run: bool = False, local: bool = False) -> None:
    from db import upsert_reading, log_etl_run

    all_rows = []

    for indicator_id, url in TE_URLS.items():
        try:
            result = _fetch_te(indicator_id)
            if result is None:
                print(f"[CBSL] {indicator_id}/SL -- no data parsed")
                if not dry_run and not local:
                    log_etl_run(SOURCE, indicator_id, COUNTRY_ID, "stale",
                                error_message="Could not parse Trading Economics page")
                continue

            value, ref_date = result
            now = datetime.utcnow().isoformat()

            if dry_run:
                print(f"  {indicator_id}/SL  {ref_date}  {value}  [{url}]")
            elif local:
                all_rows.append({
                    "indicator_id": indicator_id,
                    "country_id": COUNTRY_ID,
                    "date": ref_date.isoformat(),
                    "value": value,
                    "source": SOURCE,
                    "source_series_id": url,
                    "ingested_at": now,
                })
            else:
                upsert_reading(
                    indicator_id=indicator_id,
                    country_id=COUNTRY_ID,
                    value=value,
                    reading_date=ref_date,
                    source=SOURCE,
                    source_series_id=url,
                    notes="Sourced via Trading Economics / CBSL",
                )
                log_etl_run(SOURCE, indicator_id, COUNTRY_ID, "success", rows_written=1)

            mode = "(dry run)" if dry_run else f"-> {CSV_PATH.name}" if local else "written to Supabase"
            print(f"[CBSL] {indicator_id}/SL -- {value} on {ref_date} {mode}")

        except Exception as exc:
            if not dry_run and not local:
                log_etl_run(SOURCE, indicator_id, COUNTRY_ID, "failed", error_message=str(exc))
            print(f"[CBSL] ERROR {indicator_id}/SL: {exc}")

    if local and all_rows:
        _write_csv(all_rows)
        print(f"\nSaved {len(all_rows)} rows -> {CSV_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print only, no write")
    parser.add_argument("--local", action="store_true", help="Save to local CSV instead of Supabase")
    args = parser.parse_args()
    run(dry_run=args.dry_run, local=args.local)
