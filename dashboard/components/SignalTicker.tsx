import { type Mover, moverLabel } from '@/lib/analytics'
import { COUNTRIES } from '@/types/indicators'

interface Props {
  movers: { gainers: Mover[]; losers: Mover[] }
}

const COUNTRY_NAME = new Map(COUNTRIES.map(c => [c.id, c.name]))

function label(m: Mover): string {
  const name = moverLabel(m)
  // Global series (e.g. Brent) carry no meaningful country — show name only.
  if (m.countryId === 'GLOBAL') return name
  const country = COUNTRY_NAME.get(m.countryId) ?? m.countryId
  return `${name} · ${country}`
}

// A subtle scrolling tape of the week's biggest market moves — terminal flavour.
export default function SignalTicker({ movers }: Props) {
  const items = [...movers.gainers, ...movers.losers]
    .sort((a, b) => Math.abs(b.wowPct) - Math.abs(a.wowPct))

  if (items.length === 0) return null

  const Tape = () => (
    <>
      {items.map((m, i) => (
        <span key={i} className="inline-flex items-center gap-1.5 px-4 text-xs tnum border-r border-zinc-800/60">
          <span className="text-zinc-300 font-medium">{label(m)}</span>
          <span className={m.wowPct >= 0 ? 'text-emerald-400' : 'text-red-400'}>
            {m.wowPct >= 0 ? '▲' : '▼'} {Math.abs(m.wowPct).toFixed(2)}%
          </span>
        </span>
      ))}
    </>
  )

  return (
    <div className="relative overflow-hidden rounded-lg border border-zinc-800/60 bg-zinc-900/30 py-1.5">
      <div className="ticker-track">
        <Tape />
        <Tape />
      </div>
      {/* edge fades */}
      <div className="pointer-events-none absolute inset-y-0 left-0 w-12 bg-gradient-to-r from-[#070a0c] to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-12 bg-gradient-to-l from-[#070a0c] to-transparent" />
    </div>
  )
}
