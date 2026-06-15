# Product Requirements Document
## Global Economic Indicator Database — VR Investments Dashboard

**Version:** 1.0
**Date:** 2026-06-09
**Owner:** VR Investments

---

## 1. Overview

A Supabase-hosted PostgreSQL database that ingests, stores, and serves economic indicator data across 6 economies (US, Euro Area, Singapore, China, India, Sri Lanka) for use in an investment monitoring dashboard. The database feeds a front-end RAG (Red/Amber/Green) status dashboard updated on automated schedules.

---

## 2. Goals

- Store all 22 indicators across 7 categories (Growth, Inflation, Monetary Policy, Labour, Financial Markets, External Sector, Commodities) for 6 countries
- Automate data ingestion from free public APIs (FRED, yfinance, World Bank, CBSL)
- Enable RAG status computation per indicator per country
- Support historical trend analysis (minimum 5 years lookback)
- Serve data to the dashboard via Supabase's REST/realtime API

---

## 3. Out of Scope

- Paid data sources (Bloomberg, Refinitiv, S&P Global PMI API)
- User authentication / multi-tenant access
- Forecasting or predictive analytics
- Real-time streaming (sub-daily refresh)

---

## 4. Data Model

### 4.1 Core Tables

#### `countries`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `text` PK | e.g. `US`, `EA`, `SG`, `CN`, `IN`, `SL` |
| `name` | `text` | Full name |
| `classification` | `text` | `DM` or `EM` |

#### `indicators`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `text` PK | e.g. `G1`, `G2`, `I1`, `M1` |
| `category` | `text` | `Growth`, `Inflation`, `Monetary Policy`, `Labour Market`, `Financial Markets`, `External Sector`, `Commodities` |
| `name` | `text` | e.g. `GDP Growth (YoY %)` |
| `description` | `text` | Full description |
| `unit` | `text` | `% YoY`, `Index`, `bps`, `USD bn`, etc. |
| `frequency` | `text` | `Daily`, `Weekly`, `Monthly`, `Quarterly` |

#### `indicator_readings`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `uuid` PK | Auto-generated |
| `indicator_id` | `text` FK → `indicators.id` | |
| `country_id` | `text` FK → `countries.id` | |
| `value` | `numeric` | The actual reading |
| `date` | `date` | Reference date of the reading |
| `rag_status` | `text` | `green`, `amber`, `red` |
| `source` | `text` | e.g. `FRED`, `yfinance`, `World Bank`, `CBSL`, `manual` |
| `source_series_id` | `text` | e.g. `DCOILBRENTEU`, `^GSPC` |
| `ingested_at` | `timestamptz` | ETL run timestamp |
| `notes` | `text` | Optional override notes |

#### `rag_rules`
| Column | Type | Description |
|--------|------|-------------|
| `indicator_id` | `text` FK | |
| `country_classification` | `text` | `DM`, `EM`, or `ALL` |
| `green_condition` | `text` | Human-readable rule, e.g. `>2.5` |
| `amber_condition` | `text` | |
| `red_condition` | `text` | |
| `green_threshold_low` | `numeric` | For programmatic evaluation |
| `green_threshold_high` | `numeric` | |
| `amber_threshold_low` | `numeric` | |
| `amber_threshold_high` | `numeric` | |

#### `etl_runs`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `uuid` PK | |
| `run_at` | `timestamptz` | |
| `source` | `text` | Which API was called |
| `indicator_id` | `text` | |
| `country_id` | `text` | |
| `status` | `text` | `success`, `failed`, `stale` |
| `error_message` | `text` | Null on success |
| `rows_written` | `integer` | |

---

## 5. Indicator Reference

### 5.1 Full Indicator List

| ID | Category | Name | Unit | Frequency |
|----|----------|------|------|-----------|
| G1 | Growth | GDP Growth (YoY %) | % YoY | Quarterly |
| G2 | Growth | Manufacturing PMI | Index | Monthly |
| G3 | Growth | Services PMI | Index | Monthly |
| G4 | Growth | Industrial Production (YoY %) | % YoY | Monthly |
| I1 | Inflation | Headline CPI (YoY %) | % YoY | Monthly |
| I2 | Inflation | Core CPI (YoY %) | % YoY | Monthly |
| I3 | Inflation | Food Inflation (YoY %) | % YoY | Monthly |
| M1 | Monetary Policy | Policy Rate (%) | % | As changed |
| M2 | Monetary Policy | 10Y Government Bond Yield (%) | % | Daily/Weekly |
| M3 | Monetary Policy | Yield Curve Slope (10Y − 2Y, bps) | bps | Weekly |
| L1 | Labour Market | Unemployment Rate (%) | % | Monthly |
| L2 | Labour Market | Wage Growth (YoY %) | % YoY | Monthly |
| F1 | Financial Markets | Equity Index (WoW % change) | % WoW | Weekly |
| F2 | Financial Markets | FX vs USD (WoW % change) | % WoW | Weekly |
| F3 | Financial Markets | Credit Spreads / Risk Sentiment | bps | Weekly |
| E1 | External Sector | Trade Balance (USD bn) | USD bn | Monthly |
| E2 | External Sector | FX Reserves (USD bn) | USD bn | Monthly |
| E3 | External Sector | Remittances (USD mn) | USD mn | Monthly |
| C1 | Commodities | Brent Crude Oil (USD/bbl) | USD/bbl | Weekly |

### 5.2 Country Coverage

| ID | Country | Classification |
|----|---------|----------------|
| US | United States | DM |
| EA | Euro Area | DM |
| SG | Singapore | DM |
| CN | China | EM |
| IN | India | EM |
| SL | Sri Lanka | EM |

### 5.3 RAG Thresholds

| ID | Green | Amber | Red |
|----|-------|-------|-----|
| G1 | >2.5% (DM); >5% (EM) | 1–2.5% (DM); 3–5% (EM) | <1% (DM); <3% (EM) or negative |
| G2 | >52 and improving MoM | 50–52 or stable | <50 (contraction) |
| G3 | >52 and improving MoM | 50–52 or stable | <50 (contraction) |
| G4 | >3% YoY | 0–3% YoY | <0% YoY |
| I1 | Within 0.5pp of CB target | 0.5–2pp above/below target | >2pp above target or deflationary |
| I2 | Within 0.5pp of CB target | 0.5–2pp above target | >2pp above target or <0% |
| I3 | <5% YoY | 5–10% YoY | >10% YoY |
| M1 | Rate on hold or cutting cycle | Hiking pause; uncertain direction | Active hiking or emergency cut |
| M2 | Stable or declining WoW | Rising but <20bps WoW | >20bps rise WoW or inversion |
| M3 | >50bps (normal/steep) | 0–50bps (flat) | <0bps (inverted) |
| L1 | Falling or near structural low | Rising but <1pp above cycle low | Rising rapidly or >1pp above cycle low |
| L2 | 2–4% (real positive growth) | >4% (wage-price spiral risk) | <2% or negative real wages |
| F1 | >+1% WoW or positive YTD | -1% to +1% WoW | <-1% WoW or down >10% YTD |
| F2 | Stable or appreciating | -1% to 0% WoW depreciation | >1% depreciation WoW |
| F3 | Tightening or <300bps | 300–600bps or widening moderately | >600bps or widening rapidly |
| E1 | Surplus or improving deficit | Deficit stable / modest widening | Rapidly widening deficit |
| E2 | >3 months import cover; rising | 2–3 months import cover; stable | <2 months import cover or declining |
| E3 | Rising YoY or >$500mn/month (SL) | Flat YoY | Declining YoY or sharp drop |
| C1 | <$80/bbl or declining WoW | $80–$100/bbl | >$100/bbl or spiking |

---

## 6. ETL Data Sources

| Source | Indicators Covered | Frequency | API Key Required |
|--------|--------------------|-----------|-----------------|
| **FRED API** | G1(US), G4, I1, I2, M1(US), M2(US), M3(US), L1(US), L2(US), E1(US), C1 | Daily/Monthly | Free key at fred.stlouisfed.org |
| **yfinance** | F1 (all equity indices), F2 (all FX pairs), C1 (Brent `BZ=F`) | Daily/Weekly | None |
| **World Bank API** | G1 (non-US GDP), L1 (non-US unemployment) | Quarterly | None |
| **CBSL API/Scrape** | E2, E3, M1(SL), I1(SL), I3(SL) | Monthly | None |
| **IMF IFS** | G4, E2 (reserves, multi-country) | Monthly | None |
| **Manual Entry** | G2, G3 (PMI — all countries) | Monthly | N/A |

### 6.1 Key Series IDs

| Indicator | Country | Source | Series ID / Ticker |
|-----------|---------|--------|--------------------|
| G1 | US | FRED | `GDP` |
| G1 | All others | World Bank | `NY.GDP.MKTP.KD.ZG` |
| I1 | US | FRED | `CPIAUCSL` |
| I2 | US | FRED | `CPILFESL` |
| M2 | US | FRED | `DGS10` |
| M3 | US | FRED | `T10Y2Y` |
| L1 | US | FRED | `UNRATE` |
| L2 | US | FRED | `CES0500000003` |
| C1 | Global | FRED | `DCOILBRENTEU` |
| F1 | US | yfinance | `^GSPC` |
| F1 | EA | yfinance | `^STOXX50E` |
| F1 | SG | yfinance | `^STI` |
| F1 | CN | yfinance | `000001.SS` |
| F1 | IN | yfinance | `^BSESN` |
| F1 | SL | yfinance | `CSE.N0000` |
| F2 | EA | yfinance | `EURUSD=X` |
| F2 | SG | yfinance | `USDSGD=X` |
| F2 | CN | yfinance | `USDCNY=X` |
| F2 | IN | yfinance | `USDINR=X` |
| F2 | SL | yfinance | `USDLKR=X` |
| E2 | SL | CBSL | cbsl.gov.lk/statistics |
| E3 | SL | CBSL | cbsl.gov.lk/statistics |

---

## 7. RAG Logic Implementation

RAG status is computed at ingestion time using the `rag_rules` table and stored directly on `indicator_readings`. Rules vary by:

- **DM vs EM classification** — e.g. GDP Green is `>2.5%` for DM, `>5%` for EM
- **Direction of change** — Some indicators (PMI, bond yields) use WoW delta, not absolute level
- **Country-specific targets** — CPI targets differ per central bank (US 2%, ECB 2%, RBI 4%, CBSL 5%)

A `rag_compute` function (PostgreSQL or Python) applies these rules each time a reading is inserted.

---

## 8. Refresh Schedule

| Frequency | Indicators | Method |
|-----------|-----------|--------|
| Daily | F1 (equity), F2 (FX), C1 (Brent) | GitHub Actions cron → yfinance → Supabase |
| Weekly | M2 (10Y yields), M3 (yield curve), F3 (EMBI) | GitHub Actions cron → FRED → Supabase |
| Monthly | I1, I2, I3, M1, L1, L2, E1, E2, E3, G4 | GitHub Actions cron → FRED/World Bank/CBSL |
| Quarterly | G1 (GDP) | GitHub Actions cron → FRED/World Bank |
| Manual | G2, G3 (PMI) | Admin UI or direct Supabase table insert |

---

## 9. API / Access Layer

- **Primary:** Supabase auto-generated REST API on `indicator_readings`
- **Dashboard queries:** Supabase client (JS/Python) fetches latest reading per `(indicator_id, country_id)` plus trailing N periods for sparklines
- **Key view:** `latest_readings` — a PostgreSQL view returning the most recent reading per indicator/country pair with RAG status

```sql
CREATE VIEW latest_readings AS
SELECT DISTINCT ON (indicator_id, country_id)
  indicator_id, country_id, value, date, rag_status, source
FROM indicator_readings
ORDER BY indicator_id, country_id, date DESC;
```

---

## 10. Data Quality Requirements

- No duplicate readings for the same `(indicator_id, country_id, date)` — enforced via unique constraint
- Stale data alert if a reading is older than `2 × frequency` (e.g., monthly data not updated in 60 days)
- `etl_runs` table tracks all failures for monitoring
- Manual PMI entries require `source = 'manual'` flag and optional `notes` field

---

## 11. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Database size | < 1 GB for 5 years of history across all indicators |
| Query latency | < 200ms for latest readings dashboard query |
| Uptime | Supabase free tier (99.9% SLA) |
| Data retention | 10 years minimum |
| ETL failure alerting | Email/Slack via GitHub Actions on failed runs |

---

## 12. Milestones

| Phase | Deliverable | Target |
|-------|-------------|--------|
| 1 | Schema deployed to Supabase, seed data for all 6 countries + 22 indicators | Week 1 |
| 2 | FRED + yfinance ETL scripts running on GitHub Actions | Week 2 |
| 3 | World Bank + CBSL ETL, manual PMI entry workflow | Week 3 |
| 4 | RAG compute logic + `latest_readings` view | Week 3 |
| 5 | Dashboard front-end connected to Supabase API | Week 4 |
| 6 | ETL monitoring + alerting | Week 4 |

---

## 13. Open Questions

1. Should PMI data entry have a simple admin UI, or is direct Supabase table editor sufficient?
2. Is a Sri Lanka CDS proxy (EMBI) acceptable for F3, or should that cell show `N/A`?
3. What is the target front-end framework for the dashboard (React, Next.js, other)?
4. Should historical backfill cover 5 years or 10 years at launch?
