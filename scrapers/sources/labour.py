"""
Labour market scrapers — L1, L2.

  L1  Unemployment Rate (%)
        US          — FRED  (UNRATE)
        EA/SG/CN/IN/SL — Trading Economics (calendar layout)

  L2  Wage Growth (YoY %)
        US          — FRED  (CES0500000003, YoY%)
        EA          — Trading Economics (YoY%)
        CN          — Trading Economics (YoY% derived from annual wage level)
        SG          — Trading Economics (MoM% derived from monthly wage level)
        IN/SL       — no reliable source, skipped

Usage:
  python labour.py --dry-run
  python labour.py --local
  python labour.py
  python labour.py --force
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

NON_US = ["EA", "SG", "CN", "IN", "SL"]

# L1 TE pages — unemployment rate
L1_TE: dict[str, str] = {
    "EA": "https://tradingeconomics.com/euro-area/unemployment-rate",
    "SG": "https://tradingeconomics.com/singapore/unemployment-rate",
    "CN": "https://tradingeconomics.com/china/unemployment-rate",
    "SL": "https://tradingeconomics.com/sri-lanka/unemployment-rate",
    "IN": "https://tradingeconomics.com/india/unemployment-rate",
}

# L2 TE pages — EA has true YoY%, others are wage-level proxies
L2_TE: dict[str, dict] = {
    # EA: true YoY% series from TE calendar
    "EA": {"url": "https://tradingeconomics.com/euro-area/wage-growth",   "layout": "calendar",  "pct_label": "YoY"},
    # CN: annual wage — Last vs Previous is effectively YoY
    "CN": {"url": "https://tradingeconomics.com/china/wages",             "layout": "multi_pct", "unit_filter": "CNY/Year",  "unit_row": 0, "pct_label": "YoY"},
    # SG: monthly wage — Last vs Previous is MoM
    "SG": {"url": "https://tradingeconomics.com/singapore/wages",         "layout": "multi_pct", "unit_filter": "SGD/Month", "unit_row": 0, "pct_label": "MoM"},
    # IN wages: INR/Day data on TE is unreliable — skipped
    # SL wages: no reliable source available — skipped
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


# ── Fetch functions ───────────────────────────────────────────────────────────

def _fetch_fred_level(fred: Fred, series_id: str, lookback_days: int = 730) -> list[tuple[date, float]]:
    start = (date.today() - timedelta(days=lookback_days)).isoformat()
    series = fred.get_series(series_id, observation_start=start).dropna()
    return [(ts.date(), round(float(v), 4)) for ts, v in series.items() if not math.isnan(float(v))]


def _fetch_fred_yoy(fred: Fred, series_id: str) -> list[tuple[date, float]]:
    lookback = 730 + 730
    start  = (date.today() - timedelta(days=lookback)).isoformat()
    cutoff = (date.today() - timedelta(days=730)).isoformat()
    raw    = fred.get_series(series_id, observation_start=start).dropna()
    series = _yoy(raw).dropna().loc[cutoff:]
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


def _fetch_te_multi(url: str, unit_filter: str, unit_row: int = 0, scale: float = 1) -> Optional[tuple[float, date]]:
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
        return round(val * scale, 4), ref_date
    return None


def _fetch_te_multi_pct(url: str, unit_filter: str, unit_row: int = 0) -> Optional[tuple[float, date]]:
    """Multi table: reads Last + Previous level, returns % change and ref date."""
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
        last = _parse_value(texts[1])
        prev = _parse_value(texts[2]) if len(texts) > 2 else None
        if last is None or prev is None or prev == 0:
            return None
        pct = round((last - prev) / abs(prev) * 100, 4)
        ref_date = _parse_date(texts[4] if len(texts) > 4 else "")
        return pct, ref_date
    return None


def _fetch_l2_te(country_id: str) -> Optional[tuple[float, date]]:
    cfg    = L2_TE[country_id]
    url    = cfg["url"]
    layout = cfg["layout"]
    if layout == "calendar":
        return _fetch_te_calendar(url)
    elif layout == "multi_pct":
        return _fetch_te_multi_pct(url, cfg["unit_filter"], cfg.get("unit_row", 0))
    return None


# ── Main run ──────────────────────────────────────────────────────────────────

def run(dry_run: bool = False, local: bool = False, force: bool = False) -> None:
    from db import upsert_reading, log_etl_run, set_local, get_latest_date
    if local:
        set_local(True)

    fred = Fred(api_key=os.environ["FRED_API_KEY"])

    # ── L1 US (FRED) ──────────────────────────────────────────────────────────
    try:
        latest = None if force else get_latest_date("L1", "US")
        rows = _fetch_fred_level(fred, "UNRATE")
        new_rows = [(d, v) for d, v in rows if latest is None or d > latest]
        for reading_date, value in new_rows:
            if dry_run:
                print(f"  L1/US  {reading_date}  {value:.4f}  [UNRATE]")
            else:
                upsert_reading("L1", "US", value, reading_date, SOURCE_FRED, "UNRATE")
        if not dry_run:
            log_etl_run(SOURCE_FRED, "L1", "US", "success", rows_written=len(new_rows))
        print(f"[FRED] L1/US — {len(new_rows)} new rows (skipped {len(rows)-len(new_rows)}) {'(dry run)' if dry_run else 'written'}")
    except Exception as exc:
        if not dry_run:
            log_etl_run(SOURCE_FRED, "L1", "US", "failed", error_message=str(exc))
        print(f"[FRED] ERROR L1/US: {exc}")

    # ── L1 non-US (Trading Economics calendar) ────────────────────────────────
    for country_id, url in L1_TE.items():
        try:
            latest = None if force else get_latest_date("L1", country_id)
            result = _fetch_te_calendar(url)
            if result is None:
                print(f"[TE] L1/{country_id} — no data parsed")
                if not dry_run:
                    log_etl_run(SOURCE_TE, "L1", country_id, "stale", error_message="No data parsed")
                continue
            value, ref_date = result
            if latest is not None and ref_date <= latest:
                print(f"[TE] L1/{country_id} — already up to date (latest: {latest})")
                continue
            if dry_run:
                print(f"  L1/{country_id}  {ref_date}  {value:.4f}  [{url}]")
            else:
                upsert_reading("L1", country_id, value, ref_date, SOURCE_TE, url)
                log_etl_run(SOURCE_TE, "L1", country_id, "success", rows_written=1)
            print(f"[TE] L1/{country_id} — {value} on {ref_date} {'(dry run)' if dry_run else 'written'}")
        except Exception as exc:
            if not dry_run:
                log_etl_run(SOURCE_TE, "L1", country_id, "failed", error_message=str(exc))
            print(f"[TE] ERROR L1/{country_id}: {exc}")

    # ── L2 US (FRED YoY%) ─────────────────────────────────────────────────────
    try:
        latest = None if force else get_latest_date("L2", "US")
        rows = _fetch_fred_yoy(fred, "CES0500000003")
        new_rows = [(d, v) for d, v in rows if latest is None or d > latest]
        for reading_date, value in new_rows:
            if dry_run:
                print(f"  L2/US  {reading_date}  {value:.4f}  [CES0500000003]")
            else:
                upsert_reading("L2", "US", value, reading_date, SOURCE_FRED, "CES0500000003")
        if not dry_run:
            log_etl_run(SOURCE_FRED, "L2", "US", "success", rows_written=len(new_rows))
        print(f"[FRED] L2/US — {len(new_rows)} new rows (skipped {len(rows)-len(new_rows)}) {'(dry run)' if dry_run else 'written'}")
    except Exception as exc:
        if not dry_run:
            log_etl_run(SOURCE_FRED, "L2", "US", "failed", error_message=str(exc))
        print(f"[FRED] ERROR L2/US: {exc}")

    # ── L2 non-US (Trading Economics) ─────────────────────────────────────────
    for country_id in L2_TE:
        try:
            latest = None if force else get_latest_date("L2", country_id)
            result = _fetch_l2_te(country_id)
            if result is None:
                print(f"[TE] L2/{country_id} — no data parsed")
                if not dry_run:
                    log_etl_run(SOURCE_TE, "L2", country_id, "stale", error_message="No data parsed")
                continue
            value, ref_date = result
            if latest is not None and ref_date <= latest:
                print(f"[TE] L2/{country_id} — already up to date (latest: {latest})")
                continue
            pct_label = L2_TE[country_id].get("pct_label", "MoM")
            note = None if country_id == "EA" else f"{pct_label}% derived from wage level (Last vs Previous on TE)"
            if dry_run:
                print(f"  L2/{country_id}  {ref_date}  {value:.4f}% ({pct_label})  [{L2_TE[country_id]['url']}]")
            else:
                upsert_reading("L2", country_id, value, ref_date, SOURCE_TE,
                               L2_TE[country_id]["url"], notes=note)
                log_etl_run(SOURCE_TE, "L2", country_id, "success", rows_written=1)
            print(f"[TE] L2/{country_id} — {value} on {ref_date} {'(dry run)' if dry_run else 'written'}")
        except Exception as exc:
            if not dry_run:
                log_etl_run(SOURCE_TE, "L2", country_id, "failed", error_message=str(exc))
            print(f"[TE] ERROR L2/{country_id}: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--local",   action="store_true")
    parser.add_argument("--force",   action="store_true", help="Re-scrape all rows, ignoring what's already in the DB")
    args = parser.parse_args()
    run(dry_run=args.dry_run, local=args.local, force=args.force)
