"""
External sector scrapers — E1, E2, E3.

  E1  Trade Balance (USD bn)
        US          — FRED  (BOPGSTB, level)
        EA/SG       — Trading Economics (calendar layout, scale 1e-3 local bn → USD bn)
        CN/IN       — Trading Economics (multi layout, USD bn)
        SL          — Trading Economics (multi layout, USD mn → USD bn)

  E2  FX Reserves (USD bn)
        EA/SG       — Trading Economics
        CN          — Trading Economics (USD mn → USD bn)
        IN          — Trading Economics (calendar, USD mn → USD bn)
        SL          — CBSL via Trading Economics (USD mn → USD bn)

  E3  Remittances (USD mn)
        IN          — Reserve Bank of India via Trading Economics
        SL          — CBSL via Trading Economics

Usage:
  python external.py --dry-run
  python external.py --local
  python external.py
"""

import os
import re
import argparse
import math
from datetime import date, timedelta, datetime
from typing import Optional

from fredapi import Fred
from scrapling.fetchers import StealthyFetcher
from dotenv import load_dotenv

load_dotenv()

SOURCE_FRED = "FRED"
SOURCE_TE   = "Trading Economics"
SOURCE_CBSL = "CBSL"

# ── Page configs ──────────────────────────────────────────────────────────────

E1_TE: dict[str, dict] = {
    "EA": {"url": "https://tradingeconomics.com/euro-area/balance-of-trade",  "layout": "calendar", "scale": 1e-3},
    "CN": {"url": "https://tradingeconomics.com/china/balance-of-trade",      "layout": "multi", "unit_filter": "USD Billion", "unit_row": 0, "scale": 1},
    "IN": {"url": "https://tradingeconomics.com/india/balance-of-trade",      "layout": "multi", "unit_filter": "USD Billion", "unit_row": 0, "scale": 1},
    "SG": {"url": "https://tradingeconomics.com/singapore/balance-of-trade",  "layout": "calendar", "scale": 1e-3},
    "SL": {"url": "https://tradingeconomics.com/sri-lanka/balance-of-trade",  "layout": "multi", "unit_filter": "USD Million", "unit_row": 0, "scale": 1e-3},
}

E2_US = {"url": "https://tradingeconomics.com/united-states/foreign-exchange-reserves", "layout": "multi", "unit_filter": "USD Million", "unit_row": 1, "scale": 1e-3}

E2_TE: dict[str, dict] = {
    "EA": {"url": "https://tradingeconomics.com/euro-area/foreign-exchange-reserves",  "layout": "multi", "unit_filter": "USD Billion", "unit_row": 0, "scale": 1},
    "CN": {"url": "https://tradingeconomics.com/china/foreign-exchange-reserves",      "layout": "multi", "unit_filter": "USD Million",  "unit_row": 0, "scale": 1e-3},
    "IN": {"url": "https://tradingeconomics.com/india/foreign-exchange-reserves",      "layout": "calendar", "scale": 1e-3},
    "SG": {"url": "https://tradingeconomics.com/singapore/foreign-exchange-reserves",  "layout": "calendar", "scale": 1e-3},
    "SL": {"url": "https://tradingeconomics.com/sri-lanka/foreign-exchange-reserves",  "layout": "multi", "unit_filter": "USD Million", "unit_row": 0, "scale": 1e-3},
}

E3_TE: dict[str, dict] = {
    "IN": {"url": "https://tradingeconomics.com/india/remittances",     "layout": "multi", "unit_filter": "USD Million", "unit_row": 3, "scale": 1},
    "SL": {"url": "https://tradingeconomics.com/sri-lanka/remittances", "layout": "multi", "unit_filter": "USD Million", "unit_row": 6, "scale": 1},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_value(text: str) -> Optional[float]:
    t     = text.strip()
    upper = t.upper()
    has_billions  = upper.endswith("B") or "B " in upper
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


def _fetch_te_calendar(url: str, scale: float = 1) -> Optional[tuple[float, date]]:
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
        best = (round(val * scale, 4), ref_date)
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


def _fetch_te(indicator_id: str, country_id: str, cfg: dict) -> Optional[tuple[float, date]]:
    url    = cfg["url"]
    layout = cfg["layout"]
    scale  = cfg.get("scale", 1)
    if layout == "calendar":
        return _fetch_te_calendar(url, scale)
    return _fetch_te_multi(url, cfg.get("unit_filter", ""), cfg.get("unit_row", 0), scale)


# ── Main run ──────────────────────────────────────────────────────────────────

def _fetch_eurusd(fred: Fred) -> float:
    """Return the latest available EUR/USD rate from FRED (DEXUSEU)."""
    try:
        s = fred.get_series("DEXUSEU").dropna()
        return float(s.iloc[-1])
    except Exception:
        return 1.0  # fallback: treat 1:1 rather than silently corrupt


def run(dry_run: bool = False, local: bool = False) -> None:
    from db import upsert_reading, log_etl_run, set_local, get_latest_date
    if local:
        set_local(True)

    fred = Fred(api_key=os.environ["FRED_API_KEY"])
    eurusd = _fetch_eurusd(fred)
    print(f"[FX] EUR/USD = {eurusd:.4f} (used to convert EA EUR values to USD)")

    # ── E1 US (FRED) ──────────────────────────────────────────────────────────
    try:
        latest = get_latest_date("E1", "US")
        start  = (date.today() - timedelta(days=730)).isoformat()
        series = fred.get_series("BOPGSTB", observation_start=start).dropna()
        rows   = [(ts.date(), round(float(v), 4)) for ts, v in series.items()
                  if not math.isnan(float(v))]
        new_rows = [(d, v) for d, v in rows if latest is None or d > latest]
        for reading_date, value in new_rows:
            if dry_run:
                print(f"  E1/US  {reading_date}  {value:.4f}  [BOPGSTB]")
            else:
                upsert_reading("E1", "US", value, reading_date, SOURCE_FRED, "BOPGSTB")
        if not dry_run:
            log_etl_run(SOURCE_FRED, "E1", "US", "success", rows_written=len(new_rows))
        print(f"[FRED] E1/US — {len(new_rows)} new rows (skipped {len(rows)-len(new_rows)}) {'(dry run)' if dry_run else 'written'}")
    except Exception as exc:
        if not dry_run:
            log_etl_run(SOURCE_FRED, "E1", "US", "failed", error_message=str(exc))
        print(f"[FRED] ERROR E1/US: {exc}")

    # ── E1 non-US (Trading Economics) ─────────────────────────────────────────
    for country_id, cfg in E1_TE.items():
        source = SOURCE_CBSL if country_id == "SL" else SOURCE_TE
        try:
            latest = get_latest_date("E1", country_id)
            result = _fetch_te("E1", country_id, cfg)
            if result is None:
                print(f"[TE] E1/{country_id} — no data parsed")
                if not dry_run:
                    log_etl_run(source, "E1", country_id, "stale", error_message="No data parsed")
                continue
            value, ref_date = result
            # EA trade balance is reported in EUR bn — convert to USD bn
            if country_id == "EA":
                value = round(value * eurusd, 4)
            if latest is not None and ref_date <= latest:
                print(f"[TE] E1/{country_id} — already up to date (latest: {latest})")
                continue
            if dry_run:
                print(f"  E1/{country_id}  {ref_date}  {value:.4f}  [{cfg['url']}]")
            else:
                upsert_reading("E1", country_id, value, ref_date, source, cfg["url"])
                log_etl_run(source, "E1", country_id, "success", rows_written=1)
            print(f"[TE] E1/{country_id} — {value} on {ref_date} {'(dry run)' if dry_run else 'written'}")
        except Exception as exc:
            if not dry_run:
                log_etl_run(source, "E1", country_id, "failed", error_message=str(exc))
            print(f"[TE] ERROR E1/{country_id}: {exc}")

    # ── E2 US (Trading Economics) ─────────────────────────────────────────────
    try:
        latest = get_latest_date("E2", "US")
        result = _fetch_te_multi(E2_US["url"], E2_US["unit_filter"], E2_US["unit_row"], E2_US["scale"])
        if result is None:
            print("[TE] E2/US — no data parsed")
            if not dry_run:
                log_etl_run(SOURCE_TE, "E2", "US", "stale", error_message="No data parsed")
        else:
            value, ref_date = result
            if latest is not None and ref_date <= latest:
                print(f"[TE] E2/US — already up to date (latest: {latest})")
            else:
                if dry_run:
                    print(f"  E2/US  {ref_date}  {value:.4f}  [{E2_US['url']}]")
                else:
                    upsert_reading("E2", "US", value, ref_date, SOURCE_TE, E2_US["url"])
                    log_etl_run(SOURCE_TE, "E2", "US", "success", rows_written=1)
                print(f"[TE] E2/US — {value} on {ref_date} {'(dry run)' if dry_run else 'written'}")
    except Exception as exc:
        if not dry_run:
            log_etl_run(SOURCE_TE, "E2", "US", "failed", error_message=str(exc))
        print(f"[TE] ERROR E2/US: {exc}")

    # ── E2 non-US (Trading Economics / CBSL) ──────────────────────────────────
    for country_id, cfg in E2_TE.items():
        source = SOURCE_CBSL if country_id == "SL" else SOURCE_TE
        try:
            latest = get_latest_date("E2", country_id)
            result = _fetch_te("E2", country_id, cfg)
            if result is None:
                print(f"[TE] E2/{country_id} — no data parsed")
                if not dry_run:
                    log_etl_run(source, "E2", country_id, "stale", error_message="No data parsed")
                continue
            value, ref_date = result
            if latest is not None and ref_date <= latest:
                print(f"[TE] E2/{country_id} — already up to date (latest: {latest})")
                continue
            if dry_run:
                print(f"  E2/{country_id}  {ref_date}  {value:.4f}  [{cfg['url']}]")
            else:
                upsert_reading("E2", country_id, value, ref_date, source, cfg["url"])
                log_etl_run(source, "E2", country_id, "success", rows_written=1)
            print(f"[TE] E2/{country_id} — {value} on {ref_date} {'(dry run)' if dry_run else 'written'}")
        except Exception as exc:
            if not dry_run:
                log_etl_run(source, "E2", country_id, "failed", error_message=str(exc))
            print(f"[TE] ERROR E2/{country_id}: {exc}")


    # ── E3 (CBSL via Trading Economics — SL only) ─────────────────────────────
    for country_id, cfg in E3_TE.items():
        try:
            latest = get_latest_date("E3", country_id)
            result = _fetch_te("E3", country_id, cfg)
            if result is None:
                print(f"[CBSL] E3/{country_id} — no data parsed")
                if not dry_run:
                    log_etl_run(SOURCE_CBSL, "E3", country_id, "stale",
                                error_message="No data parsed")
                continue
            value, ref_date = result
            if latest is not None and ref_date <= latest:
                print(f"[CBSL] E3/{country_id} — already up to date (latest: {latest})")
                continue
            if dry_run:
                print(f"  E3/{country_id}  {ref_date}  {value:.4f}  [{cfg['url']}]")
            else:
                upsert_reading("E3", country_id, value, ref_date, SOURCE_CBSL, cfg["url"])
                log_etl_run(SOURCE_CBSL, "E3", country_id, "success", rows_written=1)
            print(f"[CBSL] E3/{country_id} — {value} on {ref_date} {'(dry run)' if dry_run else 'written'}")
        except Exception as exc:
            if not dry_run:
                log_etl_run(SOURCE_CBSL, "E3", country_id, "failed", error_message=str(exc))
            print(f"[CBSL] ERROR E3/{country_id}: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--local",   action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run, local=args.local)
