"""
Commodities scraper — C1.

  C1  Brent Crude Oil (USD/bbl)
        Global — yfinance (BZ=F, daily closes) as primary
                 FRED (DCOILBRENTEU) as fallback / cross-check

C1 is a global series: country_id = None in `readings`.
The weekly_market view fans it out per country at query time.

Usage:
  python commodities.py --dry-run
  python commodities.py --local
  python commodities.py
"""

import os
import argparse
import math
from datetime import date, timedelta, datetime
from typing import Optional

import pandas as pd
import yfinance as yf
from fredapi import Fred
from dotenv import load_dotenv

load_dotenv()

SOURCE_YFINANCE = "yfinance"
SOURCE_FRED     = "FRED"

LOOKBACK_DAYS = 730


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _fetch_yfinance() -> list[tuple[date, float]]:
    start = (date.today() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    df    = yf.download("BZ=F", start=start, auto_adjust=True, progress=False)
    if df.empty:
        return []
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    rows = []
    for ts, val in close.dropna().items():
        v = _safe_float(val)
        if v is not None:
            rows.append((ts.date(), v))
    return rows


def _fetch_fred(fred: Fred) -> list[tuple[date, float]]:
    start  = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    series = fred.get_series("DCOILBRENTEU", observation_start=start).dropna()
    return [(ts.date(), round(float(v), 4)) for ts, v in series.items()
            if not math.isnan(float(v))]


# ── Main run ──────────────────────────────────────────────────────────────────

def run(dry_run: bool = False, local: bool = False) -> None:
    from db import upsert_reading, log_etl_run, set_local
    if local:
        set_local(True)

    # Try yfinance first; fall back to FRED if empty
    rows: list[tuple[date, float]] = []
    source     = SOURCE_YFINANCE
    series_ref = "BZ=F"

    try:
        rows = _fetch_yfinance()
    except Exception as exc:
        print(f"[yfinance] C1 fetch failed ({exc}), trying FRED...")

    if not rows:
        try:
            fred = Fred(api_key=os.environ["FRED_API_KEY"])
            rows = _fetch_fred(fred)
            source     = SOURCE_FRED
            series_ref = "DCOILBRENTEU"
        except Exception as exc:
            print(f"[FRED] C1 fetch also failed: {exc}")

    if not rows:
        print("[C1] No data from either source.")
        if not dry_run:
            from db import log_etl_run
            log_etl_run("yfinance/FRED", "C1", None, "failed",
                        error_message="Both yfinance and FRED returned no data")
        return

    for reading_date, value in rows:
        if dry_run:
            pass
        else:
            # country_id=None — global series
            upsert_reading("C1", None, value, reading_date, source, series_ref)

    if dry_run:
        print(f"  C1/GLOBAL ({source}: {series_ref}) — {len(rows)} rows (dry run)")
        for d, v in rows[-5:]:
            print(f"    {d}  {v:.2f} USD/bbl")
    else:
        from db import log_etl_run
        log_etl_run(source, "C1", None, "success", rows_written=len(rows))
        print(f"[{source}] C1/GLOBAL ({series_ref}) — {len(rows)} rows written")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--local",   action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run, local=args.local)
