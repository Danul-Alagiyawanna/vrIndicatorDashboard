"""Writer shared by all scrapers — Supabase (default) or local CSV (--local)."""

import os
import csv
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"

LOCAL = False


def set_local(enabled: bool) -> None:
    global LOCAL
    LOCAL = enabled
    if enabled:
        DATA_DIR.mkdir(exist_ok=True)


# ── Local CSV writer ──────────────────────────────────────────────────────────

COLUMNS = ["indicator_id", "country_id", "date", "value", "source", "source_series_id", "ingested_at", "notes"]


def _write_csv(row: dict) -> None:
    # One CSV per indicator (global indicators use country_id "GLOBAL")
    label = row["country_id"] or "GLOBAL"
    path = DATA_DIR / f"{row['indicator_id']}_{label}.csv"
    file_exists = path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({col: row.get(col, "") for col in COLUMNS})


# ── Supabase writer ───────────────────────────────────────────────────────────

_client = None


def get_client():
    global _client
    if _client is None:
        from supabase import create_client
        _client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    return _client


# ── Public API ────────────────────────────────────────────────────────────────

def get_latest_date(indicator_id: str, country_id: Optional[str]) -> Optional[date]:
    """Return the most recent date already stored for this indicator/country, or None."""
    if LOCAL:
        return None  # CSV mode: always fetch everything
    try:
        query = (
            get_client()
            .table("readings")
            .select("date")
            .eq("indicator_id", indicator_id)
            .order("date", desc=True)
            .limit(1)
        )
        if country_id is None:
            query = query.is_("country_id", "null")
        else:
            query = query.eq("country_id", country_id)
        result = query.execute()
        if result.data:
            return date.fromisoformat(result.data[0]["date"])
    except Exception:
        pass
    return None


def upsert_reading(
    indicator_id: str,
    country_id: Optional[str],       # None for global series (C1 Brent)
    value: float,
    reading_date: date,
    source: str,
    source_series_id: str,
    notes: Optional[str] = None,
) -> None:
    row = {
        "indicator_id":     indicator_id,
        "country_id":       country_id,   # None serialises to SQL NULL via supabase-py
        "value":            value,
        "date":             reading_date.isoformat(),
        "source":           source,
        "source_series_id": source_series_id,
        "ingested_at":      datetime.utcnow().isoformat(),
        "notes":            notes or None,
    }
    if LOCAL:
        _write_csv(row)
    else:
        get_client().table("readings").upsert(
            row, on_conflict="indicator_id,country_id,date"
        ).execute()


def log_etl_run(
    source: str,
    indicator_id: str,
    country_id: Optional[str],
    status: str,
    rows_written: int = 0,
    error_message: Optional[str] = None,
) -> None:
    if LOCAL:
        if error_message:
            print(f"  [etl_log] {source} {indicator_id}/{country_id} {status}: {error_message}")
        return
    get_client().table("etl_runs").insert({
        "run_at":         datetime.utcnow().isoformat(),
        "source":         source,
        "indicator_id":   indicator_id,
        "country_id":     country_id,
        "status":         status,
        "rows_written":   rows_written,
        "error_message":  error_message,
    }).execute()
