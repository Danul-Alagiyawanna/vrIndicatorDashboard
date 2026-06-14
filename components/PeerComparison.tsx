import type { PeerReading } from '@/lib/data'
import { formatValue } from '@/lib/data'

interface Props {
  peers: PeerReading[]
  unit: string
  focusCountry: string
  indicatorName: string
}

const BAR: Record<string, string> = {
  green: 'bg-emerald-500',
  amber: 'bg-amber-400',
  red: 'bg-red-500',
  none: 'bg-zinc-600',
}

export default function PeerComparison({ peers, unit, focusCountry, indicatorName }: Props) {
  if (peers.length < 2) return null

  const values = peers.map(p => p.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1

  return (
    <div className="panel rounded-xl p-4">
      <h2 className="text-sm font-semibold text-zinc-300 mb-0.5">Peer comparison</h2>
      <p className="text-zinc-600 text-xs mb-4">{indicatorName} · latest reading across economies</p>

      <div className="space-y-2.5">
        {peers.map(p => {
          const widthPct = ((p.value - min) / span) * 100
          const isFocus = p.countryId === focusCountry
          const tone = p.ragStatus ?? 'none'
          return (
            <div key={p.countryId} className="flex items-center gap-3">
              <div className={`w-9 text-xs font-bold tnum ${isFocus ? 'text-cyan-400' : 'text-zinc-400'}`}>
                {p.countryId}
              </div>
              <div className="flex-1 h-6 rounded-md bg-zinc-800/40 relative overflow-hidden">
                <div
                  className={`h-full rounded-md ${BAR[tone]} ${isFocus ? 'opacity-100' : 'opacity-55'}`}
                  style={{ width: `${Math.max(widthPct, 3)}%` }}
                />
                <span className={`absolute right-2 top-1/2 -translate-y-1/2 text-[11px] tnum font-medium ${isFocus ? 'text-white' : 'text-zinc-400'}`}>
                  {formatValue(p.value, unit)}
                </span>
                {isFocus && (
                  <span className="absolute left-2 top-1/2 -translate-y-1/2 text-[9px] uppercase tracking-wider text-cyan-300 font-semibold">
                    you
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
