'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'

const STORAGE_KEY = 'vri_last_seen'

interface NewEntry {
  indicator_name: string
  indicator_id: string
  country_id: string | null
  country_name: string | null
  date: string
  value: number
  unit: string
}

export default function NewDataBanner() {
  const [entries, setEntries] = useState<NewEntry[]>([])
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    async function check() {
      const lastSeen = localStorage.getItem(STORAGE_KEY)

      // First visit — just record now and show nothing
      if (!lastSeen) {
        localStorage.setItem(STORAGE_KEY, new Date().toISOString())
        return
      }

      // Fetch readings inserted/updated since last visit
      // uses updated_at (auto-set by trigger) so both new inserts and corrected values appear
      const { data, error } = await supabase
        .from('readings')
        .select(`
          indicator_id,
          country_id,
          date,
          value,
          updated_at,
          indicators!inner ( name, unit ),
          countries ( name )
        `)
        .gt('updated_at', lastSeen)
        .order('updated_at', { ascending: false })
        .limit(20)

      if (error || !data || data.length === 0) return

      const newEntries: NewEntry[] = data.map((r: any) => ({
        indicator_id:   r.indicator_id,
        indicator_name: r.indicators?.name ?? r.indicator_id,
        country_id:     r.country_id,
        country_name:   r.countries?.name ?? null,
        date:           r.date,
        value:          r.value,
        unit:           r.indicators?.unit ?? '',
      }))

      setEntries(newEntries)
    }

    check()
  }, [])

  function dismiss() {
    setDismissed(true)
    localStorage.setItem(STORAGE_KEY, new Date().toISOString())
  }

  if (dismissed || entries.length === 0) return null

  return (
    <div className="mx-4 mt-4 md:mx-8 bg-blue-950/60 border border-blue-800/60 rounded-xl px-4 py-3">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <p className="text-blue-300 text-sm font-semibold mb-2">
            {entries.length} new {entries.length === 1 ? 'reading' : 'readings'} since your last visit
          </p>
          <ul className="flex flex-wrap gap-2">
            {entries.slice(0, 10).map((e, i) => (
              <li
                key={i}
                className="text-xs bg-blue-900/40 border border-blue-800/40 rounded-md px-2 py-1 text-blue-200"
              >
                <span className="font-medium">{e.indicator_id}</span>
                {e.country_name ? ` / ${e.country_name}` : ''}
                <span className="text-blue-400 ml-1.5">{e.date}</span>
              </li>
            ))}
            {entries.length > 10 && (
              <li className="text-xs text-blue-500 px-2 py-1">
                +{entries.length - 10} more
              </li>
            )}
          </ul>
        </div>
        <button
          onClick={dismiss}
          className="text-blue-500 hover:text-blue-300 text-lg leading-none shrink-0 mt-0.5"
          aria-label="Dismiss"
        >
          ×
        </button>
      </div>
    </div>
  )
}
