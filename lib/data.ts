import { supabase } from './supabase'
import type {
  LatestReading,
  WeeklyMarket,
  Reading,
  HeatmapCell,
  RagStatus,
} from '@/types/indicators'
import { COUNTRIES, COUNTRY_IDS } from '@/types/indicators'

// RAG thresholds — adopted from the VR Investments RAG framework.
// All level-based indicators use absolute thresholds (see computeRag below).
// M1 (Policy Rate), E1 (Trade Balance), E2 (FX Reserves), E3 (Remittances),
// and L2 (Wage Growth) have no clean absolute rule and remain uncoloured (null).
export function computeRag(
  indicatorId: string,
  value: number,
  classification: 'DM' | 'EM' | null,
  wowPct: number | null,
  prevValue: number | null = null,
): RagStatus {
  // ── Financial Markets (WoW %) ──────────────────────────────────────────────
  if (indicatorId === 'F1') {
    // Equity Index: >=1% green, -1% to +1% amber, <-1% red
    if (wowPct === null) return null
    if (wowPct >= 1) return 'green'
    if (wowPct >= -1) return 'amber'
    return 'red'
  }
  if (indicatorId === 'F2') {
    // FX vs USD: >=0% green, -1% to 0% amber, <-1% red
    if (wowPct === null) return null
    if (wowPct >= 0) return 'green'
    if (wowPct >= -1) return 'amber'
    return 'red'
  }
  if (indicatorId === 'F3') {
    // Credit Spreads / CDS: <=300bps green, 300-600 amber, >600 red
    if (value <= 300) return 'green'
    if (value <= 600) return 'amber'
    return 'red'
  }

  // ── Commodities ────────────────────────────────────────────────────────────
  if (indicatorId === 'C1') {
    // Brent Crude: <=80 green, 80-100 amber, >100 red
    if (value <= 80) return 'green'
    if (value <= 100) return 'amber'
    return 'red'
  }

  // ── Growth ─────────────────────────────────────────────────────────────────
  if (indicatorId === 'G1') {
    // GDP Growth: DM >=2.5/1-2.5/<1 ; EM >=5/3-5/<3
    if (classification === 'DM') {
      if (value >= 2.5) return 'green'
      if (value >= 1) return 'amber'
      return 'red'
    }
    if (value >= 5) return 'green'
    if (value >= 3) return 'amber'
    return 'red'
  }
  if (indicatorId === 'G2' || indicatorId === 'G3') {
    // PMI (Mfg / Services): >=52 green, 50-52 amber, <50 red
    if (value >= 52) return 'green'
    if (value >= 50) return 'amber'
    return 'red'
  }
  if (indicatorId === 'G4') {
    // Industrial Production YoY: >=3 green, 0-3 amber, <0 red
    if (value >= 3) return 'green'
    if (value >= 0) return 'amber'
    return 'red'
  }

  // ── Inflation ──────────────────────────────────────────────────────────────
  if (indicatorId === 'I1' || indicatorId === 'I2') {
    // Headline / Core CPI: <=4% green, 4-8% amber, >8% red
    if (value <= 4) return 'green'
    if (value <= 8) return 'amber'
    return 'red'
  }
  if (indicatorId === 'I3') {
    // Food Inflation: <=5% green, 5-10% amber, >10% red
    if (value <= 5) return 'green'
    if (value <= 10) return 'amber'
    return 'red'
  }

  // ── Monetary Policy ────────────────────────────────────────────────────────
  if (indicatorId === 'M2') {
    // 10Y Bond Yield: <=5% green, 5-7% amber, >7% red
    if (value <= 5) return 'green'
    if (value <= 7) return 'amber'
    return 'red'
  }
  if (indicatorId === 'M3') {
    // Yield Curve (10Y-2Y): >=50bps green, 0-50 amber, <0 red (inverted)
    if (value >= 50) return 'green'
    if (value >= 0) return 'amber'
    return 'red'
  }

  // ── Labour Market ──────────────────────────────────────────────────────────
  if (indicatorId === 'L1') {
    // Unemployment Rate: <=5% green, 5-7% amber, >7% red
    if (value <= 5) return 'green'
    if (value <= 7) return 'amber'
    return 'red'
  }

  // ── External Sector (trend vs prior reading) ───────────────────────────────
  // Raw USD levels aren't comparable across economies, so E1/E3 are scored on
  // direction vs the previous reading. A ±2% dead-band keeps tiny wiggles amber.
  if (indicatorId === 'E1' || indicatorId === 'E3') {
    if (prevValue === null || prevValue === 0) return null
    const pct = ((value - prevValue) / Math.abs(prevValue)) * 100
    // E1 Trade Balance: rising value = narrowing deficit / growing surplus = good.
    // E3 Remittances: rising inflows = good. Same direction logic for both.
    if (pct > 2) return 'green'
    if (pct >= -2) return 'amber'
    return 'red'
  }

  // M1 (Policy Rate), L2 (Wage Growth), E2 (FX Reserves — needs months of import
  // cover, not raw USD bn) — no usable single-value rule; remain uncoloured.
  return null
}

export function formatValue(value: number, unit: string, precise = false, currency = '$'): string {
  if (unit === '% YoY' || unit === '% WoW' || unit === '%') {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
  }
  if (unit === 'bps') {
    return `${value >= 0 ? '+' : ''}${precise ? value.toFixed(2) : Math.round(value)} bps`
  }
  if (unit === 'bn') {
    return `${currency}${value.toFixed(precise ? 3 : 1)}bn`
  }
  if (unit === 'USD bn') {
    return `$${value.toFixed(precise ? 3 : 1)}bn`
  }
  if (unit === 'USD mn') {
    return `$${precise ? value.toFixed(2) : Math.round(value)}mn`
  }
  if (unit === 'USD/bbl') {
    return `$${value.toFixed(precise ? 4 : 2)}`
  }
  if (unit === 'Index') {
    return value.toLocaleString(undefined, {
      minimumFractionDigits: precise ? 2 : 0,
      maximumFractionDigits: precise ? 2 : 0,
    })
  }
  if (unit === 'Rate') {
    return value.toFixed(precise ? 6 : 4)
  }
  return value.toFixed(precise ? 4 : 2)
}

// ── Data fetching ─────────────────────────────────────────────────────────────

export async function fetchLatestReadings(): Promise<LatestReading[]> {
  const { data, error } = await supabase
    .from('latest_readings')
    .select('*')
  if (error) throw error
  return data ?? []
}

export async function fetchWeeklyMarket(): Promise<WeeklyMarket[]> {
  const { data, error } = await supabase
    .from('weekly_market')
    .select('*')
    .order('week_ending', { ascending: false })
    .limit(500)
  if (error) throw error
  return data ?? []
}

export async function fetchSparklines(
  indicatorId: string,
  countryId: string | null,
  limit = 12,
): Promise<number[]> {
  let query = supabase
    .from('readings')
    .select('value, date')
    .eq('indicator_id', indicatorId)
    .order('date', { ascending: false })
    .limit(limit)

  if (countryId === null) {
    query = query.is('country_id', null)
  } else {
    query = query.eq('country_id', countryId)
  }

  const { data, error } = await query
  if (error) return []
  // reverse so oldest → newest for chart
  return (data ?? []).map(r => r.value).reverse()
}

export interface IndicatorHistory {
  indicator_id: string
  indicator_name: string
  category: string
  unit: string
  frequency: string
  country_id: string | null
  country_name: string | null
  classification: 'DM' | 'EM' | null
  readings: { date: string; value: number }[]
  latest: number | null
  previous: number | null
  change: number | null        // absolute change vs previous
  changePct: number | null     // % change vs previous
  latestDate: string | null
  ragStatus: RagStatus
  source: string | null
  source_series_id: string | null
}

export async function fetchIndicatorHistory(
  indicatorId: string,
  countryId: string,
): Promise<IndicatorHistory | null> {
  // Fetch all readings for this indicator/country, newest first
  const isGlobal = countryId === 'GLOBAL'

  let query = supabase
    .from('readings')
    .select('date, value, source, source_series_id')
    .eq('indicator_id', indicatorId)
    .order('date', { ascending: true })

  if (isGlobal) {
    query = query.is('country_id', null)
  } else {
    query = query.eq('country_id', countryId)
  }

  const { data: rows, error } = await query
  if (error || !rows || rows.length === 0) return null

  // Fetch indicator + country metadata
  const [{ data: ind }, { data: ctry }] = await Promise.all([
    supabase.from('indicators').select('*').eq('id', indicatorId).single(),
    isGlobal
      ? Promise.resolve({ data: null })
      : supabase.from('countries').select('*').eq('id', countryId).single(),
  ])

  if (!ind) return null

  const latest   = rows[rows.length - 1]?.value ?? null
  const previous = rows[rows.length - 2]?.value ?? null
  const change   = latest !== null && previous !== null ? latest - previous : null
  const changePct =
    change !== null && previous !== null && previous !== 0
      ? (change / Math.abs(previous)) * 100
      : null

  // For WoW-based RAG (F1/F2) we need the last two weekly closes
  let wowPct: number | null = null
  if ((indicatorId === 'F1' || indicatorId === 'F2') && changePct !== null) {
    wowPct = changePct
  }

  const rag = computeRag(
    indicatorId,
    latest ?? 0,
    ctry?.classification ?? null,
    wowPct,
    previous,
  )

  return {
    indicator_id:   indicatorId,
    indicator_name: ind.name,
    category:       ind.category,
    unit:           ind.unit,
    frequency:      ind.frequency,
    country_id:     isGlobal ? null : countryId,
    country_name:   ctry?.name ?? null,
    classification: ctry?.classification ?? null,
    readings:       rows.map(r => ({ date: r.date, value: r.value })),
    source:         (rows[rows.length - 1] as any)?.source ?? null,
    source_series_id: (rows[rows.length - 1] as any)?.source_series_id ?? null,
    latest,
    previous,
    change,
    changePct,
    latestDate:     rows[rows.length - 1]?.date ?? null,
    ragStatus:      rag,
  }
}

export interface PeerReading {
  countryId: string
  countryName: string
  classification: 'DM' | 'EM' | null
  value: number
  ragStatus: RagStatus
}

// Latest value of the SAME indicator across every country — for peer context on
// the detail page. Lets an analyst instantly rank the focused economy vs others.
export async function fetchPeerReadings(indicatorId: string): Promise<PeerReading[]> {
  const { data, error } = await supabase
    .from('latest_readings')
    .select('country_id, country_name, classification, value')
    .eq('indicator_id', indicatorId)
  if (error || !data) return []

  return data
    .filter(r => r.country_id !== null)
    .map(r => ({
      countryId: r.country_id as string,
      countryName: r.country_name ?? (r.country_id as string),
      classification: (r.classification as 'DM' | 'EM' | null) ?? null,
      value: r.value,
      ragStatus: computeRag(indicatorId, r.value, (r.classification as 'DM' | 'EM' | null) ?? null, null, null),
    }))
    .sort((a, b) => b.value - a.value)
}

// Prior reading per indicator+country for trend-based RAG (E1, E3).
// Returns a map keyed `indicatorId:countryId` → previous value (2nd-newest date).
async function fetchPriorReadings(
  indicatorIds: string[],
): Promise<Map<string, number>> {
  const { data, error } = await supabase
    .from('readings')
    .select('indicator_id, country_id, date, value')
    .in('indicator_id', indicatorIds)
    .order('date', { ascending: false })
  if (error || !data) return new Map()

  // Walk newest→oldest; the 2nd row seen per key is the prior reading.
  const seen = new Map<string, number>()
  const prior = new Map<string, number>()
  for (const r of data) {
    const key = `${r.indicator_id}:${r.country_id ?? 'GLOBAL'}`
    const count = seen.get(key) ?? 0
    if (count === 1) prior.set(key, r.value)
    seen.set(key, count + 1)
  }
  return prior
}

// Fetch the trailing N readings for EVERY indicator/country in one query, so the
// heatmap can show real sparklines without firing one request per cell.
// Returns a map keyed `indicatorId:countryId` → oldest→newest value array.
async function fetchAllSparklines(limit = 12): Promise<Map<string, number[]>> {
  // Pull a generous window of recent rows, newest first, then slice per series.
  const { data, error } = await supabase
    .from('readings')
    .select('indicator_id, country_id, date, value')
    .order('date', { ascending: false })
    .limit(6000)
  if (error || !data) return new Map()

  const acc = new Map<string, number[]>()
  for (const r of data) {
    const key = `${r.indicator_id}:${r.country_id ?? 'GLOBAL'}`
    const arr = acc.get(key)
    if (arr) {
      if (arr.length < limit) arr.push(r.value)
    } else {
      acc.set(key, [r.value])
    }
  }
  // rows came newest→oldest; reverse each series to oldest→newest for charts
  for (const [k, v] of acc) acc.set(k, v.reverse())
  return acc
}

// Build the full heatmap cell matrix from latest_readings + weekly_market
export async function buildHeatmapData(): Promise<HeatmapCell[]> {
  const [latest, weekly, priorReadings, sparklines] = await Promise.all([
    fetchLatestReadings(),
    fetchWeeklyMarket(),
    fetchPriorReadings(['E1', 'E3']),
    fetchAllSparklines(12),
  ])

  // Index weekly by indicator+country for latest week
  const weeklyLatest = new Map<string, WeeklyMarket>()
  for (const row of weekly) {
    const key = `${row.indicator_id}:${row.country_id ?? 'GLOBAL'}`
    if (!weeklyLatest.has(key)) weeklyLatest.set(key, row)
  }

  // Index latest readings by indicator+country
  const readingsMap = new Map<string, LatestReading>()
  for (const row of latest) {
    readingsMap.set(`${row.indicator_id}:${row.country_id ?? 'GLOBAL'}`, row)
  }

  const cells: HeatmapCell[] = []

  for (const country of COUNTRIES) {
    // Get all indicators that apply to this country from latest_readings
    const countryReadings = latest.filter(r =>
      r.country_id === country.id ||
      (r.country_id === null) // global series
    )

    for (const reading of countryReadings) {
      const weekKey = `${reading.indicator_id}:${reading.country_id ?? 'GLOBAL'}`
      const weekRow = weeklyLatest.get(weekKey)
      const wowPct = weekRow?.wow_pct ?? null

      const priorKey = `${reading.indicator_id}:${reading.country_id ?? 'GLOBAL'}`
      const prevValue = priorReadings.get(priorKey) ?? null

      const rag = computeRag(
        reading.indicator_id,
        reading.value,
        country.classification,
        wowPct,
        prevValue,
      )

      const currency = reading.indicator_id === 'E1'
        ? (country.id === 'EA' ? '€' : country.id === 'SG' ? 'S$' : '$')
        : '$'
      cells.push({
        indicatorId:    reading.indicator_id,
        indicatorName:  reading.indicator_name,
        category:       reading.category,
        unit:           reading.unit,
        frequency:      reading.frequency,
        countryId:      country.id,
        value:          reading.value,
        displayValue:   formatValue(reading.value, reading.unit, true, currency),
        date:           reading.date,
        ragStatus:      rag,
        wowPct,
        sparkline:      sparklines.get(weekKey) ?? [],
      })
    }
  }

  return cells
}
