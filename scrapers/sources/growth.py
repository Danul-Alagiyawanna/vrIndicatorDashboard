"""
Growth scrapers — G1, G2, G3, G4.

  G1  GDP Growth (YoY %)
        US          — FRED  (A191RL1Q225SBEA, quarterly annualised)
        EA/SG/CN/IN/SL — Trading Economics (quarterly YoY%)

  G2  Manufacturing PMI     — manual entry only (S&P Global PMI is paid)
  G3  Services PMI          — manual entry only

  G4  Industrial Production (YoY %)
        US          — FRED  (INDPRO, YoY%)
        EA/SG/CN/IN/SL — Trading Economics

Usage:
  python growth.py --dry-run
  python growth.py --local
  python growth.py
"""

import os
import re
import calendar
import argparse
import math
from datetime import date, timedelta, datetime
from typing import Optional

import pandas as pd
import requests
from fredapi import Fred
from scrapling.fetchers import StealthyFetcher
from dotenv import load_dotenv

load_dotenv()

SOURCE_FRED = "FRED"
SOURCE_TE   = "Trading Economics"

NON_US = ["EA", "SG", "CN", "IN", "SL"]

# ── G1 — GDP YoY% ─────────────────────────────────────────────────────────────

G1_TE_URLS = {
    "EA": "https://tradingeconomics.com/euro-area/gdp-growth-annual",
    "SG": "https://tradingeconomics.com/singapore/gdp-growth-annual",
    "CN": "https://tradingeconomics.com/china/gdp-growth-annual",
    "IN": "https://tradingeconomics.com/india/gdp-growth-annual",
    "SL": "https://tradingeconomics.com/sri-lanka/gdp-growth-annual",
}

QUARTER_MONTHS = {"Q1": (1, 3), "Q2": (4, 6), "Q3": (7, 9), "Q4": (10, 12)}

# ── G2 — Manufacturing PMI source URLs (manual entry reference) ───────────────
G2_TE_URLS = {
    "US": "https://tradingeconomics.com/united-states/manufacturing-pmi",
    "EA": "https://tradingeconomics.com/euro-area/manufacturing-pmi",
    "SG": "https://tradingeconomics.com/singapore/manufacturing-pmi",
    "CN": "https://tradingeconomics.com/china/manufacturing-pmi",
    "IN": "https://tradingeconomics.com/india/manufacturing-pmi",
    "SL": "https://tradingeconomics.com/sri-lanka/manufacturing-pmi",
}

# ── G3 — Services PMI source URLs (manual entry reference) ───────────────────
G3_TE_URLS = {
    "US": "https://tradingeconomics.com/united-states/non-manufacturing-pmi",
    "EA": "https://tradingeconomics.com/euro-area/services-pmi",
    "SG": "https://tradingeconomics.com/singapore/composite-pmi",
    "CN": "https://tradingeconomics.com/china/non-manufacturing-pmi",
    "IN": "https://tradingeconomics.com/india/services-pmi",
    "SL": "https://tradingeconomics.com/sri-lanka/services-pmi",
}

# ── G4 — Industrial Production YoY% ──────────────────────────────────────────

G4_TE_URLS = {
    "EA": {"url": "https://tradingeconomics.com/euro-area/industrial-production",  "layout": "calendar"},
    "CN": {"url": "https://tradingeconomics.com/china/industrial-production",      "layout": "calendar"},
    "IN": {"url": "https://tradingeconomics.com/india/industrial-production",      "layout": "calendar"},
    "SG": {"url": "https://tradingeconomics.com/singapore/industrial-production",  "layout": "calendar"},
    "SL": {"url": "https://tradingeconomics.com/sri-lanka/industrial-production",  "layout": "multi",
           "unit_filter": "percent", "unit_row": 1},
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


def _quarter_end_date(release_date_str: str, period_str: str) -> tuple[date, str]:
    period = period_str.strip()
    if period not in QUARTER_MONTHS:
        return date.today().replace(day=1), period
    _, end_month = QUARTER_MONTHS[period]
    try:
        release_year  = int(release_date_str[:4])
        release_month = int(release_date_str[5:7])
    except (ValueError, IndexError):
        return date.today(), period
    year = release_year if end_month <= release_month else release_year - 1
    last_day = calendar.monthrange(year, end_month)[1]
    return date(year, end_month, last_day), period


def _yoy(series: pd.Series) -> pd.Series:
    periods = 12 if (len(series) < 2 or (series.index[1] - series.index[0]).days < 60) else 4
    return series.pct_change(periods=periods) * 100


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
    """Latest value from a TE multi-metric table."""
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


# ── Fetch functions ───────────────────────────────────────────────────────────

def _fetch_g1_us(fred: Fred) -> list[tuple[date, float]]:
    start = (date.today() - timedelta(days=730)).isoformat()
    series = fred.get_series("A191RL1Q225SBEA", observation_start=start).dropna()
    return [(ts.date(), float(v)) for ts, v in series.items() if not math.isnan(float(v))]


def _fetch_g1_te(country_id: str) -> list[tuple[date, float, str]]:
    """Returns list of (ref_date, value, series_url)."""
    url = G1_TE_URLS[country_id]
    page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
    rows = page.css("table#p tr") or page.css("table tr")
    results = []
    for row in rows[1:]:
        cells = row.css("td")
        if len(cells) != 8:
            continue
        val = _parse_value(cells[4].css("::text").get("").strip())
        if val is None:
            continue
        release_date = cells[0].css("::text").get("").strip()
        period       = cells[3].css("::text").get("").strip()
        ref_date, _  = _quarter_end_date(release_date, period)
        results.append((ref_date, val, url))
    # deduplicate on date, keep last
    seen: dict[date, tuple[date, float, str]] = {}
    for item in sorted(results, key=lambda x: x[0]):
        seen[item[0]] = item
    return list(seen.values())


def _fetch_g4_us(fred: Fred) -> list[tuple[date, float]]:
    lookback = 730 + 730   # extra for YoY calc
    start = (date.today() - timedelta(days=lookback)).isoformat()
    cutoff = (date.today() - timedelta(days=730)).isoformat()
    raw = fred.get_series("INDPRO", observation_start=start).dropna()
    series = _yoy(raw).dropna().loc[cutoff:]
    return [(ts.date(), round(float(v), 4)) for ts, v in series.items() if not math.isnan(float(v))]


def _fetch_g4_te(country_id: str) -> Optional[tuple[date, float, str]]:
    cfg = G4_TE_URLS[country_id]
    url = cfg["url"]
    result = (
        _fetch_te_calendar(url) if cfg["layout"] == "calendar"
        else _fetch_te_multi(url, cfg.get("unit_filter", ""), cfg.get("unit_row", 0))
    )
    if result is None:
        return None
    value, ref_date = result
    return ref_date, value, url


# ── Main run ──────────────────────────────────────────────────────────────────

def run(dry_run: bool = False, local: bool = False) -> None:
    from db import upsert_reading, log_etl_run, set_local, get_latest_date
    if local:
        set_local(True)

    fred = Fred(api_key=os.environ["FRED_API_KEY"])

    # ── G1 US (FRED) ──────────────────────────────────────────────────────────
    try:
        latest = get_latest_date("G1", "US")
        rows = _fetch_g1_us(fred)
        new_rows = [(d, v) for d, v in rows if latest is None or d > latest]
        for reading_date, value in new_rows:
            if dry_run:
                print(f"  G1/US  {reading_date}  {value:.4f}  [A191RL1Q225SBEA]")
            else:
                upsert_reading("G1", "US", value, reading_date, SOURCE_FRED, "A191RL1Q225SBEA")
        if not dry_run:
            log_etl_run(SOURCE_FRED, "G1", "US", "success", rows_written=len(new_rows))
        print(f"[FRED] G1/US — {len(new_rows)} new rows (skipped {len(rows)-len(new_rows)}) {'(dry run)' if dry_run else 'written'}")
    except Exception as exc:
        if not dry_run:
            log_etl_run(SOURCE_FRED, "G1", "US", "failed", error_message=str(exc))
        print(f"[FRED] ERROR G1/US: {exc}")

    # ── G1 non-US (Trading Economics) ─────────────────────────────────────────
    for country_id in NON_US:
        try:
            latest = get_latest_date("G1", country_id)
            rows = _fetch_g1_te(country_id)
            if not rows:
                print(f"[TE] G1/{country_id} — no data parsed")
                if not dry_run:
                    log_etl_run(SOURCE_TE, "G1", country_id, "stale", error_message="No rows parsed")
                continue
            new_rows = [(d, v, u) for d, v, u in rows if latest is None or d > latest]
            for ref_date, value, url in new_rows:
                if dry_run:
                    print(f"  G1/{country_id}  {ref_date}  {value:.4f}  [{url}]")
                else:
                    upsert_reading("G1", country_id, value, ref_date, SOURCE_TE, url)
            if not dry_run:
                log_etl_run(SOURCE_TE, "G1", country_id, "success", rows_written=len(new_rows))
            print(f"[TE] G1/{country_id} — {len(new_rows)} new rows (skipped {len(rows)-len(new_rows)}) {'(dry run)' if dry_run else 'written'}")
        except Exception as exc:
            if not dry_run:
                log_etl_run(SOURCE_TE, "G1", country_id, "failed", error_message=str(exc))
            print(f"[TE] ERROR G1/{country_id}: {exc}")

    # ── G2 / G3 — manual entry stub ───────────────────────────────────────────
    print("[PMI] G2/G3 — manual entry required (S&P Global PMI API is paid-only)")
    print("       Enter values via /admin with source='manual' and source_series_id from below:")
    for country_id in ["US", "EA", "SG", "CN", "IN", "SL"]:
        print(f"  G2/{country_id}: {G2_TE_URLS[country_id]}")
        print(f"  G3/{country_id}: {G3_TE_URLS[country_id]}")

    # ── G4 US (FRED) ──────────────────────────────────────────────────────────
    try:
        latest = get_latest_date("G4", "US")
        rows = _fetch_g4_us(fred)
        new_rows = [(d, v) for d, v in rows if latest is None or d > latest]
        for reading_date, value in new_rows:
            if dry_run:
                print(f"  G4/US  {reading_date}  {value:.4f}  [INDPRO]")
            else:
                upsert_reading("G4", "US", value, reading_date, SOURCE_FRED, "INDPRO")
        if not dry_run:
            log_etl_run(SOURCE_FRED, "G4", "US", "success", rows_written=len(new_rows))
        print(f"[FRED] G4/US — {len(new_rows)} new rows (skipped {len(rows)-len(new_rows)}) {'(dry run)' if dry_run else 'written'}")
    except Exception as exc:
        if not dry_run:
            log_etl_run(SOURCE_FRED, "G4", "US", "failed", error_message=str(exc))
        print(f"[FRED] ERROR G4/US: {exc}")

    # ── G4 non-US (Trading Economics) ─────────────────────────────────────────
    for country_id in NON_US:
        try:
            latest = get_latest_date("G4", country_id)
            result = _fetch_g4_te(country_id)
            if result is None:
                print(f"[TE] G4/{country_id} — no data parsed")
                if not dry_run:
                    log_etl_run(SOURCE_TE, "G4", country_id, "stale", error_message="No data parsed")
                continue
            ref_date, value, url = result
            if latest is not None and ref_date <= latest:
                print(f"[TE] G4/{country_id} — already up to date (latest: {latest})")
                continue
            if dry_run:
                print(f"  G4/{country_id}  {ref_date}  {value:.4f}  [{url}]")
            else:
                upsert_reading("G4", country_id, value, ref_date, SOURCE_TE, url)
                log_etl_run(SOURCE_TE, "G4", country_id, "success", rows_written=1)
            print(f"[TE] G4/{country_id} — {value} on {ref_date} {'(dry run)' if dry_run else 'written'}")
        except Exception as exc:
            if not dry_run:
                log_etl_run(SOURCE_TE, "G4", country_id, "failed", error_message=str(exc))
            print(f"[TE] ERROR G4/{country_id}: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--local",   action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run, local=args.local)
