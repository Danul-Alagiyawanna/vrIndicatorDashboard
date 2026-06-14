'use client'

import { useState, useTransition } from 'react'
import Link from 'next/link'
import { upsertReading } from './actions'
import type { UpsertResult } from './actions'

// ── Indicator + country reference data ────────────────────────────────────────

const INDICATORS = [
  { id: 'G1', name: 'G1 — GDP Growth', global: false },
  { id: 'G2', name: 'G2 — Mfg PMI',   global: false },
  { id: 'G3', name: 'G3 — Svc PMI',   global: false },
  { id: 'G4', name: 'G4 — Industrial Production', global: false },
  { id: 'I1', name: 'I1 — CPI',        global: false },
  { id: 'I2', name: 'I2 — Core CPI',   global: false },
  { id: 'I3', name: 'I3 — PPI',        global: false },
  { id: 'M1', name: 'M1 — Policy Rate', global: false },
  { id: 'M2', name: 'M2 — 10Y Yield',  global: false },
  { id: 'M3', name: 'M3 — Yield Curve (10Y-2Y)', global: false },
  { id: 'L1', name: 'L1 — Unemployment Rate', global: false },
  { id: 'L2', name: 'L2 — Wage Growth', global: false },
  { id: 'F1', name: 'F1 — Equity Index', global: false },
  { id: 'F2', name: 'F2 — FX Rate',      global: false },
  { id: 'F3', name: 'F3 — Credit Spreads (HY OAS)', global: false },
  { id: 'E1', name: 'E1 — Trade Balance', global: false },
  { id: 'E2', name: 'E2 — Current Account', global: false },
  { id: 'E3', name: 'E3 — FX Reserves',    global: false },
  { id: 'C1', name: 'C1 — Brent Crude',    global: true  },
]

const COUNTRIES = [
  { id: 'US', name: 'United States' },
  { id: 'EA', name: 'Euro Area' },
  { id: 'SG', name: 'Singapore' },
  { id: 'CN', name: 'China' },
  { id: 'IN', name: 'India' },
  { id: 'SL', name: 'Sri Lanka' },
]

// ── PMI source URLs per country ───────────────────────────────────────────────

const G2_URLS: Record<string, string> = {
  US: 'https://tradingeconomics.com/united-states/manufacturing-pmi',
  EA: 'https://tradingeconomics.com/euro-area/manufacturing-pmi',
  SG: 'https://tradingeconomics.com/singapore/manufacturing-pmi',
  CN: 'https://tradingeconomics.com/china/manufacturing-pmi',
  IN: 'https://tradingeconomics.com/india/manufacturing-pmi',
  SL: 'https://tradingeconomics.com/sri-lanka/manufacturing-pmi',
}

const G3_URLS: Record<string, string> = {
  US: 'https://tradingeconomics.com/united-states/non-manufacturing-pmi',
  EA: 'https://tradingeconomics.com/euro-area/services-pmi',
  SG: 'https://tradingeconomics.com/singapore/composite-pmi',
  CN: 'https://tradingeconomics.com/china/non-manufacturing-pmi',
  IN: 'https://tradingeconomics.com/india/services-pmi',
  SL: 'https://tradingeconomics.com/sri-lanka/services-pmi',
}

function getPmiSourceUrl(indicatorId: string, countryId: string): string | null {
  if (indicatorId === 'G2') return G2_URLS[countryId] ?? null
  if (indicatorId === 'G3') return G3_URLS[countryId] ?? null
  return null
}

// ── Log entry stored in component state ──────────────────────────────────────

interface LogEntry {
  ts: string
  success: boolean
  message: string
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const [log, setLog] = useState<LogEntry[]>([])
  const [isPending, startTransition] = useTransition()

  const [selectedIndicator, setSelectedIndicator] = useState('G1')
  const [selectedCountry, setSelectedCountry]     = useState('US')
  const isGlobal   = INDICATORS.find(i => i.id === selectedIndicator)?.global ?? false
  const pmiSource  = getPmiSourceUrl(selectedIndicator, selectedCountry)

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    // Inject the PMI source URL automatically so the detail page can link back to TE
    if (pmiSource) fd.set('source_series_id', pmiSource)
    const form = e.currentTarget
    startTransition(async () => {
      const result: UpsertResult = await upsertReading(fd)
      setLog(prev => [
        { ts: new Date().toLocaleTimeString(), ...result },
        ...prev,
      ])
      if (result.success) {
        ;(form.elements.namedItem('date') as HTMLInputElement).value = ''
        ;(form.elements.namedItem('value') as HTMLInputElement).value = ''
        ;(form.elements.namedItem('notes') as HTMLInputElement).value = ''
      }
    })
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-white px-4 py-6 md:px-8">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-zinc-500 hover:text-zinc-200 text-sm mb-6 transition-colors"
      >
        ← Back to dashboard
      </Link>

      <h1 className="text-2xl font-bold text-white mb-1">Manual Data Entry</h1>
      <p className="text-zinc-500 text-sm mb-8">
        Insert or overwrite a reading in the database. Existing rows for the same
        indicator / country / date are updated in place.
      </p>

      <div className="grid gap-8 lg:grid-cols-[480px_1fr]">
        {/* ── Form ── */}
        <form
          onSubmit={handleSubmit}
          className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-6 space-y-5"
        >
          {/* Indicator */}
          <Field label="Indicator">
            <select
              name="indicator_id"
              value={selectedIndicator}
              onChange={e => setSelectedIndicator(e.target.value)}
              className={selectClass}
              required
            >
              {INDICATORS.map(ind => (
                <option key={ind.id} value={ind.id}>
                  {ind.name}
                </option>
              ))}
            </select>
          </Field>

          {/* Country — hidden for global indicators (C1) */}
          {isGlobal ? (
            <>
              <input type="hidden" name="country_id" value="" />
              <div className="text-xs text-zinc-500 -mt-2">
                This is a global series — no country required.
              </div>
            </>
          ) : (
            <Field label="Country">
              <select
                name="country_id"
                className={selectClass}
                required
                value={selectedCountry}
                onChange={e => setSelectedCountry(e.target.value)}
              >
                {COUNTRIES.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.id})
                  </option>
                ))}
              </select>
            </Field>
          )}

          {/* Source link — shown for G2/G3 to let you verify the value before entering */}
          {pmiSource && (
            <div className="flex items-center gap-2 -mt-2">
              <span className="text-xs text-zinc-500">Source:</span>
              <a
                href={pmiSource}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-400 hover:text-blue-300 underline underline-offset-2 truncate"
              >
                {pmiSource} ↗
              </a>
            </div>
          )}

          {/* Date */}
          <Field label="Date" hint="YYYY-MM-DD">
            <input
              type="date"
              name="date"
              className={inputClass}
              required
              placeholder="YYYY-MM-DD"
            />
          </Field>

          {/* Value */}
          <Field label="Value">
            <input
              type="number"
              name="value"
              step="any"
              className={inputClass}
              required
              placeholder="e.g. 2.5"
            />
          </Field>

          {/* Notes (optional) */}
          <Field label="Notes" hint="optional">
            <input
              type="text"
              name="notes"
              className={inputClass}
              placeholder="e.g. revised estimate, source: IMF"
            />
          </Field>

          <button
            type="submit"
            disabled={isPending}
            className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm transition-colors"
          >
            {isPending ? 'Saving…' : 'Save Reading'}
          </button>
        </form>

        {/* ── Activity log ── */}
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-zinc-400 mb-4">
            Activity Log
          </h2>

          {log.length === 0 ? (
            <p className="text-zinc-600 text-sm">No entries yet.</p>
          ) : (
            <ul className="space-y-2">
              {log.map((entry, i) => (
                <li
                  key={i}
                  className={`flex gap-3 text-sm rounded-lg px-3 py-2 ${
                    entry.success
                      ? 'bg-green-900/20 border border-green-800/50'
                      : 'bg-red-900/20 border border-red-800/50'
                  }`}
                >
                  <span className="text-zinc-500 shrink-0">{entry.ts}</span>
                  <span className={entry.success ? 'text-green-400' : 'text-red-400'}>
                    {entry.success ? '✓' : '✗'}
                  </span>
                  <span className={entry.success ? 'text-zinc-300' : 'text-red-300'}>
                    {entry.message}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </main>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="block text-sm text-zinc-400 mb-1.5">
        {label}
        {hint && <span className="text-zinc-600 ml-1.5 text-xs">({hint})</span>}
      </label>
      {children}
    </div>
  )
}

const inputClass =
  'w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500'

const selectClass =
  'w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500'
