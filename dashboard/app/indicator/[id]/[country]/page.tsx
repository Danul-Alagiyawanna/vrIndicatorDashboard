import Link from 'next/link'
import { notFound } from 'next/navigation'
import { fetchIndicatorHistory, fetchPeerReadings, formatValue } from '@/lib/data'
import TimeSeriesChart from '@/components/TimeSeriesChart'
import EditableReadingsTable from '@/components/EditableReadingsTable'
import PeerComparison from '@/components/PeerComparison'
import { COUNTRIES } from '@/types/indicators'

export const revalidate = 3600

interface Props {
  params: Promise<{ id: string; country: string }>
}

// Reference lines for indicators where a threshold is meaningful on the chart
const REFERENCE: Record<string, { value: number; label: string }> = {
  G2: { value: 50, label: 'Expansion / Contraction' },
  G3: { value: 50, label: 'Expansion / Contraction' },
  M3: { value: 0,  label: 'Inversion' },
}

const RAG_BADGE: Record<string, string> = {
  green: 'bg-green-500/20 text-green-400 border border-green-700',
  amber: 'bg-amber-500/20 text-amber-400 border border-amber-700',
  red:   'bg-red-500/20   text-red-400   border border-red-700',
}

// M3 yield curve source URLs — 10Y and 2Y per country
const M3_10Y_URLS: Record<string, string> = {
  US:  'https://fred.stlouisfed.org/series/DGS10',
  EA:  'https://tradingeconomics.com/euro-area/government-bond-yield',
  SG:  'https://tradingeconomics.com/singapore/government-bond-yield',
  CN:  'https://tradingeconomics.com/china/government-bond-yield',
  IN:  'https://tradingeconomics.com/india/government-bond-yield',
  SL:  'https://www.investing.com/rates-bonds/sri-lanka-10-year',
}
const M3_2Y_URLS: Record<string, string> = {
  US:  'https://fred.stlouisfed.org/series/DGS2',
  EA:  'https://data.ecb.europa.eu/data/datasets/FM/FM.M.U2.EUR.4F.BB.U2_2Y.YLD',
  SG:  'https://tradingeconomics.com/singapore/2-year-bond-yield',
  CN:  'https://tradingeconomics.com/china/2-year-note-yield',
  IN:  'https://tradingeconomics.com/india/2-year-note-yield',
  SL:  'https://www.investing.com/rates-bonds/sri-lanka-2-year-bond-yield',
}

const G2_TE_URLS: Record<string, string> = {
  US: 'https://tradingeconomics.com/united-states/manufacturing-pmi',
  EA: 'https://tradingeconomics.com/euro-area/manufacturing-pmi',
  SG: 'https://tradingeconomics.com/singapore/manufacturing-pmi',
  CN: 'https://tradingeconomics.com/china/manufacturing-pmi',
  IN: 'https://tradingeconomics.com/india/manufacturing-pmi',
  SL: 'https://tradingeconomics.com/sri-lanka/manufacturing-pmi',
}

const G3_TE_URLS: Record<string, string> = {
  US: 'https://tradingeconomics.com/united-states/non-manufacturing-pmi',
  EA: 'https://tradingeconomics.com/euro-area/services-pmi',
  SG: 'https://tradingeconomics.com/singapore/composite-pmi',
  CN: 'https://tradingeconomics.com/china/non-manufacturing-pmi',
  IN: 'https://tradingeconomics.com/india/services-pmi',
  SL: 'https://tradingeconomics.com/sri-lanka/services-pmi',
}

// Build a human-readable source URL from source + source_series_id
function buildSourceUrl(
  source: string | null,
  seriesId: string | null,
  indicatorId: string,
  countryId: string,
): string | null {
  if (indicatorId === 'M3') return M3_10Y_URLS[countryId] ?? null
  // series_id is already a full URL (TE pages, or PMI entries with injected URL)
  if (seriesId?.startsWith('http')) return seriesId
  if (source === 'FRED') return `https://fred.stlouisfed.org/series/${seriesId}`
  if (source === 'World Bank') return `https://data.worldbank.org/indicator/${seriesId}`
  if (source === 'yfinance') return `https://finance.yahoo.com/quote/${encodeURIComponent(seriesId ?? '')}`
  // Fallback for manually-entered PMI rows that predate the URL injection
  if (indicatorId === 'G2') return G2_TE_URLS[countryId] ?? null
  if (indicatorId === 'G3') return G3_TE_URLS[countryId] ?? null
  return null
}

function buildSourceLabel(source: string | null, seriesId: string | null, indicatorId?: string): string {
  if (indicatorId === 'M3') return '10Y Yield'
  if (!source) return 'Source'
  if (source === 'FRED') return `FRED — ${seriesId}`
  if (source === 'World Bank') return `World Bank — ${seriesId}`
  if (source === 'yfinance') return `Yahoo Finance — ${seriesId}`
  if (source === 'Trading Economics') return 'Trading Economics'
  if (source === 'CBSL') return 'CBSL / Trading Economics'
  if (source === 'manual') return 'Trading Economics'
  return source
}

const CATEGORY_COLOR: Record<string, string> = {
  'Growth':            'text-blue-400',
  'Inflation':         'text-orange-400',
  'Monetary Policy':   'text-purple-400',
  'Labour Market':     'text-cyan-400',
  'Financial Markets': 'text-emerald-400',
  'External Sector':   'text-yellow-400',
  'Commodities':       'text-rose-400',
}

export default async function IndicatorDetailPage({ params }: Props) {
  const { id, country } = await params
  const countryId = country.toUpperCase()

  const [history, peers] = await Promise.all([
    fetchIndicatorHistory(id, countryId).catch(() => null),
    countryId === 'GLOBAL' ? Promise.resolve([]) : fetchPeerReadings(id).catch(() => []),
  ])
  if (!history || history.readings.length === 0) notFound()

  // 52-week (trailing ~52 readings) range for the focus series
  const vals = history.readings.map(r => r.value)
  const rangeMin = Math.min(...vals)
  const rangeMax = Math.max(...vals)
  const rangeSpan = rangeMax - rangeMin || 1
  const latestPos = history.latest !== null ? ((history.latest - rangeMin) / rangeSpan) * 100 : null

  const countryMeta = COUNTRIES.find(c => c.id === countryId)
  const ref = REFERENCE[id]
  const categoryColor = CATEGORY_COLOR[history.category] ?? 'text-zinc-400'
  const sourceUrl = buildSourceUrl(history.source, history.source_series_id, id, countryId)
  const sourceLabel = buildSourceLabel(history.source, history.source_series_id, id)
  const source2Url = id === 'M3' ? (M3_2Y_URLS[countryId] ?? null) : null
  const source2Label = id === 'M3' ? '2Y Yield' : null

  const changePositive = history.change !== null && history.change >= 0
  // Trade Balance currency varies by country (EA=EUR, SG=SGD, others=USD)
  const currency = id === 'E1'
    ? (countryId === 'EA' ? '€' : countryId === 'SG' ? 'S$' : '$')
    : '$'
  const unitLabel = history.unit === 'bn'
    ? (countryId === 'EA' ? 'EUR bn' : countryId === 'SG' ? 'SGD bn' : 'USD bn')
    : history.unit

  return (
    <main className="min-h-screen text-white px-4 py-6 md:px-8 max-w-[1200px] mx-auto w-full overflow-x-clip">
      {/* Back nav */}
      <div className="flex items-center justify-between mb-6">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-zinc-500 hover:text-cyan-300 text-sm transition-colors"
        >
          ← Back to terminal
        </Link>
        <Link
          href="/guide"
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-zinc-800 text-zinc-300 hover:text-cyan-300 hover:border-cyan-700 text-sm transition-colors"
        >
          <span aria-hidden>📘</span> Guide
        </Link>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4 mb-8">
        <div>
          <div className={`text-xs font-semibold uppercase tracking-wider mb-1 ${categoryColor}`}>
            {history.category}
          </div>
          <h1 className="text-2xl font-bold text-white">{history.indicator_name}</h1>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-zinc-400 text-sm">
              {history.country_name ?? 'Global'} · {unitLabel} · {history.frequency}
            </span>
            {countryMeta && (
              <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                countryMeta.classification === 'DM'
                  ? 'bg-blue-900/40 text-blue-400'
                  : 'bg-amber-900/40 text-amber-400'
              }`}>
                {countryMeta.classification}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* RAG badge */}
          {history.ragStatus && (
            <span className={`px-3 py-1 rounded-full text-sm font-semibold capitalize ${RAG_BADGE[history.ragStatus]}`}>
              {history.ragStatus === 'green' ? 'Positive' : history.ragStatus === 'amber' ? 'Watch' : 'Risk'}
            </span>
          )}
          {/* Source link(s) */}
          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm border border-zinc-700 text-zinc-400 hover:text-white hover:border-zinc-500 transition-colors"
            >
              {sourceLabel} ↗
            </a>
          )}
          {source2Url && (
            <a
              href={source2Url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm border border-zinc-700 text-zinc-400 hover:text-white hover:border-zinc-500 transition-colors"
            >
              {source2Label} ↗
            </a>
          )}
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <StatCard
          label="Latest"
          value={history.latest !== null ? formatValue(history.latest, history.unit, true, currency) : '—'}
          sub={history.latestDate ?? ''}
        />
        <StatCard
          label="Previous"
          value={history.previous !== null ? formatValue(history.previous, history.unit, true, currency) : '—'}
        />
        <StatCard
          label="Change"
          value={history.change !== null ? formatValue(history.change, history.unit, true, currency) : '—'}
          positive={history.change !== null ? changePositive : undefined}
        />
        <StatCard
          label="% Change"
          value={history.changePct !== null
            ? `${history.changePct >= 0 ? '+' : ''}${history.changePct.toFixed(2)}%`
            : '—'}
          positive={history.changePct !== null ? history.changePct >= 0 : undefined}
        />
      </div>

      {/* 52-reading range bar */}
      {history.readings.length > 1 && latestPos !== null && (
        <div className="panel rounded-xl px-4 py-3 mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="heading-mono text-[10px] uppercase text-zinc-500">
              Range · last {history.readings.length} readings
            </span>
            <span className="text-[11px] text-zinc-500 tnum">
              {formatValue(rangeMin, history.unit, false, currency)} — {formatValue(rangeMax, history.unit, false, currency)}
            </span>
          </div>
          <div className="relative h-2 rounded-full bg-gradient-to-r from-red-500/30 via-amber-400/30 to-emerald-500/30">
            <div
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-white shadow-lg shadow-cyan-500/30 ring-2 ring-cyan-400"
              style={{ left: `${Math.min(Math.max(latestPos, 0), 100)}%` }}
              title="Current"
            />
          </div>
          <div className="flex justify-between mt-1 text-[10px] text-zinc-600 tnum">
            <span>Low</span>
            <span className="text-cyan-400">Current {history.latest !== null ? formatValue(history.latest, history.unit, false, currency) : ''}</span>
            <span>High</span>
          </div>
        </div>
      )}

      {/* Chart + Peer comparison */}
      <div className={`grid gap-6 mb-8 ${peers.length >= 2 ? 'lg:grid-cols-[1.7fr_1fr]' : 'grid-cols-1'}`}>
      <div className="panel rounded-xl p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-zinc-300">
            Historical — {history.readings.length} data point{history.readings.length !== 1 ? 's' : ''}
          </h2>
          {history.readings.length === 1 ? (
            <span className="text-xs text-zinc-500">
              Last scraped: <span className="text-zinc-300">{history.readings[0]?.date}</span>
              {' '}· More history will appear as the scraper runs weekly
            </span>
          ) : (
            <span className="text-xs text-zinc-600">
              {history.readings[0]?.date} → {history.readings[history.readings.length - 1]?.date}
            </span>
          )}
        </div>
        <TimeSeriesChart
          data={history.readings}
          unit={history.unit}
          ragStatus={history.ragStatus}
          referenceValue={ref?.value}
          referenceLabel={ref?.label}
        />
      </div>

      {peers.length >= 2 && (
        <PeerComparison
          peers={peers}
          unit={history.unit}
          focusCountry={countryId}
          indicatorName={history.indicator_name}
        />
      )}
      </div>

      {/* Data table — last 12 readings, inline editable */}
      <div className="panel rounded-xl p-4">
        <h2 className="text-sm font-semibold text-zinc-300 mb-3">Recent releases</h2>
        <EditableReadingsTable
          readings={history.readings}
          indicatorId={id}
          countryId={history.country_id}
          unit={history.unit}
        />
      </div>
    </main>
  )
}

function StatCard({
  label,
  value,
  sub,
  positive,
}: {
  label: string
  value: string
  sub?: string
  positive?: boolean
}) {
  const valueColor =
    positive === undefined ? 'text-white' :
    positive ? 'text-green-400' : 'text-red-400'

  return (
    <div className="panel panel-hover rounded-xl px-4 py-3">
      <div className="heading-mono text-[10px] uppercase text-zinc-500 mb-1">{label}</div>
      <div className={`text-xl font-bold tnum ${valueColor}`}>{value}</div>
      {sub && <div className="text-zinc-600 text-xs mt-0.5 tnum">{sub}</div>}
    </div>
  )
}
