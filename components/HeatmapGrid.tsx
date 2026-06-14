'use client'

import type { HeatmapCell, RagStatus } from '@/types/indicators'
import { CATEGORIES, COUNTRIES } from '@/types/indicators'
import type { CountryHealth } from '@/lib/analytics'
import RagCell from './RagCell'

interface Props {
  cells: HeatmapCell[]
  health: CountryHealth[]
  filter: RagStatus | 'all'
}

const CATEGORY_INDICATORS: Record<string, { id: string; label: string; unit: string }[]> = {
  'Growth': [
    { id: 'G1', label: 'GDP Growth',    unit: '% YoY' },
    { id: 'G2', label: 'Mfg PMI',       unit: 'Index' },
    { id: 'G3', label: 'Svcs PMI',      unit: 'Index' },
    { id: 'G4', label: 'Ind. Prod.',    unit: '% YoY' },
  ],
  'Inflation': [
    { id: 'I1', label: 'Headline CPI',  unit: '% YoY' },
    { id: 'I2', label: 'Core CPI',      unit: '% YoY' },
    { id: 'I3', label: 'Food CPI',      unit: '% YoY' },
  ],
  'Monetary Policy': [
    { id: 'M1', label: 'Policy Rate',   unit: '%' },
    { id: 'M2', label: '10Y Yield',     unit: '%' },
    { id: 'M3', label: 'Yield Curve',   unit: 'bps' },
  ],
  'Labour Market': [
    { id: 'L1', label: 'Unemployment',  unit: '%' },
    { id: 'L2', label: 'Wage Growth',   unit: '% YoY' },
  ],
  'Financial Markets': [
    { id: 'F1', label: 'Equity',        unit: 'Index' },
    { id: 'F2', label: 'FX vs USD',     unit: 'Rate' },
    { id: 'F3', label: 'Credit Spread', unit: 'bps' },
  ],
  'External Sector': [
    { id: 'E1', label: 'Trade Balance', unit: 'USD bn' },
    { id: 'E2', label: 'FX Reserves',  unit: 'USD bn' },
    { id: 'E3', label: 'Remittances',  unit: 'USD mn' },
  ],
  'Commodities': [
    { id: 'C1', label: 'Brent Crude',  unit: 'USD/bbl' },
  ],
}

const CATEGORY_COLOR: Record<string, { bar: string; label: string }> = {
  'Growth':            { bar: 'bg-blue-500',    label: 'text-blue-400' },
  'Inflation':         { bar: 'bg-orange-500',  label: 'text-orange-400' },
  'Monetary Policy':   { bar: 'bg-purple-500',  label: 'text-purple-400' },
  'Labour Market':     { bar: 'bg-cyan-500',    label: 'text-cyan-400' },
  'Financial Markets': { bar: 'bg-emerald-500', label: 'text-emerald-400' },
  'External Sector':   { bar: 'bg-yellow-500',  label: 'text-yellow-400' },
  'Commodities':       { bar: 'bg-rose-500',    label: 'text-rose-400' },
}

function scoreBar(score: number | null): string {
  if (score === null) return 'bg-zinc-600'
  if (score >= 70) return 'bg-emerald-500'
  if (score >= 45) return 'bg-amber-400'
  return 'bg-red-500'
}

export default function HeatmapGrid({ cells, health, filter }: Props) {
  // Build lookup: indicatorId → countryId → cell
  const lookup = new Map<string, Map<string, HeatmapCell>>()
  for (const cell of cells) {
    if (!lookup.has(cell.indicatorId)) lookup.set(cell.indicatorId, new Map())
    lookup.get(cell.indicatorId)!.set(cell.countryId, cell)
  }
  const healthById = new Map(health.map(h => [h.id, h]))

  // Tighter columns on phones; the label column is pinned left while the country
  // columns scroll horizontally — the standard data-terminal mobile pattern.
  const gridCols =
    'grid-cols-[104px_repeat(6,minmax(76px,1fr))] sm:grid-cols-[150px_repeat(6,minmax(92px,1fr))]'

  return (
    <div className="panel rounded-2xl p-2.5 sm:p-4 rise" style={{ animationDelay: '120ms' }}>
      {/* Horizontal scroll only. The cell detail popover is portaled to body, so
          it's never clipped here regardless of overflow. */}
      <div className="w-full overflow-x-auto">
        {/* Header row with country + health bar */}
        <div className={`grid ${gridCols} gap-x-1.5 mb-3 sticky top-0 bg-[#070a0c]/90 backdrop-blur z-20 pb-3 border-b border-zinc-800/70`}>
          <div className="flex items-end pb-0.5 sticky left-0 bg-[#070a0c]/90 z-10">
            <span className="heading-mono text-[10px] uppercase text-zinc-600">Indicator</span>
          </div>
          {COUNTRIES.map(c => {
            const h = healthById.get(c.id)
            return (
              <div key={c.id} className="text-center px-0.5">
                <div className="text-white font-bold text-sm leading-none">{c.id}</div>
                <div className={`text-[9px] font-semibold mt-0.5 ${c.classification === 'DM' ? 'text-cyan-400' : 'text-amber-400'}`}>
                  {c.classification} · {c.region.split(' ')[0]}
                </div>
                {/* mini health track */}
                <div className="h-1 rounded-full bg-zinc-800/70 overflow-hidden mt-1.5">
                  <div className={`h-full ${scoreBar(h?.score ?? null)}`} style={{ width: `${h?.score ?? 0}%` }} />
                </div>
                <div className="text-[9px] text-zinc-600 tnum mt-0.5">{h?.score ?? '—'}</div>
              </div>
            )
          })}
        </div>

        {/* Category sections */}
        {CATEGORIES.map(category => {
          const indicators = CATEGORY_INDICATORS[category] ?? []
          const color = CATEGORY_COLOR[category] ?? { bar: 'bg-zinc-600', label: 'text-zinc-400' }

          return (
            <div key={category} className="mb-5 last:mb-1">
              <div className="flex items-center gap-2 mb-2">
                <div className={`w-1 h-3.5 rounded-full ${color.bar}`} />
                <span className={`text-[11px] font-semibold uppercase tracking-wider ${color.label}`}>
                  {category}
                </span>
                <div className="flex-1 h-px bg-zinc-800/50" />
              </div>

              {indicators.map(({ id, label, unit }) => (
                <div key={id} className={`grid ${gridCols} gap-x-1.5 gap-y-1.5 mb-1.5 items-stretch`}>
                  <div className="pr-2 flex flex-col justify-center sticky left-0 bg-[#070a0c]/90 backdrop-blur z-10">
                    <div className="text-zinc-200 text-[11px] sm:text-xs font-medium leading-tight">{label}</div>
                    <div className="text-zinc-600 text-[10px]">{unit}</div>
                  </div>

                  {COUNTRIES.map(country => {
                    const cell = lookup.get(id)?.get(country.id)
                    if (!cell) {
                      return (
                        <div key={country.id} className="rounded-lg border border-zinc-800/60 bg-zinc-900/20 flex items-center justify-center min-h-[52px]">
                          <span className="text-zinc-700 text-xs">—</span>
                        </div>
                      )
                    }
                    const dimmed = filter !== 'all' && cell.ragStatus !== filter
                    return <RagCell key={country.id} cell={cell} dimmed={dimmed} />
                  })}
                </div>
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}
