import { type RagDistribution, type Signal, type Mover, moverLabel } from '@/lib/analytics'

interface Props {
  dist: RagDistribution
  regime: { label: string; tone: Signal['tone'] }
  signals: Signal[]
  movers: { gainers: Mover[]; losers: Mover[] }
  countriesTracked: number
  indicatorsTracked: number
}

const TONE_TEXT: Record<Signal['tone'], string> = {
  risk: 'text-red-400',
  watch: 'text-amber-300',
  positive: 'text-emerald-400',
  neutral: 'text-cyan-300',
}
const TONE_DOT: Record<Signal['tone'], string> = {
  risk: 'bg-red-500',
  watch: 'bg-amber-400',
  positive: 'bg-emerald-400',
  neutral: 'bg-cyan-400',
}

function pct(n: number, total: number) {
  return total === 0 ? 0 : Math.round((n / total) * 100)
}

export default function MacroPulse({
  dist,
  regime,
  signals,
  movers,
  countriesTracked,
  indicatorsTracked,
}: Props) {
  const greenPct = pct(dist.green, dist.scored)
  const amberPct = pct(dist.amber, dist.scored)
  const redPct = pct(dist.red, dist.scored)

  return (
    <section className="rise mb-5">
      <div className="panel rounded-2xl overflow-hidden">
        <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_1.4fr_1.3fr] divide-y lg:divide-y-0 lg:divide-x divide-zinc-800/60">

          {/* ── Regime read ───────────────────────────────────────────── */}
          <div className="p-4 sm:p-5">
            <div className="flex items-center gap-2 mb-3">
              <span className={`relative w-2 h-2 rounded-full live-dot ${TONE_DOT[regime.tone]}`} />
              <span className="heading-mono text-[10px] uppercase text-zinc-500">Market Regime</span>
            </div>
            <div className={`text-2xl font-bold tracking-tight ${TONE_TEXT[regime.tone]}`}>
              {regime.label}
            </div>
            <p className="text-zinc-500 text-xs mt-1.5 leading-relaxed">
              Synthesised from {dist.scored} scored signals across {countriesTracked} economies
              &middot; {indicatorsTracked} indicators tracked
            </p>

            {/* Distribution bar */}
            <div className="mt-4">
              <div className="flex h-2.5 rounded-full overflow-hidden bg-zinc-800/60">
                <div className="bg-emerald-500" style={{ width: `${greenPct}%` }} title={`Positive ${greenPct}%`} />
                <div className="bg-amber-400" style={{ width: `${amberPct}%` }} title={`Watch ${amberPct}%`} />
                <div className="bg-red-500" style={{ width: `${redPct}%` }} title={`Risk ${redPct}%`} />
              </div>
              <div className="flex justify-between mt-2 text-[11px] tnum">
                <span className="text-emerald-400">{greenPct}% positive</span>
                <span className="text-amber-300">{amberPct}% watch</span>
                <span className="text-red-400">{redPct}% risk</span>
              </div>
            </div>
          </div>

          {/* ── Key signals ──────────────────────────────────────────── */}
          <div className="p-4 sm:p-5">
            <div className="heading-mono text-[10px] uppercase text-zinc-500 mb-3">Key Signals</div>
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {signals.slice(0, 4).map((s, i) => (
                <li key={i} className="flex items-start gap-2.5">
                  <span className={`mt-1 w-1.5 h-1.5 rounded-full shrink-0 ${TONE_DOT[s.tone]}`} />
                  <div className="min-w-0">
                    <div className={`text-sm font-semibold leading-tight ${TONE_TEXT[s.tone]}`}>
                      {s.label}
                    </div>
                    <div className="text-zinc-500 text-[11px] truncate">{s.detail}</div>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {/* ── Top movers ───────────────────────────────────────────── */}
          <div className="p-4 sm:p-5">
            <div className="heading-mono text-[10px] uppercase text-zinc-500 mb-3">Weekly Movers</div>
            <div className="grid grid-cols-2 gap-x-3 sm:gap-x-5 gap-y-1.5 [&>*]:min-w-0">
              <div className="text-[10px] uppercase tracking-wider text-emerald-500/70 mb-0.5">Gainers</div>
              <div className="text-[10px] uppercase tracking-wider text-red-500/70 mb-0.5">Losers</div>
              {Array.from({ length: Math.max(movers.gainers.length, movers.losers.length, 1) }).map((_, i) => (
                <MoverPair key={i} g={movers.gainers[i]} l={movers.losers[i]} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function MoverPair({ g, l }: { g?: Mover; l?: Mover }) {
  return (
    <>
      <div className="flex items-center justify-between gap-2 text-xs">
        {g ? (
          <>
            <span className="text-zinc-300 truncate">
              {moverLabel(g)}
              {g.countryId !== 'GLOBAL' && <span className="text-zinc-600"> · {g.countryId}</span>}
            </span>
            <span className="text-emerald-400 font-semibold tnum shrink-0">+{g.wowPct.toFixed(2)}%</span>
          </>
        ) : <span className="text-zinc-700">—</span>}
      </div>
      <div className="flex items-center justify-between gap-2 text-xs">
        {l ? (
          <>
            <span className="text-zinc-300 truncate">
              {moverLabel(l)}
              {l.countryId !== 'GLOBAL' && <span className="text-zinc-600"> · {l.countryId}</span>}
            </span>
            <span className="text-red-400 font-semibold tnum shrink-0">{l.wowPct.toFixed(2)}%</span>
          </>
        ) : <span className="text-zinc-700">—</span>}
      </div>
    </>
  )
}
