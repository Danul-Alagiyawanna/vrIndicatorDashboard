"""
Financial markets scrapers — F1, F2, F3.

  F1  Equity Index (level, daily closes)
        US/EA/SG/CN/IN — yfinance
        SL             — TradingView (CSELK-ASI, current close)

  F2  FX vs USD (rate, daily closes)
        US  — DX-Y.NYB (DXY index, no flip)
        EA  — EURUSD=X (no flip)
        SG/CN/IN/SL — USDXXX=X (stored as raw rate; weekly_market view handles sign)

  F3  Credit Spreads / Risk Sentiment (bps)
        US  — FRED (BAMLH0A0HYM2, HY spread as risk proxy)
        Others — not available on free APIs

All F1/F2 daily closes write to `readings`.
The weekly_market view in Postgres derives Friday closes and WoW% — nothing computed here.

Usage:
  python financial.py --dry-run
  python financial.py --local
  python financial.py
"""

import os
import re
import argparse
import math
from datetime import date, timedelta, datetime
from typing import Optional

import pandas as pd
import yfinance as yf
from fredapi import Fred
from scrapling.fetchers import StealthyFetcher
from dotenv import load_dotenv

load_dotenv()

SOURCE_YFINANCE    = "yfinance"
SOURCE_FRED        = "FRED"
SOURCE_TRADINGVIEW = "TradingView"

F1_SL_URL = "https://www.tradingview.com/symbols/CSELK-ASI/technicals/"

LOOKBACK_DAYS = 730

F1_TICKERS: dict[str, str] = {
    "US": "^GSPC",
    "EA": "^STOXX50E",
    "SG": "^STI",
    "CN": "000001.SS",
    "IN": "^BSESN",
    # SL: ^CSE not available on yfinance
}

# (ticker, flip_sign_for_wow)  — flip stored in schema notes; raw rate always stored
F2_TICKERS: dict[str, tuple[str, bool]] = {
    "US": ("DX-Y.NYB", False),
    "EA": ("EURUSD=X",  False),
    "SG": ("USDSGD=X",  True),
    "CN": ("USDCNY=X",  True),
    "IN": ("USDINR=X",  True),
    "SL": ("USDLKR=X",  True),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _fetch_daily(ticker: str) -> list[tuple[date, float]]:
    start  = (date.today() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    df     = yf.download(ticker, start=start, auto_adjust=True, progress=False)
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


def _fetch_tradingview_price(url: str) -> Optional[float]:
    """Scrape the current price from a TradingView symbol page."""
    page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
    els = page.css('[class*="last"]')
    for el in els:
        text = el.css('::text').get('').strip().replace(',', '')
        try:
            return float(text)
        except ValueError:
            continue
    return None


def _yoy(series: pd.Series) -> pd.Series:
    periods = 12 if (len(series) < 2 or (series.index[1] - series.index[0]).days < 60) else 4
    return series.pct_change(periods=periods) * 100


# ── Main run ──────────────────────────────────────────────────────────────────

def run(dry_run: bool = False, local: bool = False) -> None:
    from db import upsert_reading, log_etl_run, set_local
    if local:
        set_local(True)

    fred = Fred(api_key=os.environ["FRED_API_KEY"])

    # ── F1 — Equity index daily closes ────────────────────────────────────────
    for country_id, ticker in F1_TICKERS.items():
        try:
            rows = _fetch_daily(ticker)
            if not rows:
                print(f"[yfinance] F1/{country_id} ({ticker}) — no data")
                if not dry_run:
                    log_etl_run(SOURCE_YFINANCE, "F1", country_id, "stale",
                                error_message="Empty series")
                continue
            for reading_date, value in rows:
                if dry_run:
                    pass  # print only last 3 below
                else:
                    upsert_reading("F1", country_id, value, reading_date,
                                   SOURCE_YFINANCE, ticker)
            if dry_run:
                print(f"  F1/{country_id} ({ticker}) — {len(rows)} rows (dry run)")
                for d, v in rows[-3:]:
                    print(f"    {d}  {v:.4f}")
            else:
                log_etl_run(SOURCE_YFINANCE, "F1", country_id, "success", rows_written=len(rows))
                print(f"[yfinance] F1/{country_id} ({ticker}) — {len(rows)} rows written")
        except Exception as exc:
            if not dry_run:
                log_etl_run(SOURCE_YFINANCE, "F1", country_id, "failed", error_message=str(exc))
            print(f"[yfinance] ERROR F1/{country_id}: {exc}")

    # ── F1/SL — CSE All Share Index via TradingView ───────────────────────────
    try:
        from db import get_latest_date
        latest = get_latest_date("F1", "SL")
        today  = date.today()
        if latest is not None and latest >= today:
            print(f"[TV] F1/SL — already up to date (latest: {latest})")
        else:
            value = _fetch_tradingview_price(F1_SL_URL)
            if value is None:
                print("[TV] F1/SL — no price found on TradingView page")
                if not dry_run:
                    log_etl_run(SOURCE_TRADINGVIEW, "F1", "SL", "stale", error_message="No price found")
            else:
                reading_date = today
                if dry_run:
                    print(f"  F1/SL  {reading_date}  {value:.2f}  [{F1_SL_URL}]")
                else:
                    upsert_reading("F1", "SL", value, reading_date, SOURCE_TRADINGVIEW, F1_SL_URL)
                    log_etl_run(SOURCE_TRADINGVIEW, "F1", "SL", "success", rows_written=1)
                print(f"[TV] F1/SL — {value} on {reading_date} {'(dry run)' if dry_run else 'written'}")
    except Exception as exc:
        if not dry_run:
            log_etl_run(SOURCE_TRADINGVIEW, "F1", "SL", "failed", error_message=str(exc))
        print(f"[TV] ERROR F1/SL: {exc}")

    # ── F2 — FX daily closes (raw rate) ───────────────────────────────────────
    for country_id, (ticker, flip) in F2_TICKERS.items():
        flip_note = "raw USDxxx rate; weekly_market view flips sign for appreciation" if flip else None
        try:
            rows = _fetch_daily(ticker)
            if not rows:
                print(f"[yfinance] F2/{country_id} ({ticker}) — no data")
                if not dry_run:
                    log_etl_run(SOURCE_YFINANCE, "F2", country_id, "stale",
                                error_message="Empty series")
                continue
            for reading_date, value in rows:
                if dry_run:
                    pass
                else:
                    upsert_reading("F2", country_id, value, reading_date,
                                   SOURCE_YFINANCE, ticker, notes=flip_note)
            if dry_run:
                print(f"  F2/{country_id} ({ticker}) — {len(rows)} rows (dry run)")
                for d, v in rows[-3:]:
                    print(f"    {d}  {v:.4f}")
            else:
                log_etl_run(SOURCE_YFINANCE, "F2", country_id, "success", rows_written=len(rows))
                print(f"[yfinance] F2/{country_id} ({ticker}) — {len(rows)} rows written")
        except Exception as exc:
            if not dry_run:
                log_etl_run(SOURCE_YFINANCE, "F2", country_id, "failed", error_message=str(exc))
            print(f"[yfinance] ERROR F2/{country_id}: {exc}")

    # ── F3 — Credit spreads / risk sentiment ──────────────────────────────────
    # US only: FRED HY spread as proxy
    # Non-US sovereign CDS not available on free APIs
    try:
        start  = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
        series = fred.get_series("BAMLH0A0HYM2", observation_start=start).dropna()
        rows   = [(ts.date(), round(float(v), 4)) for ts, v in series.items()
                  if not math.isnan(float(v))]
        for reading_date, value in rows:
            if dry_run:
                pass
            else:
                upsert_reading("F3", "US", value, reading_date, SOURCE_FRED, "BAMLH0A0HYM2")
        if dry_run:
            print(f"  F3/US — {len(rows)} rows (dry run)")
            for d, v in rows[-3:]:
                print(f"    {d}  {v:.4f} bps")
        else:
            log_etl_run(SOURCE_FRED, "F3", "US", "success", rows_written=len(rows))
            print(f"[FRED] F3/US (BAMLH0A0HYM2) — {len(rows)} rows written")
    except Exception as exc:
        if not dry_run:
            log_etl_run(SOURCE_FRED, "F3", "US", "failed", error_message=str(exc))
        print(f"[FRED] ERROR F3/US: {exc}")

    print("[F3] Non-US credit spreads — not available on free APIs. Only US (FRED HY proxy) written.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--local",   action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run, local=args.local)
