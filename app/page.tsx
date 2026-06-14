import Link from 'next/link'
import { buildHeatmapData } from '@/lib/data'
import {
  ragDistribution,
  countryHealth,
  topMovers,
  keySignals,
  regimeRead,
} from '@/lib/analytics'
import { COUNTRIES } from '@/types/indicators'
import DashboardControls from '@/components/DashboardControls'
import MacroPulse from '@/components/MacroPulse'
import CountryHealthBar from '@/components/CountryHealthBar'
import SignalTicker from '@/components/SignalTicker'
import NewDataBanner from '@/components/NewDataBanner'

export const revalidate = 3600 // ISR: re-fetch from Supabase every hour

export default async function DashboardPage() {
  const cells = await buildHeatmapData().catch(() => [])

  const lastUpdated = cells.reduce(
    (latest, c) => (c.date && c.date > latest ? c.date : latest),
    '',
  )

  // Derive macro intelligence (pure, no extra DB calls)
  const dist = ragDistribution(cells)
  const health = countryHealth(cells)
  const movers = topMovers(cells, 5)
  const signals = keySignals(cells)
  const regime = regimeRead(dist)
  const indicatorsTracked = new Set(cells.map(c => c.indicatorId)).size

  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
  })

  return (
    <main className="min-h-screen text-white px-4 py-5 md:px-7 max-w-[1600px] mx-auto w-full overflow-x-clip">
      <NewDataBanner />

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="mb-5 rise">
        <div className="flex items-start justify-between flex-wrap gap-4 mb-3">
          <div className="flex items-center gap-3">
            {/* logo mark */}
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-400/90 to-blue-600/90 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <span className="font-bold text-black text-sm tracking-tighter">VR</span>
            </div>
            <div>
              <h1 className="text-base sm:text-lg font-bold text-white tracking-tight leading-none">
                VR Investments
              </h1>
              <p className="text-zinc-500 text-[11px] sm:text-xs mt-1 heading-mono uppercase">
                Global Macro Terminal
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 sm:gap-4 text-xs flex-wrap">
            <span className="flex items-center gap-1.5 text-zinc-400">
              <span className="relative w-2 h-2 rounded-full bg-cyan-400 live-dot" />
              <span className="heading-mono text-[10px] uppercase text-cyan-400">Live</span>
            </span>
            <span className="hidden sm:inline text-zinc-600">{today}</span>
            {lastUpdated && (
              <span className="text-zinc-500">
                <span className="hidden sm:inline">Latest data </span>
                <span className="text-zinc-300 tnum">{lastUpdated}</span>
              </span>
            )}
            <div className="hidden md:flex items-center gap-3 text-zinc-500">
              <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-500" />Positive</span>
              <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-400" />Watch</span>
              <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-500" />Risk</span>
            </div>
            <Link
              href="/guide"
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-zinc-800 text-zinc-300 hover:text-cyan-300 hover:border-cyan-700 transition-colors font-medium"
            >
              <span aria-hidden>📘</span> Guide
            </Link>
          </div>
        </div>

        {/* Live tape */}
        <SignalTicker movers={movers} />
      </header>

      {cells.length === 0 ? (
        <div className="panel rounded-2xl flex flex-col items-center justify-center py-24 text-zinc-500">
          <p className="text-lg font-medium text-zinc-300">No data yet</p>
          <p className="text-sm mt-1">Deploy the schema to Supabase and run the scrapers.</p>
          <code className="mt-4 bg-zinc-900 px-3 py-1.5 rounded text-xs text-zinc-300">
            python run.py --source financial
          </code>
        </div>
      ) : (
        <>
          <MacroPulse
            dist={dist}
            regime={regime}
            signals={signals}
            movers={movers}
            countriesTracked={COUNTRIES.length}
            indicatorsTracked={indicatorsTracked}
          />
          <CountryHealthBar health={health} />
          <DashboardControls cells={cells} health={health} />

          <footer className="mt-6 text-center text-[11px] text-zinc-600">
            Sources: FRED · World Bank · Yahoo Finance · Trading Economics · CBSL ·
            RAG thresholds per the VR Investments framework · Click any cell for full history & methodology
          </footer>
        </>
      )}
    </main>
  )
}
