"""
Monetary policy scrapers — M1, M2, M3.

  M1  Policy Rate (%)
        US          — FRED  (FEDFUNDS)
        EA/CN/IN    — Trading Economics
        SL          — CBSL via Trading Economics
        SG          — skipped (MAS uses exchange-rate band, no single rate)

  M2  10Y Government Bond Yield (%)
        US          — FRED  (DGS10)
        EA/CN/IN/SG — Trading Economics (summary9 layout)
        SL          — investing.com

  M3  Yield Curve Slope (10Y − 2Y, bps)
        US          — FRED  (T10Y2Y, already in bps)
        EA/CN/IN/SG/SL — derived: M2 minus 2Y yield (both from TE/investing.com)

Usage:
  python monetary.py --dry-run
  python monetary.py --local
  python monetary.py
"""

import os
import re
import argparse
import math
from datetime import date, timedelta, datetime
from typing import Optional

import requests
import pandas as pd
from fredapi import Fred
from scrapling.fetchers import StealthyFetcher
from dotenv import load_dotenv

load_dotenv()

SOURCE_FRED = "FRED"
SOURCE_TE   = "Trading Economics"
SOURCE_CBSL = "CBSL"

NON_US = ["EA", "SG", "CN", "IN", "SL"]

# ── M1 policy rate pages ──────────────────────────────────────────────────────

M1_TE: dict[str, dict] = {
    "EA": {"url": "https://tradingeconomics.com/euro-area/interest-rate", "layout": "calendar"},
    "CN": {"url": "https://tradingeconomics.com/china/interest-rate",     "layout": "calendar"},
    "IN": {"url": "https://tradingeconomics.com/india/interest-rate",     "layout": "calendar"},
    "SL": {"url": "https://tradingeconomics.com/sri-lanka/interest-rate", "layout": "calendar"},
    # SG intentionally omitted
}

# ── M2 10Y yield pages ────────────────────────────────────────────────────────

M2_TE: dict[str, dict] = {
    "EA": {"url": "https://tradingeconomics.com/euro-area/government-bond-yield",  "layout": "summary9"},
    "CN": {"url": "https://tradingeconomics.com/china/government-bond-yield",      "layout": "summary9"},
    "IN": {"url": "https://tradingeconomics.com/india/government-bond-yield",      "layout": "summary9"},
    "SG": {"url": "https://tradingeconomics.com/singapore/government-bond-yield",  "layout": "summary9"},
    "SL": {"url": "https://www.investing.com/rates-bonds/sri-lanka-10-year", "layout": "investing"},
}

# ── 2Y yield pages (intermediate — used only for M3 spread) ──────────────────

Y2_TE: dict[str, dict] = {
    "EA": {"url": "https://data-api.ecb.europa.eu/service/data/FM/M.U2.EUR.4F.BB.U2_2Y.YLD?lastNObservations=3&format=jsondata", "layout": "ecb"},
    "CN": {"url": "https://tradingeconomics.com/gcny2y:gov",                           "layout": "ticker"},
    "IN": {"url": "https://tradingeconomics.com/gind2y:ind",                           "layout": "ticker"},
    "SG": {"url": "https://tradingeconomics.com/singapore/2-year-bond-yield",          "layout": "ticker"},
    "SL": {"url": "https://www.investing.com/rates-bonds/sri-lanka-2-year-bond-yield", "layout": "investing"},
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


def _fetch_fred_series(fred: Fred, series_id: str, lookback_days: int = 730) -> list[tuple[date, float]]:
    start = (date.today() - timedelta(days=lookback_days)).isoformat()
    series = fred.get_series(series_id, observation_start=start).dropna()
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


def _fetch_te_ticker(url: str, href_filter: str = "2-year") -> Optional[tuple[float, date]]:
    """TE ticker pages (e.g. gcny2y:gov) — 7-cell rows, col 1 = value, col 6 = date.
    href_filter: substring to match in col0's anchor href to select the right row."""
    page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
    rows = page.css("table#p tr") or page.css("table tr")
    for row in rows[1:]:
        cells = row.css("td")
        if len(cells) != 7:
            continue
        href = cells[0].css("a::attr(href)").get("").lower()
        if href_filter and href_filter not in href:
            continue
        val = _parse_value(cells[1].css("::text").get("").strip())
        if val is None:
            continue
        date_text = cells[6].css("::text").get("").strip()
        ref_date = _parse_date(date_text) if date_text else date.today().replace(day=1)
        return val, ref_date
    return None


def _fetch_te_summary9(url: str) -> Optional[tuple[float, date]]:
    """9-cell summary row on TE bond yield pages."""
    page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
    rows = page.css("table#p tr") or page.css("table tr")
    for row in rows:
        cells = row.css("td")
        if len(cells) != 9:
            continue
        texts = [c.css("::text").get("").strip() for c in cells]
        if "percent" not in texts[6].lower():
            continue
        val = _parse_value(texts[1])
        if val is None:
            continue
        return val, date.today().replace(day=1)
    return None


def _fetch_investing(url: str) -> Optional[tuple[float, date]]:
    """investing.com bond yield page."""
    page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
    el = page.css('[data-test="instrument-price-last"]')
    if el:
        val = _parse_value(el[0].css("::text").get("").strip())
        if val is not None:
            return val, date.today().replace(day=1)
    rows = page.css("table tr")
    for row in rows[1:]:
        cells = row.css("td")
        if len(cells) < 2:
            continue
        val = _parse_value(cells[1].css("::text").get("").strip())
        if val is None:
            continue
        ref_date = _parse_date(cells[0].css("::text").get("").strip())
        return val, ref_date
    return None


def _fetch_ecb(url: str) -> Optional[tuple[float, date]]:
    """ECB SDW REST API — returns latest observation value and period date."""
    resp = requests.get(url, timeout=30, headers={"Accept": "application/json"})
    resp.raise_for_status()
    data = resp.json()
    try:
        series = data["dataSets"][0]["series"]["0:0:0:0:0:0:0"]
        obs    = series["observations"]
        periods = data["structure"]["dimensions"]["observation"][0]["values"]
        # obs keys are string indices; take the last one
        last_idx = str(max(int(k) for k in obs))
        value    = obs[last_idx][0]
        period   = periods[int(last_idx)]["id"]   # e.g. "2026-05"
        ref_date = date.fromisoformat(period + "-01")
        return round(float(value), 4), ref_date
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _fetch_yield(cfg: dict) -> Optional[tuple[float, date]]:
    layout = cfg["layout"]
    url    = cfg["url"]
    if layout == "calendar":
        return _fetch_te_calendar(url)
    elif layout == "ticker":
        return _fetch_te_ticker(url)
    elif layout == "summary9":
        return _fetch_te_summary9(url)
    elif layout == "investing":
        return _fetch_investing(url)
    elif layout == "ecb":
        return _fetch_ecb(url)
    return None


# ── Main run ──────────────────────────────────────────────────────────────────

def run(dry_run: bool = False, local: bool = False, force: bool = False) -> None:
    from db import upsert_reading, log_etl_run, set_local, get_latest_date
    if local:
        set_local(True)

    fred = Fred(api_key=os.environ["FRED_API_KEY"])

    # ── M1 US (FRED) ──────────────────────────────────────────────────────────
    try:
        latest = None if force else get_latest_date("M1", "US")
        rows = _fetch_fred_series(fred, "FEDFUNDS")
        new_rows = [(d, v) for d, v in rows if latest is None or d > latest]
        for reading_date, value in new_rows:
            if dry_run:
                print(f"  M1/US  {reading_date}  {value:.4f}  [FEDFUNDS]")
            else:
                upsert_reading("M1", "US", value, reading_date, SOURCE_FRED, "FEDFUNDS")
        if not dry_run:
            log_etl_run(SOURCE_FRED, "M1", "US", "success", rows_written=len(new_rows))
        print(f"[FRED] M1/US — {len(new_rows)} new rows (skipped {len(rows)-len(new_rows)}) {'(dry run)' if dry_run else 'written'}")
    except Exception as exc:
        if not dry_run:
            log_etl_run(SOURCE_FRED, "M1", "US", "failed", error_message=str(exc))
        print(f"[FRED] ERROR M1/US: {exc}")

    # ── M1 non-US (Trading Economics / CBSL) ──────────────────────────────────
    for country_id, cfg in M1_TE.items():
        source = SOURCE_CBSL if country_id == "SL" else SOURCE_TE
        try:
            latest = None if force else get_latest_date("M1", country_id)
            result = _fetch_te_calendar(cfg["url"])
            if result is None:
                print(f"[TE] M1/{country_id} — no data parsed")
                if not dry_run:
                    log_etl_run(source, "M1", country_id, "stale", error_message="No data parsed")
                continue
            value, ref_date = result
            if latest is not None and ref_date <= latest:
                print(f"[TE] M1/{country_id} — already up to date (latest: {latest})")
                continue
            if dry_run:
                print(f"  M1/{country_id}  {ref_date}  {value:.4f}  [{cfg['url']}]")
            else:
                upsert_reading("M1", country_id, value, ref_date, source, cfg["url"])
                log_etl_run(source, "M1", country_id, "success", rows_written=1)
            print(f"[TE] M1/{country_id} — {value} on {ref_date} {'(dry run)' if dry_run else 'written'}")
        except Exception as exc:
            if not dry_run:
                log_etl_run(source, "M1", country_id, "failed", error_message=str(exc))
            print(f"[TE] ERROR M1/{country_id}: {exc}")

    print("[M1] SG — skipped (MAS uses exchange-rate band, no single policy rate)")

    # ── M2 US (FRED) ──────────────────────────────────────────────────────────
    try:
        latest = None if force else get_latest_date("M2", "US")
        rows = _fetch_fred_series(fred, "DGS10")
        new_rows = [(d, v) for d, v in rows if latest is None or d > latest]
        for reading_date, value in new_rows:
            if dry_run:
                print(f"  M2/US  {reading_date}  {value:.4f}  [DGS10]")
            else:
                upsert_reading("M2", "US", value, reading_date, SOURCE_FRED, "DGS10")
        if not dry_run:
            log_etl_run(SOURCE_FRED, "M2", "US", "success", rows_written=len(new_rows))
        print(f"[FRED] M2/US — {len(new_rows)} new rows (skipped {len(rows)-len(new_rows)}) {'(dry run)' if dry_run else 'written'}")
    except Exception as exc:
        if not dry_run:
            log_etl_run(SOURCE_FRED, "M2", "US", "failed", error_message=str(exc))
        print(f"[FRED] ERROR M2/US: {exc}")

    # ── M2 non-US + intermediate 2Y yields for M3 ─────────────────────────────
    yield_10y: dict[str, tuple[float, date]] = {}
    yield_2y:  dict[str, tuple[float, date]] = {}

    for country_id, cfg in M2_TE.items():
        source = SOURCE_CBSL if country_id == "SL" else SOURCE_TE
        try:
            latest = None if force else get_latest_date("M2", country_id)
            result = _fetch_yield(cfg)
            if result is None:
                print(f"[TE] M2/{country_id} — no data parsed")
                if not dry_run:
                    log_etl_run(source, "M2", country_id, "stale", error_message="No data parsed")
                continue
            value, ref_date = result
            yield_10y[country_id] = (value, ref_date)
            if latest is not None and ref_date <= latest:
                print(f"[TE] M2/{country_id} — already up to date (latest: {latest})")
                continue
            if dry_run:
                print(f"  M2/{country_id}  {ref_date}  {value:.4f}  [{cfg['url']}]")
            else:
                upsert_reading("M2", country_id, value, ref_date, source, cfg["url"])
                log_etl_run(source, "M2", country_id, "success", rows_written=1)
            print(f"[TE] M2/{country_id} — {value} on {ref_date} {'(dry run)' if dry_run else 'written'}")
        except Exception as exc:
            if not dry_run:
                log_etl_run(source, "M2", country_id, "failed", error_message=str(exc))
            print(f"[TE] ERROR M2/{country_id}: {exc}")

    for country_id, cfg in Y2_TE.items():
        try:
            result = _fetch_yield(cfg)
            if result is None:
                print(f"[TE] 2Y/{country_id} — no data (M3 spread will be skipped)")
                continue
            value, ref_date = result
            yield_2y[country_id] = (value, ref_date)
            print(f"[TE] 2Y/{country_id} — {value} on {ref_date} (intermediate for M3)")
        except Exception as exc:
            print(f"[TE] ERROR 2Y/{country_id}: {exc}")

    # ── M3 US (FRED — already in bps) ─────────────────────────────────────────
    try:
        latest = None if force else get_latest_date("M3", "US")
        rows = _fetch_fred_series(fred, "T10Y2Y")
        new_rows = [(d, v) for d, v in rows if latest is None or d > latest]
        for reading_date, value in new_rows:
            value_bps = round(value * 100, 2)
            if dry_run:
                print(f"  M3/US  {reading_date}  {value_bps:.2f} bps  [T10Y2Y]")
            else:
                upsert_reading("M3", "US", value_bps, reading_date, SOURCE_FRED, "T10Y2Y")
        if not dry_run:
            log_etl_run(SOURCE_FRED, "M3", "US", "success", rows_written=len(new_rows))
        print(f"[FRED] M3/US — {len(new_rows)} new rows (skipped {len(rows)-len(new_rows)}) {'(dry run)' if dry_run else 'written'}")
    except Exception as exc:
        if not dry_run:
            log_etl_run(SOURCE_FRED, "M3", "US", "failed", error_message=str(exc))
        print(f"[FRED] ERROR M3/US: {exc}")

    # ── M3 non-US (derived: 10Y - 2Y in bps) ─────────────────────────────────
    for country_id in sorted(set(yield_10y) | set(yield_2y)):
        if country_id not in yield_10y or country_id not in yield_2y:
            print(f"[TE] M3/{country_id} — skipped (missing 10Y or 2Y yield)")
            continue
        y10, d10 = yield_10y[country_id]
        y2,  _   = yield_2y[country_id]
        spread   = round((y10 - y2) * 100, 2)
        source   = SOURCE_CBSL if country_id == "SL" else SOURCE_TE
        latest   = None if force else get_latest_date("M3", country_id)
        if latest is not None and d10 <= latest:
            print(f"[TE] M3/{country_id} — already up to date (latest: {latest})")
            continue
        if dry_run:
            print(f"  M3/{country_id}  {d10}  {spread} bps  (10Y={y10} − 2Y={y2})")
        else:
            upsert_reading("M3", country_id, spread, d10, source, "10Y-2Y")
            log_etl_run(source, "M3", country_id, "success", rows_written=1)
        print(f"[TE] M3/{country_id} — {spread} bps on {d10} {'(dry run)' if dry_run else 'written'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--local",   action="store_true")
    parser.add_argument("--force",   action="store_true", help="Re-scrape all rows, ignoring what's already in the DB")
    args = parser.parse_args()
    run(dry_run=args.dry_run, local=args.local, force=args.force)
