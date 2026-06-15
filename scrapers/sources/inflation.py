"""
Inflation scrapers — I1, I2, I3.

  I1  Headline CPI (YoY %)
        US          — FRED  (CPIAUCSL, YoY%)
        EA/CN/IN/SG — Trading Economics
        SL          — CBSL via Trading Economics

  I2  Core CPI (YoY %)
        US             — FRED  (CPILFESL, YoY%)
        EA/CN/IN/SG/SL — Trading Economics

  I3  Food Inflation (YoY %)
        US          — FRED  (CPIUFDSL, YoY%)
        EA/CN/IN/SG — Trading Economics
        SL          — CBSL via Trading Economics

Usage:
  python inflation.py --dry-run
  python inflation.py --local
  python inflation.py
"""

import os
import re
import argparse
import math
from datetime import date, timedelta, datetime
from typing import Optional

import pandas as pd
from fredapi import Fred
from scrapling.fetchers import StealthyFetcher
from dotenv import load_dotenv

load_dotenv()

SOURCE_FRED = "FRED"
SOURCE_TE   = "Trading Economics"
SOURCE_CBSL = "CBSL"

# ── Trading Economics page config ─────────────────────────────────────────────
# layout: "calendar" | "multi"

TE_INDICATORS: dict[str, dict[str, dict]] = {
    "I1": {
        "EA": {"url": "https://tradingeconomics.com/euro-area/inflation-cpi",  "layout": "calendar"},
        "CN": {"url": "https://tradingeconomics.com/china/inflation-cpi",      "layout": "calendar"},
        "IN": {"url": "https://tradingeconomics.com/india/inflation-cpi",      "layout": "calendar"},
        "SG": {"url": "https://tradingeconomics.com/singapore/inflation-cpi",  "layout": "calendar"},
        "SL": {"url": "https://tradingeconomics.com/sri-lanka/inflation-cpi",  "layout": "calendar"},
    },
    "I2": {
        "EA": {"url": "https://tradingeconomics.com/euro-area/core-inflation-rate",  "layout": "calendar"},
        "CN": {"url": "https://tradingeconomics.com/china/core-inflation-rate",      "layout": "multi", "unit_filter": "percent", "unit_row": 0},
        "IN": {"url": "https://tradingeconomics.com/india/core-inflation-rate",      "layout": "multi", "unit_filter": "percent", "unit_row": 0},
        "SG": {"url": "https://tradingeconomics.com/singapore/core-inflation-rate",  "layout": "calendar"},
        "SL": {"url": "https://tradingeconomics.com/sri-lanka/core-inflation-rate",  "layout": "multi", "unit_filter": "percent", "unit_row": 0},
    },
    "I3": {
        "EA": {"url": "https://tradingeconomics.com/euro-area/food-inflation",  "layout": "multi", "unit_filter": "percent", "unit_row": 1},
        "CN": {"url": "https://tradingeconomics.com/china/food-inflation",      "layout": "multi", "unit_filter": "percent", "unit_row": 2},
        "IN": {"url": "https://tradingeconomics.com/india/food-inflation",      "layout": "multi", "unit_filter": "percent", "unit_row": 0},
        "SG": {"url": "https://tradingeconomics.com/singapore/food-inflation",  "layout": "multi", "unit_filter": "percent", "unit_row": 1},
        "SL": {"url": "https://tradingeconomics.com/sri-lanka/food-inflation",  "layout": "multi", "unit_filter": "percent", "unit_row": 0},
    },
}

# FRED series for US
FRED_SERIES = {
    "I1": ("CPIAUCSL",  "yoy"),
    "I2": ("CPILFESL",  "yoy"),
    "I3": ("CPIFABSL",  "yoy"),  # Food and Beverages (total food, incl. away from home)
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_value(text: str) -> Optional[float]:
    cleaned = re.sub(r"[^\d.\-]", "", text.strip())
    try:
        return float(cleaned)
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


def _yoy(series: pd.Series) -> pd.Series:
    periods = 12 if (len(series) < 2 or (series.index[1] - series.index[0]).days < 60) else 4
    return series.pct_change(periods=periods) * 100


def _fetch_fred(fred: Fred, series_id: str, transform: str) -> list[tuple[date, float]]:
    lookback = 730 + (730 if transform == "yoy" else 0)
    start  = (date.today() - timedelta(days=lookback)).isoformat()
    cutoff = (date.today() - timedelta(days=730)).isoformat()
    raw = fred.get_series(series_id, observation_start=start).dropna()
    series = _yoy(raw).dropna().loc[cutoff:] if transform == "yoy" else raw
    return [(ts.date(), round(float(v), 4)) for ts, v in series.items() if not math.isnan(float(v))]


def _fetch_te_calendar(url: str) -> Optional[tuple[float, date]]:
    """8-cell TE calendar table. col 4 = value, col 0 = release date."""
    page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
    rows = page.css("table#p tr") or page.css("table tr")
    best = None
    for row in rows[1:]:
        cells = row.css("td")
        if len(cells) != 8:
            continue
        val = _parse_value(cells[4].css("::text").get("").strip())
        if val is None:
            continue
        ref_date = _parse_date(cells[0].css("::text").get("").strip())
        best = (val, ref_date)
    return best


def _fetch_te_multi(url: str, unit_filter: str, unit_row: int = 0) -> Optional[tuple[float, date]]:
    page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
    rows = page.css("table#p tr") or page.css("table tr")
    match_count = 0
    for row in rows:
        cells = row.css("td")
        if len(cells) < 4:
            continue
        texts = [c.css("::text").get("").strip() for c in cells]
        if unit_filter not in (texts[3] if len(texts) > 3 else ""):
            continue
        if match_count < unit_row:
            match_count += 1
            continue
        val = _parse_value(texts[1])
        if val is None:
            continue
        ref_date = _parse_date(texts[4] if len(texts) > 4 else "")
        return val, ref_date
    return None


def _fetch_te(indicator_id: str, country_id: str) -> Optional[tuple[float, date]]:
    cfg = TE_INDICATORS[indicator_id][country_id]
    url = cfg["url"]
    if cfg["layout"] == "calendar":
        return _fetch_te_calendar(url)
    return _fetch_te_multi(url, cfg.get("unit_filter", ""), cfg.get("unit_row", 0))


# ── Main run ──────────────────────────────────────────────────────────────────

def run(dry_run: bool = False, local: bool = False, force: bool = False) -> None:
    from db import upsert_reading, log_etl_run, set_local, get_latest_date
    if local:
        set_local(True)

    fred = Fred(api_key=os.environ["FRED_API_KEY"])

    for indicator_id, (series_id, transform) in FRED_SERIES.items():
        try:
            latest = None if force else get_latest_date(indicator_id, "US")
            rows = _fetch_fred(fred, series_id, transform)
            new_rows = [(d, v) for d, v in rows if latest is None or d > latest]
            for reading_date, value in new_rows:
                if dry_run:
                    print(f"  {indicator_id}/US  {reading_date}  {value:.4f}  [{series_id}]")
                else:
                    upsert_reading(indicator_id, "US", value, reading_date, SOURCE_FRED, series_id)
            if not dry_run:
                log_etl_run(SOURCE_FRED, indicator_id, "US", "success", rows_written=len(new_rows))
            skipped = len(rows) - len(new_rows)
            print(f"[FRED] {indicator_id}/US — {len(new_rows)} written, {skipped} already in DB {'(dry run)' if dry_run else ''}")
        except Exception as exc:
            if not dry_run:
                log_etl_run(SOURCE_FRED, indicator_id, "US", "failed", error_message=str(exc))
            print(f"[FRED] ERROR {indicator_id}/US: {exc}")

    for indicator_id, countries in TE_INDICATORS.items():
        for country_id, cfg in countries.items():
            source = SOURCE_CBSL if country_id == "SL" else SOURCE_TE
            try:
                latest = None if force else get_latest_date(indicator_id, country_id)
                result = _fetch_te(indicator_id, country_id)
                if result is None:
                    print(f"[TE] {indicator_id}/{country_id} — no data parsed")
                    if not dry_run:
                        log_etl_run(source, indicator_id, country_id, "stale",
                                    error_message="No data parsed")
                    continue
                value, ref_date = result
                if latest is not None and ref_date <= latest:
                    print(f"[TE] {indicator_id}/{country_id} — already up to date (latest: {latest})")
                    continue
                if dry_run:
                    print(f"  {indicator_id}/{country_id}  {ref_date}  {value:.4f}  [{cfg['url']}]")
                else:
                    upsert_reading(indicator_id, country_id, value, ref_date, source, cfg["url"])
                    log_etl_run(source, indicator_id, country_id, "success", rows_written=1)
                print(f"[TE] {indicator_id}/{country_id} — {value} on {ref_date} {'(dry run)' if dry_run else 'written'}")
            except Exception as exc:
                if not dry_run:
                    log_etl_run(source, indicator_id, country_id, "failed", error_message=str(exc))
                print(f"[TE] ERROR {indicator_id}/{country_id}: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--local",   action="store_true")
    parser.add_argument("--force",   action="store_true", help="Re-scrape all rows, ignoring what's already in the DB")
    args = parser.parse_args()
    run(dry_run=args.dry_run, local=args.local, force=args.force)
