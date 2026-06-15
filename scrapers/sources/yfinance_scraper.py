"""
yfinance scraper — Financial Markets indicators (F1, F2, C1).

Writes to TWO tables / CSV files:

  1. daily_readings   — one row per (indicator, country, calendar_date)
                        columns: indicator_id, country_id, date, value, source, source_series_id

  2. weekly_readings  — one row per (indicator, country, week_ending friday)
                        columns: indicator_id, country_id, week_ending,
                                 value, prior_value, wow_pct,
                                 source, source_series_id

  Indicators:
    F1  Equity index level (daily) + WoW % (weekly Friday)
    F2  FX rate vs USD  (daily) + WoW % (weekly Friday)
    C1  Brent crude USD/bbl (daily) + WoW % (weekly Friday) — same value all countries

Usage:
  python yfinance_scraper.py --local      # save CSVs to ../../data/
  python yfinance_scraper.py --dry-run    # print samples, no write
  python yfinance_scraper.py              # write to Supabase
"""

import math
import argparse
import csv
from datetime import date, timedelta, datetime
from pathlib import Path

import yfinance as yf
import pandas as pd

SOURCE = "yfinance"
DATA_DIR = Path(__file__).parent.parent / "data"

# ── Ticker definitions ────────────────────────────────────────────────────────

F1_TICKERS = {
    "US": "^GSPC",       # S&P 500
    "EA": "^STOXX50E",   # EuroStoxx 50
    "SG": "^STI",        # Straits Times Index
    "CN": "000001.SS",   # Shanghai Composite
    "IN": "^BSESN",      # BSE Sensex
    "SL": "^CSE",        # Colombo All Share (unavailable on yfinance — rows will be null)
}

F2_TICKERS = {
    "US": ("DX-Y.NYB", False),   # DXY — USD basket, no flip
    "EA": ("EURUSD=X",  False),  # EUR/USD, no flip
    "SG": ("USDSGD=X",  True),   # flip: higher = SGD weaker
    "CN": ("USDCNY=X",  True),   # flip
    "IN": ("USDINR=X",  True),   # flip
    "SL": ("USDLKR=X",  True),   # flip
}

C1_TICKER = "BZ=F"   # Brent crude front-month futures

COUNTRIES = ["US", "EA", "SG", "CN", "IN", "SL"]

LOOKBACK_DAYS = 730   # fetch ~2 years of history on first run

# ── CSV column definitions ────────────────────────────────────────────────────

DAILY_COLS   = ["indicator_id", "country_id", "date", "value",
                "source", "source_series_id", "ingested_at"]

WEEKLY_COLS  = ["indicator_id", "country_id", "week_ending",
                "value", "prior_value", "wow_pct",
                "source", "source_series_id", "ingested_at"]


# ── Fetch helpers ─────────────────────────────────────────────────────────────

def _fetch_daily(ticker: str) -> pd.Series:
    """Download daily closes. Returns a Series indexed by date."""
    start = (date.today() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    df = yf.download(ticker, start=start, auto_adjust=True, progress=False)
    if df.empty:
        return pd.Series(dtype=float, name=ticker)
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close.dropna().rename(ticker)


def _to_weekly(series: pd.Series) -> pd.Series:
    """Resample to last trading day of each week ending Friday."""
    return series.resample("W-FRI").last().dropna()


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _wow_pct(cur: float | None, prior: float | None) -> float | None:
    if cur is None or prior is None or prior == 0:
        return None
    return round((cur / prior - 1) * 100, 4)


# ── Row builders ──────────────────────────────────────────────────────────────

def _build_rows(indicator_id: str, ticker: str, country_id: str,
                flip_wow: bool = False) -> tuple[list[dict], list[dict]]:
    """
    For a single ticker + country, return:
      (daily_rows, weekly_rows)
    flip_wow=True for USD/XXX pairs so positive WoW% = local currency appreciated.
    """
    now = datetime.utcnow().isoformat()
    daily_series = _fetch_daily(ticker)

    daily_rows = []
    for ts, val in daily_series.items():
        v = _safe_float(val)
        if v is None:
            continue
        daily_rows.append({
            "indicator_id":    indicator_id,
            "country_id":      country_id,
            "date":            ts.date().isoformat(),
            "value":           v,
            "source":          SOURCE,
            "source_series_id": ticker,
            "ingested_at":     now,
        })

    weekly_series = _to_weekly(daily_series)
    weekly_rows = []
    prev = None
    for ts, val in weekly_series.items():
        cur = _safe_float(val)
        if cur is None:
            prev = None
            continue
        wow = _wow_pct(cur, prev)
        if wow is not None and flip_wow:
            wow = -wow   # flip so positive = local currency stronger
        weekly_rows.append({
            "indicator_id":    indicator_id,
            "country_id":      country_id,
            "week_ending":     ts.date().isoformat(),
            "value":           cur,
            "prior_value":     prev,
            "wow_pct":         wow,
            "source":          SOURCE,
            "source_series_id": ticker,
            "ingested_at":     now,
        })
        prev = cur

    return daily_rows, weekly_rows


# ── CSV writers ───────────────────────────────────────────────────────────────

def _append_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


# ── Supabase writers ──────────────────────────────────────────────────────────

def _supabase_daily(rows: list[dict]) -> None:
    from db import get_client
    if not rows:
        return
    get_client().table("daily_readings").upsert(
        rows, on_conflict="indicator_id,country_id,date"
    ).execute()


def _supabase_weekly(rows: list[dict]) -> None:
    from db import get_client
    if not rows:
        return
    get_client().table("weekly_readings").upsert(
        rows, on_conflict="indicator_id,country_id,week_ending"
    ).execute()


# ── Main run ──────────────────────────────────────────────────────────────────

def run(dry_run: bool = False, local: bool = False) -> None:

    # Collect all (indicator_id, country_id, ticker, flip_wow) jobs
    jobs: list[tuple[str, str, str, bool]] = []

    for country_id, ticker in F1_TICKERS.items():
        jobs.append(("F1", country_id, ticker, False))

    for country_id, (ticker, flip) in F2_TICKERS.items():
        jobs.append(("F2", country_id, ticker, flip))

    # C1 Brent — same ticker, write a row for every country
    for country_id in COUNTRIES:
        jobs.append(("C1", country_id, C1_TICKER, False))

    all_daily:  list[dict] = []
    all_weekly: list[dict] = []

    # Avoid downloading C1 six times — cache it
    _c1_cache: dict[str, tuple[list, list]] = {}

    for indicator_id, country_id, ticker, flip_wow in jobs:
        cache_key = f"{indicator_id}:{ticker}"

        if indicator_id == "C1" and cache_key in _c1_cache:
            d_rows, w_rows = _c1_cache[cache_key]
            # Re-stamp country_id (rows were built for first country)
            d_rows = [{**r, "country_id": country_id} for r in d_rows]
            w_rows = [{**r, "country_id": country_id} for r in w_rows]
        else:
            try:
                d_rows, w_rows = _build_rows(indicator_id, ticker, country_id, flip_wow)
                if indicator_id == "C1":
                    _c1_cache[cache_key] = (d_rows, w_rows)
            except Exception as exc:
                print(f"  ERROR {indicator_id}/{country_id} ({ticker}): {exc}")
                continue

        all_daily.extend(d_rows)
        all_weekly.extend(w_rows)

        d_count = len(d_rows)
        w_count = len(w_rows)
        status = f"{d_count} daily + {w_count} weekly rows"

        if dry_run:
            # Print last 3 daily and last 2 weekly
            print(f"\n  {indicator_id}/{country_id} ({ticker}) -- {status}")
            print("    Daily (last 3):")
            for r in d_rows[-3:]:
                print(f"      {r['date']}  {r['value']:.4f}")
            print("    Weekly (last 2):")
            for r in w_rows[-2:]:
                print(f"      week={r['week_ending']}  val={r['value']:.4f}  "
                      f"prior={r['prior_value']}  wow%={r['wow_pct']}")
        else:
            print(f"  {indicator_id}/{country_id} ({ticker}) -- {status}")

    if dry_run:
        return

    if local:
        daily_path  = DATA_DIR / "daily_readings.csv"
        weekly_path = DATA_DIR / "weekly_readings.csv"
        _append_csv(daily_path,  all_daily,  DAILY_COLS)
        _append_csv(weekly_path, all_weekly, WEEKLY_COLS)
        print(f"\nSaved {len(all_daily)} daily rows  -> {daily_path}")
        print(f"Saved {len(all_weekly)} weekly rows -> {weekly_path}")
    else:
        _supabase_daily(all_daily)
        _supabase_weekly(all_weekly)
        print(f"\nWritten {len(all_daily)} daily + {len(all_weekly)} weekly rows to Supabase")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print samples, no write")
    parser.add_argument("--local",   action="store_true", help="Save to CSV in data/ folder")
    args = parser.parse_args()
    run(dry_run=args.dry_run, local=args.local)
