// ── Macro analytics ───────────────────────────────────────────────────────────
// Derives the at-a-glance intelligence an investment researcher wants first:
// RAG distribution, per-country health scores, the strongest movers, and a set
// of notable structural signals (inverted curves, oil regime, etc.).
//
// Everything here is pure: it takes the already-fetched HeatmapCell[] and the
// static country/indicator metadata, so it adds zero extra database round-trips.

import type { HeatmapCell, RagStatus } from '@/types/indicators'
import { COUNTRIES } from '@/types/indicators'

// Weight each RAG state on a 0–100 scale so countries can be ranked.
const RAG_SCORE: Record<NonNullable<RagStatus>, number> = {
  green: 100,
  amber: 55,
  red: 12,
}

export interface RagDistribution {
  green: number
  amber: number
  red: number
  none: number
  scored: number // green + amber + red (cells that carry a RAG signal)
  total: number
}

export function ragDistribution(cells: HeatmapCell[]): RagDistribution {
  const d: RagDistribution = { green: 0, amber: 0, red: 0, none: 0, scored: 0, total: cells.length }
  for (const c of cells) {
    if (c.ragStatus === 'green') d.green++
    else if (c.ragStatus === 'amber') d.amber++
    else if (c.ragStatus === 'red') d.red++
    else d.none++
  }
  d.scored = d.green + d.amber + d.red
  return d
}

export interface CountryHealth {
  id: string
  name: string
  region: string
  classification: 'DM' | 'EM'
  score: number | null      // 0–100 composite, null when no scored cells
  green: number
  amber: number
  red: number
  scored: number
  trend: number | null      // avg WoW% of that country's market cells (sentiment)
}

// Composite health score per country = mean of RAG_SCORE over its scored cells.
export function countryHealth(cells: HeatmapCell[]): CountryHealth[] {
  return COUNTRIES.map(country => {
    const owned = cells.filter(c => c.countryId === country.id)
    const scoredCells = owned.filter(c => c.ragStatus !== null)
    const green = owned.filter(c => c.ragStatus === 'green').length
    const amber = owned.filter(c => c.ragStatus === 'amber').length
    const red = owned.filter(c => c.ragStatus === 'red').length

    const score = scoredCells.length
      ? Math.round(
          scoredCells.reduce((s, c) => s + RAG_SCORE[c.ragStatus!], 0) /
            scoredCells.length,
        )
      : null

    const wowCells = owned.filter(c => c.wowPct !== null)
    const trend = wowCells.length
      ? wowCells.reduce((s, c) => s + (c.wowPct ?? 0), 0) / wowCells.length
      : null

    return {
      id: country.id,
      name: country.name,
      region: country.region,
      classification: country.classification,
      score,
      green,
      amber,
      red,
      scored: scoredCells.length,
      trend,
    }
  })
}

export interface Mover {
  indicatorId: string
  indicatorName: string
  countryId: string
  wowPct: number
  ragStatus: RagStatus
  unit: string
}

// Short, readable indicator names for compact UI (ticker, movers list). The DB
// names are verbose ("Equity Index (WoW % change)"), so map to clean ones.
const SHORT_LABEL: Record<string, string> = {
  F1: 'Equity',
  F2: 'FX vs USD',
  F3: 'Credit Spread',
  C1: 'Brent Crude',
  M2: '10Y Yield',
  M3: 'Yield Curve',
}

export function moverLabel(m: Mover): string {
  return SHORT_LABEL[m.indicatorId] ?? m.indicatorName
}

// Strongest weekly movers (markets) — sorted by magnitude, split gainers/losers.
export function topMovers(cells: HeatmapCell[], n = 5): { gainers: Mover[]; losers: Mover[] } {
  // Global series (e.g. C1 Brent) have country_id = null in the DB but are
  // fanned out to every country row in the heatmap. Deduplicate by indicatorId
  // for these so they appear only once in the movers list.
  const GLOBAL_INDICATORS = new Set(['C1'])
  const seenGlobal = new Set<string>()
  const movers: Mover[] = cells
    .filter(c => c.wowPct !== null)
    .filter(c => {
      if (!GLOBAL_INDICATORS.has(c.indicatorId)) return true
      if (seenGlobal.has(c.indicatorId)) return false
      seenGlobal.add(c.indicatorId)
      return true
    })
    .map(c => ({
      indicatorId: c.indicatorId,
      indicatorName: c.indicatorName,
      countryId: c.countryId,
      wowPct: c.wowPct as number,
      ragStatus: c.ragStatus,
      unit: c.unit,
    }))

  const gainers = [...movers].filter(m => m.wowPct > 0).sort((a, b) => b.wowPct - a.wowPct).slice(0, n)
  const losers = [...movers].filter(m => m.wowPct < 0).sort((a, b) => a.wowPct - b.wowPct).slice(0, n)
  return { gainers, losers }
}

export interface Signal {
  label: string
  detail: string
  tone: 'risk' | 'watch' | 'positive' | 'neutral'
}

// A small set of structural reads that matter for a macro view.
export function keySignals(cells: HeatmapCell[]): Signal[] {
  const signals: Signal[] = []
  const find = (id: string, country: string) =>
    cells.find(c => c.indicatorId === id && c.countryId === country)

  // Inverted yield curves (M3 < 0)
  const inverted = cells.filter(c => c.indicatorId === 'M3' && c.value !== null && (c.value as number) < 0)
  if (inverted.length) {
    signals.push({
      label: `${inverted.length} inverted curve${inverted.length > 1 ? 's' : ''}`,
      detail: inverted.map(c => c.countryId).join(', '),
      tone: 'risk',
    })
  } else {
    signals.push({ label: 'No curve inversions', detail: 'Curves positively sloped', tone: 'positive' })
  }

  // Brent crude regime
  const brent = find('C1', 'GLOBAL') ?? cells.find(c => c.indicatorId === 'C1')
  if (brent && brent.value !== null) {
    const v = brent.value as number
    signals.push({
      label: `Brent $${v.toFixed(0)}`,
      detail: v > 100 ? 'Elevated — inflation pressure' : v > 80 ? 'Mid-range' : 'Subdued',
      tone: v > 100 ? 'risk' : v > 80 ? 'watch' : 'positive',
    })
  }

  // Economies in contraction — manufacturing PMI < 50
  const contracting = cells.filter(c => c.indicatorId === 'G2' && c.value !== null && (c.value as number) < 50)
  if (contracting.length) {
    signals.push({
      label: `${contracting.length} mfg contracting`,
      detail: contracting.map(c => c.countryId).join(', ') + ' PMI < 50',
      tone: 'watch',
    })
  }

  // Hot inflation — headline CPI > 8 anywhere
  const hotCpi = cells.filter(c => c.indicatorId === 'I1' && c.value !== null && (c.value as number) > 8)
  if (hotCpi.length) {
    signals.push({
      label: `${hotCpi.length} hot CPI print${hotCpi.length > 1 ? 's' : ''}`,
      detail: hotCpi.map(c => `${c.countryId} ${(c.value as number).toFixed(1)}%`).join(', '),
      tone: 'risk',
    })
  }

  return signals
}

// Overall regime read derived from the RAG distribution — a one-line headline.
export function regimeRead(d: RagDistribution): { label: string; tone: Signal['tone'] } {
  if (d.scored === 0) return { label: 'Insufficient data', tone: 'neutral' }
  const riskShare = d.red / d.scored
  const positiveShare = d.green / d.scored
  if (riskShare >= 0.33) return { label: 'Risk-off regime', tone: 'risk' }
  if (riskShare >= 0.2) return { label: 'Defensive / late cycle', tone: 'watch' }
  if (positiveShare >= 0.5) return { label: 'Risk-on / expansion', tone: 'positive' }
  return { label: 'Mixed / transitional', tone: 'neutral' }
}
