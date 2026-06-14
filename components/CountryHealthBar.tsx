import type { CountryHealth } from '@/lib/analytics'

interface Props {
  health: CountryHealth[]
}

function scoreColor(score: number | null): string {
  if (score === null) return 'text-zinc-500'
  if (score >= 70) return 'text-emerald-400'
  if (score >= 45) return 'text-amber-300'
  return 'text-red-400'
}
function scoreBar(score: number | null): string {
  if (score === null) return 'bg-zinc-600'
  if (score >= 70) return 'bg-emerald-500'
  if (score >= 45) return 'bg-amber-400'
  return 'bg-red-500'
}

export default function CountryHealthBar({ health }: Props) {
  // Rank by score desc, nulls last
  const ranked = [...health].sort((a, b) => (b.score ?? -1) - (a.score ?? -1))

  return (
    <section className="rise mb-5" style={{ animationDelay: '60ms' }}>
      <div className="flex items-center gap-2 mb-2.5">
        <div className="w-1 h-3.5 rounded-full bg-cyan-400" />
        <h2 className="heading-mono text-[10px] uppercase text-zinc-500">
          Economy Health Ranking
        </h2>
        <span className="text-[10px] text-zinc-600">composite RAG score · 0–100</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2.5">
        {ranked.map((c, i) => (
          <div
            key={c.id}
            className="panel panel-hover rounded-xl p-3.5 relative overflow-hidden"
          >
            {/* rank chip */}
            <span className="absolute top-2.5 right-2.5 text-[10px] font-mono text-zinc-600">
              #{i + 1}
            </span>

            <div className="flex items-baseline gap-2">
              <span className="text-lg font-bold text-white tracking-tight">{c.id}</span>
              <span className={`text-[10px] font-semibold ${c.classification === 'DM' ? 'text-cyan-400' : 'text-amber-400'}`}>
                {c.classification}
              </span>
            </div>
            <div className="text-zinc-500 text-[11px] truncate mb-2.5">{c.name}</div>

            <div className="flex items-end justify-between mb-1.5">
              <span className={`text-2xl font-bold tnum ${scoreColor(c.score)}`}>
                {c.score ?? '—'}
              </span>
              {c.trend !== null && (
                <span className={`text-[11px] font-medium tnum mb-1 ${c.trend >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {c.trend >= 0 ? '▲' : '▼'} {Math.abs(c.trend).toFixed(2)}%
                </span>
              )}
            </div>

            {/* score track */}
            <div className="h-1.5 rounded-full bg-zinc-800/70 overflow-hidden">
              <div
                className={`h-full rounded-full ${scoreBar(c.score)}`}
                style={{ width: `${c.score ?? 0}%` }}
              />
            </div>

            {/* RAG tally */}
            <div className="flex items-center gap-2.5 mt-2.5 text-[10px] tnum">
              <span className="flex items-center gap-1 text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />{c.green}
              </span>
              <span className="flex items-center gap-1 text-amber-300">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />{c.amber}
              </span>
              <span className="flex items-center gap-1 text-red-400">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500" />{c.red}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
