"""
FRED scraper — US macro indicators and global Brent crude.

Indicators:
  G1  US  GDP growth (QoQ annualised %)
  G4  US  Industrial Production YoY %
  I1  US  Headline CPI YoY %
  I2  US  Core CPI YoY %
  I3  US  Food CPI YoY %
  M1  US  Fed Funds Rate %
  M2  US  10Y Treasury yield %
  M3  US  10Y-2Y yield spread bps
  L1  US  Unemployment rate %
  L2  US  Average hourly earnings YoY %
  E1  US  Trade balance USD bn
  F3  US  EMBI Global spread bps
  C1  US  Brent crude USD/bbl

Usage:
  python fred_scraper.py --local     # save to ../../data/fred.csv
  python fred_scraper.py --dry-run   # print only, no write
  python fred_scraper.py             # write to Supabase
"""

import os
import math
import argparse
import csv
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from fredapi import Fred
from dotenv import load_dotenv

load_dotenv()

SOURCE = "FRED"

SERIES = [
    ("G1", "US", "A191RL1Q225SBEA", "level"),
    ("G4", "US", "INDPRO",          "yoy"),
    ("I1", "US", "CPIAUCSL",        "yoy"),
    ("I2", "US", "CPILFESL",        "yoy"),
    ("I3", "US", "CPIUFDSL",        "yoy"),
    ("M1", "US", "FEDFUNDS",        "level"),
    ("M2", "US", "DGS10",           "level"),
    ("M3", "US", "T10Y2Y",          "level"),
    ("L1", "US", "UNRATE",          "level"),
    ("L2", "US", "CES0500000003",   "yoy"),
    ("E1", "US", "BOPGSTB",         "level"),
    ("F3", "US", "BAMLH0A0HYM2",    "level"),
    ("C1", "US", "DCOILBRENTEU",    "level"),
]

CSV_PATH = Path(__file__).parent.parent / "data" / "fred.csv"
COLUMNS = ["indicator_id", "country_id", "date", "value", "source", "source_series_id", "ingested_at"]


def _yoy(series: pd.Series) -> pd.Series:
    periods = 12 if (len(series) < 2 or (series.index[1] - series.index[0]).days < 60) else 4
    return series.pct_change(periods=periods) * 100


def _fetch(fred: Fred, series_id: str, transform: str, lookback_days: int = 400) -> pd.Series:
    # yoy needs extra history to compute pct_change(periods=12) — fetch 2 extra years
    fetch_days = lookback_days + 730 if transform == "yoy" else lookback_days
    start = (date.today() - timedelta(days=fetch_days)).isoformat()
    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()
    raw = fred.get_series(series_id, observation_start=start).dropna()
    if transform == "yoy":
        return _yoy(raw).dropna().loc[cutoff:]
    return raw


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

    fred = Fred(api_key=os.environ["FRED_API_KEY"])
    all_rows = []

    for indicator_id, country_id, series_id, transform in SERIES:
        try:
            series = _fetch(fred, series_id, transform)
            if series.empty:
                print(f"[FRED] {indicator_id}/{country_id} ({series_id}) — no data")
                if not dry_run and not local:
                    log_etl_run(SOURCE, indicator_id, country_id, "stale", error_message="Empty series")
                continue

            rows = 0
            now = datetime.utcnow().isoformat()
            for ts, val in series.items():
                if isinstance(val, float) and math.isnan(val):
                    continue

                if dry_run:
                    if len(series) < 3 or ts >= series.index[-3]:
                        print(f"  {indicator_id}/{country_id}  {ts.date()}  {float(val):.4f}  [{series_id}]")
                elif local:
                    all_rows.append({
                        "indicator_id": indicator_id,
                        "country_id": country_id,
                        "date": ts.date().isoformat(),
                        "value": float(val),
                        "source": SOURCE,
                        "source_series_id": series_id,
                        "ingested_at": now,
                    })
                else:
                    upsert_reading(
                        indicator_id=indicator_id,
                        country_id=country_id,
                        value=float(val),
                        reading_date=ts.date(),
                        source=SOURCE,
                        source_series_id=series_id,
                    )
                rows += 1

            if not dry_run and not local:
                log_etl_run(SOURCE, indicator_id, country_id, "success", rows_written=rows)
            mode = "(dry run)" if dry_run else f"-> {CSV_PATH.name}" if local else "written to Supabase"
            print(f"[FRED] {indicator_id}/{country_id} ({series_id}) — {rows} rows {mode}")

        except Exception as exc:
            if not dry_run and not local:
                log_etl_run(SOURCE, indicator_id, country_id, "failed", error_message=str(exc))
            print(f"[FRED] ERROR {indicator_id}/{country_id}: {exc}")

    if local and all_rows:
        _write_csv(all_rows)
        print(f"\nSaved {len(all_rows)} rows -> {CSV_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print only, no write")
    parser.add_argument("--local", action="store_true", help="Save to local CSV instead of Supabase")
    args = parser.parse_args()
    run(dry_run=args.dry_run, local=args.local)
