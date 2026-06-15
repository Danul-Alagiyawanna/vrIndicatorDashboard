# Database Schema
## VR Investments — Global Macro Indicator Database

**Version:** 2.0
**Date:** 2026-06-12

---

## Design Principles

This database is a **shared, multi-use economic data store**, not a dashboard-specific store. The RAG dashboard is the first consumer, but others will follow (reports, models, internal APIs). Three principles follow from that:

1. **Raw readings are the single source of truth.** Every indicator value — market or macro, daily or quarterly — lives in one canonical `readings` table. No consumer-specific interpretation (like RAG colour) is baked into it.
2. **Derived data is derived, never duplicated as a second source.** The dashboard's weekly heatmap data (Friday close, WoW %, prior value) is a *view* over `readings`, so it can never drift from the canonical values.
3. **Consumer logic lives in consumer-owned tables/views.** RAG thresholds and evaluations are optional, dashboard-owned, and reference readings — they do not modify them.

---

## Overview

| Table / View | Kind | Purpose |
|--------------|------|---------|
| `countries` | table | Reference — 6 economies tracked |
| `indicators` | table | Reference — 19 indicators tracked |
| `readings` | table | **Canonical** — one row per indicator/country/date. All indicators, all frequencies. |
| `etl_runs` | table | ETL audit — one row per scraper run |
| `rag_rules` | table | *(optional, dashboard-owned)* RAG thresholds per indicator |
| `weekly_market` | view | Derived — Friday close + WoW % for F1/F2/C1 (heatmap) |
| `latest_readings` | view | Derived — most recent reading per indicator/country |
| `rag_evaluations` | view | *(optional, dashboard-owned)* RAG colour per latest reading |

**What changed from v1.1**
- `daily_readings` + `weekly_readings` + `indicator_readings` → collapsed into one `readings` table. Market data is no longer split across two parallel source tables.
- Weekly WoW data is now the `weekly_market` **view**, derived from `readings`, so it cannot disagree with the underlying closes.
- RAG (`rag_rules`, `rag_evaluations`) is reintroduced from the PRD but kept **out** of the readings table — it is optional and consumer-owned.
- `is_global` boolean replaced by nullable `country_id` (a global series = `NULL` country).
- Reference tables gain `created_at` / `updated_at` and an `active` flag for long-lived governance.
- `frequency` is now an enum-checked value with a companion `period_days` for the stale-data alert.
- Indicator count reconciled: **19 indicators** (PRD's "22" was stale — corrected there too).

---

## Entity Relationship Diagram

```
countries (id) ◄──────┐         ┌──────► indicators (id)
                      │         │
                  country_id  indicator_id
                      │         │
                      ▼         ▼
                      readings  (canonical — every value)
                          ▲
                          │ (read-only)
            ┌─────────────┼──────────────┐
            │             │              │
    weekly_market   latest_readings   rag_evaluations
       (view)           (view)        (view, uses rag_rules)
```

`country_id` is **nullable** in `readings` for global series (Brent). `etl_runs` has no FKs by design — the audit log must survive reference-data edits.

---

## Table 1: `countries`

Reference table. Slow-changing.

```sql
CREATE TABLE countries (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    region         TEXT NOT NULL,
    classification TEXT NOT NULL CHECK (classification IN ('DM', 'EM')),
    active         BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Seed Data

| id | name | region | classification |
|----|------|--------|----------------|
| US | United States | North America | DM |
| EA | Euro Area | Europe | DM |
| SG | Singapore | Asia | DM |
| CN | China | Asia | EM |
| IN | India | South Asia | EM |
| SL | Sri Lanka | South Asia | EM |

> `classification` (DM/EM) can change over time. When it does, update the row and record the change in your application/ETL log — historical `readings` are unaffected because they reference `country_id`, not classification.

---

## Table 2: `indicators`

Reference table. Slow-changing.

```sql
CREATE TABLE indicators (
    id          TEXT PRIMARY KEY,
    category    TEXT NOT NULL,
    name        TEXT NOT NULL,
    description TEXT,
    unit        TEXT NOT NULL,
    frequency   TEXT NOT NULL CHECK (frequency IN
                    ('Daily', 'Weekly', 'Monthly', 'Quarterly', 'Per meeting')),
    period_days INTEGER NOT NULL,   -- nominal days between releases; powers the stale-data alert
    is_global   BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE => readings carry country_id = NULL
    active      BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

- **`period_days`** — nominal cadence. Stale alert fires when `now() - max(date) > 2 * period_days`. (Daily=1, Weekly=7, Monthly=31, Quarterly=92, Per meeting=45.)
- **`is_global`** — `TRUE` for C1 (Brent). A global indicator's `readings` rows use `country_id = NULL`; consumers fan it out to all countries at read time.

### Seed Data

| id | category | name | unit | frequency | period_days | is_global |
|----|----------|------|------|-----------|-------------|-----------|
| G1 | Growth | GDP Growth (YoY %) | % YoY | Quarterly | 92 | false |
| G2 | Growth | Manufacturing PMI | Index | Monthly | 31 | false |
| G3 | Growth | Services PMI | Index | Monthly | 31 | false |
| G4 | Growth | Industrial Production (YoY %) | % YoY | Monthly | 31 | false |
| I1 | Inflation | Headline CPI (YoY %) | % YoY | Monthly | 31 | false |
| I2 | Inflation | Core CPI (YoY %) | % YoY | Monthly | 31 | false |
| I3 | Inflation | Food Inflation (YoY %) | % YoY | Monthly | 31 | false |
| M1 | Monetary Policy | Policy Rate (%) | % | Per meeting | 45 | false |
| M2 | Monetary Policy | 10Y Bond Yield (%) | % | Weekly | 7 | false |
| M3 | Monetary Policy | Yield Curve (10Y-2Y, bps) | bps | Weekly | 7 | false |
| L1 | Labour Market | Unemployment Rate (%) | % | Monthly | 31 | false |
| L2 | Labour Market | Wage Growth (YoY %) | % YoY | Monthly | 31 | false |
| F1 | Financial Markets | Equity Index | Index | Weekly | 7 | false |
| F2 | Financial Markets | FX vs USD | Rate | Weekly | 7 | false |
| F3 | Financial Markets | Credit Spreads (bps) | bps | Weekly | 7 | false |
| E1 | External Sector | Trade Balance (USD bn) | USD bn | Monthly | 31 | false |
| E2 | External Sector | FX Reserves (USD bn) | USD bn | Monthly | 31 | false |
| E3 | External Sector | Remittances (USD mn) | USD mn | Monthly | 31 | false |
| C1 | Commodities | Brent Crude (USD/bbl) | USD/bbl | Weekly | 7 | true |

---

## Table 3: `readings` — canonical source of truth

One row per `(indicator_id, country_id, date)`. **Every** indicator value lives here — market and macro, daily and quarterly. There is no separate market-data table.

```sql
CREATE TABLE readings (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    indicator_id      TEXT        NOT NULL REFERENCES indicators(id),
    country_id        TEXT                 REFERENCES countries(id),  -- NULL for global series
    date              DATE        NOT NULL,
    value             NUMERIC     NOT NULL,
    source            TEXT        NOT NULL,   -- 'FRED' | 'yfinance' | 'World Bank' | 'CBSL' | 'manual'
    source_series_id  TEXT,                   -- ticker / FRED id / WB code / URL
    notes             TEXT,                   -- manual override notes
    ingested_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),  -- refreshed on every upsert via trigger

    -- enforce uniqueness even when country_id is NULL (global series)
    UNIQUE NULLS NOT DISTINCT (indicator_id, country_id, date)
);

CREATE INDEX idx_readings_indicator_country ON readings (indicator_id, country_id);
CREATE INDEX idx_readings_indicator_date    ON readings (indicator_id, date DESC);
CREATE INDEX idx_readings_date              ON readings (date DESC);
CREATE INDEX idx_readings_updated_at        ON readings (updated_at DESC);  -- for new-data banner

-- Auto-update updated_at on every upsert
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$;

CREATE TRIGGER readings_updated_at
BEFORE INSERT OR UPDATE ON readings
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

> `UNIQUE NULLS NOT DISTINCT` (Postgres 15+, available on Supabase) treats two `NULL` country_ids as equal, so a global series still gets one row per date. On older engines, use a partial unique index pair instead.

### Column Reference

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| `indicator_id` | text | `F1` | FK to indicators |
| `country_id` | text | `US` / `NULL` | FK to countries; NULL for global (Brent) |
| `date` | date | `2026-06-12` | Reference/close date of the reading |
| `value` | numeric | `7405.73` | Raw value in the indicator's `unit`. Always join `indicators.unit` to interpret. |
| `source` | text | `yfinance` | Data provider |
| `source_series_id` | text | `^GSPC` | Ticker / series id / code / URL |
| `notes` | text | `null` | Manual override notes |
| `ingested_at` | timestamptz | `2026-06-09T08:01:45` | ETL run timestamp |

**Interpretation contract:** `value` is dimensionless on its own. A consumer must join `indicators.unit` to know whether a number is a percent, a bps figure, an index level, or USD. F2 stores the **raw** FX rate (e.g. `USDLKR=X`), not a WoW %; sign conventions for WoW are handled in `weekly_market` below.

### Coverage (first load, ~2yr backfill)

| Indicator group | Grain | Rows |
|-----------------|-------|------|
| F1, F2 (5 ctry each), C1 (global) | daily | ~8,500 |
| All macro indicators | monthly/quarterly | ~500–800 |

---

## Table 4: `etl_runs`

Tracks every scraper run for monitoring and failure diagnosis. **No FKs** — the audit log must survive reference-data edits.

```sql
CREATE TABLE etl_runs (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    source        TEXT        NOT NULL,
    indicator_id  TEXT,
    country_id    TEXT,
    status        TEXT        NOT NULL CHECK (status IN ('success', 'failed', 'stale')),
    rows_written  INTEGER     DEFAULT 0,
    error_message TEXT
);

CREATE INDEX idx_etl_run_at ON etl_runs (run_at DESC);
```

---

## Table 5: `rag_rules` *(optional — dashboard-owned)*

RAG thresholds per indicator. This is **consumer logic**, not economic data. It references indicators but never modifies `readings`. Drop this table (and the `rag_evaluations` view) entirely if a future consumer does not want RAG — the core data is unaffected.

```sql
CREATE TABLE rag_rules (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    indicator_id           TEXT NOT NULL REFERENCES indicators(id),
    country_classification TEXT NOT NULL CHECK (country_classification IN ('DM', 'EM', 'ALL')),
    -- human-readable, for display
    green_condition        TEXT,
    amber_condition        TEXT,
    red_condition          TEXT,
    -- machine-evaluable thresholds (interpretation depends on indicator)
    green_threshold_low    NUMERIC,
    green_threshold_high   NUMERIC,
    amber_threshold_low    NUMERIC,
    amber_threshold_high   NUMERIC,

    UNIQUE (indicator_id, country_classification)
);
```

> Some indicators are RAG-scored on a **delta** (WoW change, direction) rather than an absolute level — e.g. PMI "improving MoM", bond yields ">20bps rise WoW". Those rules can't be expressed purely as static thresholds; the dashboard's `rag_compute` function consults `weekly_market` / trailing readings for them. Keep thresholds here for the level-based indicators and document the delta-based ones in the compute function.

---

## View 1: `weekly_market` — derived heatmap data

Friday close + prior Friday close + WoW % for the market indicators (F1, F2, C1), **computed from `readings`**. This replaces the old `weekly_readings` table — it is now derived, so it can never drift from the underlying closes.

```sql
CREATE VIEW weekly_market AS
WITH fridays AS (
    SELECT
        r.indicator_id,
        r.country_id,
        -- snap each reading to the Friday of its ISO week
        (r.date + (5 - EXTRACT(ISODOW FROM r.date))::int) AS week_ending,
        r.date,
        r.value,
        r.source_series_id,
        ROW_NUMBER() OVER (
            PARTITION BY r.indicator_id, r.country_id,
                         (r.date + (5 - EXTRACT(ISODOW FROM r.date))::int)
            ORDER BY r.date DESC
        ) AS rn          -- last actual reading on/before that Friday
    FROM readings r
    WHERE r.indicator_id IN ('F1', 'F2', 'C1')
),
weekly AS (
    SELECT indicator_id, country_id, week_ending, value, source_series_id
    FROM fridays
    WHERE rn = 1
)
SELECT
    w.indicator_id,
    w.country_id,
    w.week_ending,
    w.value,
    LAG(w.value) OVER win                                    AS prior_value,
    ROUND( (w.value / NULLIF(LAG(w.value) OVER win, 0) - 1) * 100, 4) AS wow_pct,
    w.source_series_id
FROM weekly w
WINDOW win AS (PARTITION BY w.indicator_id, w.country_id ORDER BY w.week_ending);
```

### WoW % sign convention for F2 (FX)

The view stores the **raw** WoW % of the stored rate. For `USDxxx=X` pairs, a *falling* rate means the local currency *appreciated*, so the dashboard must flip the sign at read time (or wrap this view with a CASE on `country_id`).

| Ticker | Quote | Raw wow_pct positive means | Dashboard should show |
|--------|-------|----------------------------|-----------------------|
| `DX-Y.NYB` | USD index | USD strengthening | as-is |
| `EURUSD=X` | EUR per USD | EUR strengthening | as-is |
| `USDSGD=X` | SGD per USD | USD strengthening | **flip** → SGD appreciation |
| `USDCNY=X` | CNY per USD | USD strengthening | **flip** → CNY appreciation |
| `USDINR=X` | INR per USD | USD strengthening | **flip** → INR appreciation |
| `USDLKR=X` | LKR per USD | USD strengthening | **flip** → LKR appreciation |

---

## View 2: `latest_readings` — most recent value per indicator/country

```sql
CREATE VIEW latest_readings AS
SELECT DISTINCT ON (r.indicator_id, r.country_id)
    r.indicator_id,
    i.name          AS indicator_name,
    i.category,
    i.unit,
    i.frequency,
    r.country_id,
    c.name          AS country_name,
    c.classification,
    r.date,
    r.value,
    r.source,
    r.source_series_id
FROM readings r
JOIN indicators i ON i.id = r.indicator_id
LEFT JOIN countries c ON c.id = r.country_id   -- LEFT JOIN: global series have NULL country
ORDER BY r.indicator_id, r.country_id, r.date DESC;
```

> `DISTINCT ON` is Postgres-specific (fine for Supabase). The `LEFT JOIN` keeps global series (Brent, `country_id = NULL`) in the result.

---

## View 3: `rag_evaluations` *(optional — dashboard-owned)*

Joins the latest reading to its rule and emits a colour. Level-based indicators only; delta-based ones are handled in application code. Shown here as a sketch — adapt the threshold logic to your sign conventions.

```sql
CREATE VIEW rag_evaluations AS
SELECT
    lr.indicator_id,
    lr.country_id,
    lr.value,
    lr.date,
    CASE
        WHEN rr.green_threshold_low IS NULL THEN NULL  -- delta-based: compute in app
        WHEN lr.value >= rr.green_threshold_low
         AND (rr.green_threshold_high IS NULL OR lr.value <= rr.green_threshold_high)
             THEN 'green'
        WHEN lr.value >= rr.amber_threshold_low
         AND (rr.amber_threshold_high IS NULL OR lr.value <= rr.amber_threshold_high)
             THEN 'amber'
        ELSE 'red'
    END AS rag_status
FROM latest_readings lr
JOIN countries c ON c.id = lr.country_id
LEFT JOIN rag_rules rr
       ON rr.indicator_id = lr.indicator_id
      AND rr.country_classification IN (c.classification, 'ALL');
```

---

## Scraper → Indicator Mapping

All scrapers write to the single `readings` table.

| Scraper | Indicators | Countries |
|---------|-----------|-----------|
| yfinance | F1, F2, C1 | F1/F2: 5 each; C1: global (`country_id = NULL`) |
| FRED | G1, G4, I1, I2, I3, M1, M2, M3, L1, L2, E1, F3 | US |
| World Bank | G1, L1 | EA, SG, CN, IN, SL |
| CBSL | I1, I3, M1, E2, E3 | SL |
| Manual entry | G2, G3 | All 6 |

### Key Series IDs

| Indicator | Country | Source | Series ID / Ticker |
|-----------|---------|--------|--------------------|
| G1 | US | FRED | `GDP` |
| G1 | non-US | World Bank | `NY.GDP.MKTP.KD.ZG` |
| I1 | US | FRED | `CPIAUCSL` |
| I2 | US | FRED | `CPILFESL` |
| M2 | US | FRED | `DGS10` |
| M3 | US | FRED | `T10Y2Y` |
| L1 | US | FRED | `UNRATE` |
| L2 | US | FRED | `CES0500000003` |
| C1 | global | FRED / yfinance | `DCOILBRENTEU` / `BZ=F` |
| F1 | US/EA/SG/CN/IN | yfinance | `^GSPC` / `^STOXX50E` / `^STI` / `000001.SS` / `^BSESN` |
| F2 | EA/SG/CN/IN/SL | yfinance | `EURUSD=X` / `USDSGD=X` / `USDCNY=X` / `USDINR=X` / `USDLKR=X` |
| E2,E3 | SL | CBSL | cbsl.gov.lk/statistics |

---

## Refresh Schedule

| Scraper | Frequency |
|---------|-----------|
| yfinance (F1, F2, C1) | Daily (weekdays) |
| FRED (M2, M3, F3) | Weekly |
| FRED (I1, I2, I3, M1, L1, L2, E1, G4) | Monthly |
| FRED / World Bank (G1) | Quarterly |
| CBSL | Monthly |
| Manual (G2, G3 PMI) | Monthly |

Stale-data alert: a series is stale when `now() - max(readings.date) > 2 * indicators.period_days`.

---

## Known Data Gaps

| Indicator | Country | Reason | Workaround |
|-----------|---------|--------|------------|
| F1 | SL | `^CSE` not on yfinance | Manual entry or CBSL scraper |
| G2, G3 | All | S&P Global PMI API is paid-only | Manual entry monthly |
| F3 | non-US | Sovereign CDS not on free APIs | EMBI (FRED) proxy for US only |
| L2 | CN | No reliable free wage data | Blank — national stats only |

---

## Reusability Notes (for future consumers)

- **Read `readings` + `indicators`/`countries` to get raw data.** That's the whole contract. You never need RAG, weekly views, or dashboard tables.
- **`value` is meaningless without `unit`.** Always join `indicators.unit`.
- **Global series carry `country_id = NULL`.** Fan out at read time if your use case is per-country.
- **Never write derived/consumer state back into `readings`.** Add your own table or view (the way RAG does) and reference readings read-only.
