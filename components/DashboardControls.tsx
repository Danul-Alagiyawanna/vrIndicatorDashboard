'use client'

import { useState } from 'react'
import type { HeatmapCell, RagStatus } from '@/types/indicators'
import type { CountryHealth } from '@/lib/analytics'
import HeatmapGrid from './HeatmapGrid'

interface Props {
  cells: HeatmapCell[]
  health: CountryHealth[]
}

type Filter = RagStatus | 'all'

const FILTERS: { key: Filter; label: string; dot: string; active: string }[] = [
  { key: 'all',   label: 'All',      dot: 'bg-zinc-400',    active: 'border-zinc-500 text-white bg-zinc-800/60' },
  { key: 'red',   label: 'Risk',     dot: 'bg-red-500',     active: 'border-red-600 text-red-300 bg-red-950/40' },
  { key: 'amber', label: 'Watch',    dot: 'bg-amber-400',   active: 'border-amber-600 text-amber-300 bg-amber-950/40' },
  { key: 'green', label: 'Positive', dot: 'bg-emerald-400', active: 'border-emerald-600 text-emerald-300 bg-emerald-950/40' },
]

export default function DashboardControls({ cells, health }: Props) {
  const [filter, setFilter] = useState<Filter>('all')

  const counts: Record<string, number> = {
    all: cells.filter(c => c.ragStatus !== null).length,
    red: cells.filter(c => c.ragStatus === 'red').length,
    amber: cells.filter(c => c.ragStatus === 'amber').length,
    green: cells.filter(c => c.ragStatus === 'green').length,
  }

  return (
    <div>
      {/* Control bar */}
      <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="heading-mono text-[10px] uppercase text-zinc-600 mr-1">Filter</span>
          {FILTERS.map(f => {
            const isActive = filter === f.key
            return (
              <button
                key={f.key ?? 'all'}
                onClick={() => setFilter(f.key)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium transition-all
                  ${isActive ? f.active : 'border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700'}`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${f.dot}`} />
                {f.label}
                <span className="tnum text-[10px] opacity-70">{counts[f.key ?? 'all']}</span>
              </button>
            )
          })}
        </div>

        {filter !== 'all' && (
          <span className="text-[11px] text-zinc-500">
            Highlighting <span className="text-zinc-300">{counts[filter ?? 'all']}</span> cells · others dimmed
          </span>
        )}
      </div>

      {/* Mobile scroll hint */}
      <p className="sm:hidden text-[10px] text-zinc-600 mb-2 flex items-center gap-1">
        <span aria-hidden>↔</span> Swipe the grid sideways to see all economies
      </p>

      <HeatmapGrid cells={cells} health={health} filter={filter} />
    </div>
  )
}
