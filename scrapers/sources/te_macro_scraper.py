"""
Trading Economics macro scraper — non-US indicators not covered by FRED or World Bank.

Indicators covered:
  G4  EA, SG, CN, IN, SL   Industrial Production YoY %
  I1  EA, SG, CN, IN        Headline CPI YoY %
  I2  EA, SG, CN, SL        Core CPI YoY %
  I3  EA, SG, CN, IN        Food Inflation YoY %
  M1  EA, CN, IN             Policy Rate %  (SG: MAS band-based, no single rate)
  M2  EA, CN, IN, SG        10Y Bond Yield %
  L2  EA                    Wage Growth YoY % (quarterly)
  E1  EA, CN, IN, SG, SL   Trade Balance
  E2  EA, CN, IN, SG        FX Reserves USD bn

Usage:
  python te_macro_scraper.py --local     # save to ../../data/te_macro.csv
  python te_macro_scraper.py --dry-run   # print only, no write
  python te_macro_scraper.py             # write to Supabase
"""

import re
import argparse
import csv
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from scrapling.fetchers import StealthyFetcher

SOURCE = "Trading Economics"
CSV_PATH = Path(__file__).parent.parent / "data" / "te_macro.csv"
COLUMNS = ["indicator_id", "country_id", "date", "value", "source", "source_series_id", "ingested_at"]

# ── Page config ───────────────────────────────────────────────────────────────
# layout:
#   "calendar" — 8-cell rows: [date, time, event, period, actual, prev, cons, te]
#                picks last row with non-empty cells[4]
#   "multi"    — 5-cell rows: [blank, value, prev, unit, ref_date]
#                picks unit_row-th row matching unit_filter
#
# scale: multiply scraped value by this (e.g. 1e-3 for USD Million -> USD bn)
# unit_filter: string that must appear in cells[3] for multi layout
# unit_row: 0-based index among matching unit rows

INDICATORS = {
    # G4 — Industrial Production YoY%
    "G4": {
        "EA": {"url": "https://tradingeconomics.com/euro-area/industrial-production",  "layout": "calendar", "scale": 1},
        "CN": {"url": "https://tradingeconomics.com/china/industrial-production",       "layout": "calendar", "scale": 1},
        "IN": {"url": "https://tradingeconomics.com/india/industrial-production",       "layout": "calendar", "scale": 1},
        "SG": {"url": "https://tradingeconomics.com/singapore/industrial-production",   "layout": "calendar", "scale": 1},
        "SL": {"url": "https://tradingeconomics.com/sri-lanka/industrial-production",   "layout": "multi",    "unit_filter": "percent", "unit_row": 1, "scale": 1},
    },
    # I1 — Headline CPI YoY%
    "I1": {
        "EA": {"url": "https://tradingeconomics.com/euro-area/inflation-cpi",  "layout": "calendar", "scale": 1},
        "CN": {"url": "https://tradingeconomics.com/china/inflation-cpi",      "layout": "calendar", "scale": 1},
        "IN": {"url": "https://tradingeconomics.com/india/inflation-cpi",      "layout": "calendar", "scale": 1},
        "SG": {"url": "https://tradingeconomics.com/singapore/inflation-cpi",  "layout": "calendar", "scale": 1},
    },
    # I2 — Core CPI YoY%
    "I2": {
        "EA": {"url": "https://tradingeconomics.com/euro-area/core-inflation-rate",  "layout": "calendar", "scale": 1},
        "CN": {"url": "https://tradingeconomics.com/china/core-inflation-rate",      "layout": "multi", "unit_filter": "percent", "unit_row": 0, "scale": 1},
        "SG": {"url": "https://tradingeconomics.com/singapore/core-inflation-rate",  "layout": "calendar", "scale": 1},
        "SL": {"url": "https://tradingeconomics.com/sri-lanka/core-inflation-rate",  "layout": "multi", "unit_filter": "percent", "unit_row": 0, "scale": 1},
    },
    # I3 — Food Inflation YoY%
    "I3": {
        "EA": {"url": "https://tradingeconomics.com/euro-area/food-inflation",  "layout": "multi", "unit_filter": "percent", "unit_row": 1, "scale": 1},
        "CN": {"url": "https://tradingeconomics.com/china/food-inflation",      "layout": "multi", "unit_filter": "percent", "unit_row": 2, "scale": 1},
        "IN": {"url": "https://tradingeconomics.com/india/food-inflation",      "layout": "multi", "unit_filter": "percent", "unit_row": 0, "scale": 1},
        "SG": {"url": "https://tradingeconomics.com/singapore/food-inflation",  "layout": "multi", "unit_filter": "percent", "unit_row": 1, "scale": 1},
    },
    # M1 — Policy Rate %
    "M1": {
        "EA": {"url": "https://tradingeconomics.com/euro-area/interest-rate",  "layout": "calendar", "scale": 1},
        "CN": {"url": "https://tradingeconomics.com/china/interest-rate",      "layout": "calendar", "scale": 1},
        "IN": {"url": "https://tradingeconomics.com/india/interest-rate",      "layout": "calendar", "scale": 1},
        # SG: MAS uses exchange rate policy, no traditional rate — skipped
    },
    # M2 — 10Y Government Bond Yield %
    # These pages show a live bond market table; the 9-cell summary row has the value
    "M2": {
        "EA": {"url": "https://tradingeconomics.com/euro-area/government-bond-yield",  "layout": "summary9", "scale": 1},
        "CN": {"url": "https://tradingeconomics.com/china/government-bond-yield",      "layout": "summary9", "scale": 1},
        "IN": {"url": "https://tradingeconomics.com/india/government-bond-yield",      "layout": "summary9", "scale": 1},
        "SG": {"url": "https://tradingeconomics.com/singapore/government-bond-yield",  "layout": "summary9", "scale": 1},
        "SL": {"url": "https://www.investing.com/rates-bonds/sri-lanka-10-year-bond-yield", "layout": "investing", "scale": 1},
    },
    # _2Y — intermediate: 2Y yields for M3 spread calculation (not stored directly)
    "_2Y": {
        "EA": {"url": "https://tradingeconomics.com/euro-area/2-year-note-yield",          "layout": "summary9", "scale": 1},
        "CN": {"url": "https://tradingeconomics.com/china/2-year-bond-yield",              "layout": "summary9", "scale": 1},
        "IN": {"url": "https://tradingeconomics.com/india/2-year-bond-yield",              "layout": "summary9", "scale": 1},
        "SG": {"url": "https://tradingeconomics.com/singapore/2-year-bond-yield",          "layout": "summary9", "scale": 1},
        "SL": {"url": "https://www.investing.com/rates-bonds/sri-lanka-2-year-bond-yield", "layout": "investing", "scale": 1},
    },
    # L2 — Wage Growth YoY % for EA; wage level (local currency) for SG/CN/IN/SL
    # Note: SG/CN/IN/SL pages have no YoY% row — storing wage level as best available proxy
    "L2": {
        "EA": {"url": "https://tradingeconomics.com/euro-area/wage-growth",   "layout": "calendar", "scale": 1},
        "SG": {"url": "https://tradingeconomics.com/singapore/wages",         "layout": "multi", "unit_filter": "SGD/Month", "unit_row": 0, "scale": 1},
        "CN": {"url": "https://tradingeconomics.com/china/wages",             "layout": "multi", "unit_filter": "CNY/Year",  "unit_row": 0, "scale": 1},
        "IN": {"url": "https://tradingeconomics.com/india/wages",             "layout": "summary9_any", "scale": 1},
        "SL": {"url": "https://tradingeconomics.com/sri-lanka/wages",         "layout": "multi", "unit_filter": "LKR/Month", "unit_row": 0, "scale": 1},
    },
    # E1 — Trade Balance (scale 1e-3 converts M -> bn; _parse_value handles B suffix -> M first)
    "E1": {
        "EA": {"url": "https://tradingeconomics.com/euro-area/balance-of-trade",  "layout": "calendar", "scale": 1e-3},  # €B -> M -> bn
        "CN": {"url": "https://tradingeconomics.com/china/balance-of-trade",      "layout": "multi", "unit_filter": "USD Billion", "unit_row": 0, "scale": 1},
        "IN": {"url": "https://tradingeconomics.com/india/balance-of-trade",      "layout": "multi", "unit_filter": "USD Billion", "unit_row": 0, "scale": 1},
        "SG": {"url": "https://tradingeconomics.com/singapore/balance-of-trade",  "layout": "calendar", "scale": 1e-3},  # SGD B -> M -> bn
        "SL": {"url": "https://tradingeconomics.com/sri-lanka/balance-of-trade",  "layout": "multi", "unit_filter": "USD Million", "unit_row": 0, "scale": 1e-3},
    },
    # E2 — FX Reserves USD bn
    "E2": {
        "EA": {"url": "https://tradingeconomics.com/euro-area/foreign-exchange-reserves",  "layout": "multi", "unit_filter": "USD Billion", "unit_row": 0, "scale": 1},
        "CN": {"url": "https://tradingeconomics.com/china/foreign-exchange-reserves",      "layout": "multi", "unit_filter": "USD Million",  "unit_row": 0, "scale": 1e-3},
        "IN": {"url": "https://tradingeconomics.com/india/foreign-exchange-reserves",      "layout": "calendar", "scale": 1e-3},  # USD M -> bn
        "SG": {"url": "https://tradingeconomics.com/singapore/foreign-exchange-reserves",  "layout": "calendar", "scale": 1e-3},  # SGD M -> bn
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_value(text: str) -> Optional[float]:
    t = text.strip()
    # detect B/T suffix before stripping non-numeric chars
    upper = t.upper()
    has_billions = upper.endswith("B") or "B " in upper
    has_trillions = upper.endswith("T") or "T " in upper
    cleaned = re.sub(r"[^\d.\-]", "", t)
    try:
        val = float(cleaned)
        if has_trillions:
            val *= 1_000_000
        elif has_billions:
            val *= 1_000
        return val
    except ValueError:
        return None


def _parse_date(text: str) -> date:
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%b %Y", "%Y-%m", "%m/%Y", "%Y"):
        try:
            dt = datetime.strptime(text, fmt)
            return date(dt.year, dt.month, 1)
        except ValueError:
            continue
    return date.today().replace(day=1)


def _fetch_page(url: str, cfg: dict) -> Optional[tuple[float, date]]:
    page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
    rows = page.css("table#p tr") or page.css("table tr")
    layout = cfg["layout"]
    scale = cfg.get("scale", 1)

    if layout == "calendar":
        # 8-cell rows: [date, time, event, period, actual, prev, cons, te]
        best = None
        for row in rows[1:]:
            cells = row.css("td")
            if len(cells) != 8:
                continue
            actual_text = cells[4].css("::text").get("").strip()
            val = _parse_value(actual_text)
            if val is None:
                continue
            ref_date = _parse_date(cells[0].css("::text").get("").strip())
            best = (round(val * scale, 4), ref_date)
        return best

    elif layout == "multi":
        # 5-cell rows: [blank, value, prev, unit, ref_date]
        unit_filter = cfg.get("unit_filter", "")
        unit_row = cfg.get("unit_row", 0)
        match_count = 0
        for row in rows:
            cells = row.css("td")
            if len(cells) < 4:
                continue
            texts = [c.css("::text").get("").strip() for c in cells]
            unit_col = texts[3] if len(texts) > 3 else ""
            if unit_filter and unit_filter not in unit_col:
                continue
            if match_count < unit_row:
                match_count += 1
                continue
            val = _parse_value(texts[1])
            if val is None:
                continue
            date_text = texts[4] if len(texts) > 4 else ""
            ref_date = _parse_date(date_text)
            return round(val * scale, 4), ref_date

    elif layout in ("summary9", "summary9_any"):
        # 9-cell summary row: [blank, value, prev, high, low, range, unit, freq, blank]
        # summary9     — only picks rows where unit contains "percent"
        # summary9_any — picks first valid 9-cell row regardless of unit
        for row in rows:
            cells = row.css("td")
            if len(cells) != 9:
                continue
            texts = [c.css("::text").get("").strip() for c in cells]
            if layout == "summary9" and "percent" not in texts[6].lower():
                continue
            val = _parse_value(texts[1])
            if val is None:
                continue
            return round(val * scale, 4), date.today().replace(day=1)

    elif layout == "investing":
        # investing.com bond page — price shown in [data-test="instrument-price-last"]
        el = page.css('[data-test="instrument-price-last"]')
        if el:
            val = _parse_value(el[0].css("::text").get("").strip())
            if val is not None:
                return round(val * scale, 4), date.today().replace(day=1)
        # fallback: first row of historical data table (cols: date, price, open, high, low, chg%)
        for row in rows[1:]:
            cells = row.css("td")
            if len(cells) < 2:
                continue
            val = _parse_value(cells[1].css("::text").get("").strip())
            if val is None:
                continue
            date_text = cells[0].css("::text").get("").strip()
            ref_date = _parse_date(date_text)
            return round(val * scale, 4), ref_date

    return None


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
    # Store 10Y and 2Y values keyed by country for M3 spread calculation
    yield_10y: dict[str, tuple[float, date]] = {}
    yield_2y:  dict[str, tuple[float, date]] = {}

    for indicator_id, countries in INDICATORS.items():
        for country_id, cfg in countries.items():
            url = cfg["url"]
            try:
                result = _fetch_page(url, cfg)
                if result is None:
                    print(f"[TE] {indicator_id}/{country_id} -- no data parsed")
                    if not dry_run and not local:
                        log_etl_run(SOURCE, indicator_id, country_id, "stale",
                                    error_message="Could not parse page")
                    continue

                value, ref_date = result

                # Stash yields for M3 calculation; skip writing _2Y rows directly
                if indicator_id == "M2":
                    yield_10y[country_id] = (value, ref_date)
                elif indicator_id == "_2Y":
                    yield_2y[country_id] = (value, ref_date)
                    print(f"[TE] 2Y/{country_id} -- {value} on {ref_date} (intermediate)")
                    continue

                now = datetime.utcnow().isoformat()

                if dry_run:
                    print(f"  {indicator_id}/{country_id}  {ref_date}  {value}  [{url}]")
                elif local:
                    all_rows.append({
                        "indicator_id": indicator_id,
                        "country_id": country_id,
                        "date": ref_date.isoformat(),
                        "value": value,
                        "source": SOURCE,
                        "source_series_id": url,
                        "ingested_at": now,
                    })
                else:
                    upsert_reading(
                        indicator_id=indicator_id,
                        country_id=country_id,
                        value=value,
                        reading_date=ref_date,
                        source=SOURCE,
                        source_series_id=url,
                    )
                    log_etl_run(SOURCE, indicator_id, country_id, "success", rows_written=1)

                mode = "(dry run)" if dry_run else f"-> {CSV_PATH.name}" if local else "written to Supabase"
                print(f"[TE] {indicator_id}/{country_id} -- {value} on {ref_date} {mode}")

            except Exception as exc:
                if not dry_run and not local:
                    log_etl_run(SOURCE, indicator_id, country_id, "failed", error_message=str(exc))
                print(f"[TE] ERROR {indicator_id}/{country_id}: {exc}")

    # M3 = 10Y - 2Y spread (in bps)
    now = datetime.utcnow().isoformat()
    all_countries = set(yield_10y) | set(yield_2y)
    for country_id in sorted(all_countries):
        if country_id not in yield_10y or country_id not in yield_2y:
            print(f"[TE] M3/{country_id} -- skipped (missing 10Y or 2Y)")
            continue
        y10, d10 = yield_10y[country_id]
        y2,  _   = yield_2y[country_id]
        spread = round((y10 - y2) * 100, 2)  # convert % to bps
        ref_date = d10

        if dry_run:
            print(f"  M3/{country_id}  {ref_date}  {spread} bps  (10Y={y10} - 2Y={y2})")
        elif local:
            all_rows.append({
                "indicator_id": "M3",
                "country_id": country_id,
                "date": ref_date.isoformat(),
                "value": spread,
                "source": SOURCE,
                "source_series_id": "10Y-2Y",
                "ingested_at": now,
            })
        else:
            upsert_reading("M3", country_id, spread, ref_date, SOURCE, "10Y-2Y")
            log_etl_run(SOURCE, "M3", country_id, "success", rows_written=1)

        mode = "(dry run)" if dry_run else f"-> {CSV_PATH.name}" if local else "written to Supabase"
        print(f"[TE] M3/{country_id} -- {spread} bps on {ref_date} {mode}")

    if local and all_rows:
        _write_csv(all_rows)
        print(f"\nSaved {len(all_rows)} rows -> {CSV_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print only, no write")
    parser.add_argument("--local", action="store_true", help="Save to local CSV instead of Supabase")
    args = parser.parse_args()
    run(dry_run=args.dry_run, local=args.local)
