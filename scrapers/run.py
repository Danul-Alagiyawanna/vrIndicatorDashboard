"""
Main runner — executes scrapers organised by indicator category.

Usage:
  python run.py                          # run all scrapers (writes to Supabase)
  python run.py --dry-run               # print fetched values, skip Supabase
  python run.py --source growth         # run one category only
  python run.py --source financial --dry-run
  python run.py --schedule              # start the recurring scheduler

Categories (map to indicator IDs):
  growth      G1 GDP, G2/G3 PMI (stub), G4 Industrial Production
  inflation   I1 Headline CPI, I2 Core CPI, I3 Food Inflation
  monetary    M1 Policy Rate, M2 10Y Yield, M3 Yield Curve
  labour      L1 Unemployment, L2 Wage Growth
  financial   F1 Equity, F2 FX, F3 Credit Spreads
  external    E1 Trade Balance, E2 FX Reserves, E3 Remittances
  commodities C1 Brent Crude

Schedules:
  Daily    06:00 UTC  financial   (equity, FX)
  Daily    06:00 UTC  commodities (Brent)
  Weekly   Mon 06:30  monetary    (bond yields, yield curve)
  Monthly  1st 07:00  growth, inflation, labour, external
"""

import argparse
import sys
import os
import importlib.util

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sources"))

SOURCES = ["growth", "inflation", "monetary", "labour", "financial", "external", "commodities"]


def _load(name: str):
    path = os.path.join(os.path.dirname(__file__), "sources", f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_all(dry_run: bool = False) -> None:
    label = " (DRY RUN — no data written to Supabase)" if dry_run else ""
    print(f"=== Running all scrapers{label} ===")
    for name in SOURCES:
        print(f"\n--- {name} ---")
        _load(name).run(dry_run=dry_run)
    print("\n=== Done ===")


def run_source(name: str, dry_run: bool = False) -> None:
    if name not in SOURCES:
        print(f"Unknown source '{name}'. Choose from: {', '.join(SOURCES)}")
        sys.exit(1)
    label = " (DRY RUN)" if dry_run else ""
    print(f"=== Running {name}{label} ===")
    _load(name).run(dry_run=dry_run)
    print("=== Done ===")


def start_scheduler() -> None:
    import schedule, time, datetime

    print("Scheduler started. Press Ctrl+C to stop.")

    # Daily: financial markets + commodities
    schedule.every().day.at("06:00").do(lambda: _load("financial").run())
    schedule.every().day.at("06:05").do(lambda: _load("commodities").run())

    # Weekly Monday: monetary (bond yields, yield curve)
    schedule.every().monday.at("06:30").do(lambda: _load("monetary").run())

    # Monthly 1st: macro categories
    def _monthly():
        if datetime.date.today().day == 1:
            for name in ["growth", "inflation", "labour", "external"]:
                _load(name).run()

    schedule.every().day.at("07:00").do(_monthly)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indicator dashboard scraper runner")
    parser.add_argument("--schedule", action="store_true", help="Run on a recurring schedule")
    parser.add_argument("--source",   type=str, choices=SOURCES, help="Run a single category only")
    parser.add_argument("--dry-run",  action="store_true", help="Print fetched data without writing")
    args = parser.parse_args()

    if args.source:
        run_source(args.source, dry_run=args.dry_run)
    elif args.schedule:
        start_scheduler()
    else:
        run_all(dry_run=args.dry_run)
