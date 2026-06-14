'use client'

import { useState, useTransition } from 'react'
import { upsertReading, deleteReading } from '@/app/admin/actions'
import { formatValue } from '@/lib/data'

interface Row {
  date: string
  value: number
}

interface Props {
  readings: Row[]
  indicatorId: string
  countryId: string | null
  unit: string
}

export default function EditableReadingsTable({
  readings,
  indicatorId,
  countryId,
  unit,
}: Props) {
  const [editingDate, setEditingDate] = useState<string | null>(null)
  const [editValue, setEditValue]     = useState('')
  const [toast, setToast]             = useState<{ ok: boolean; msg: string } | null>(null)
  const [isPending, startTransition]  = useTransition()

  const rows = [...readings].reverse().slice(0, 12)

  function openEdit(row: Row) {
    setEditingDate(row.date)
    setEditValue(String(row.value))
  }

  function cancelEdit() {
    setEditingDate(null)
    setEditValue('')
  }

  function showToast(ok: boolean, msg: string) {
    setToast({ ok, msg })
    setTimeout(() => setToast(null), 3500)
  }

  function handleSave(date: string) {
    const fd = new FormData()
    fd.set('indicator_id', indicatorId)
    fd.set('country_id',   countryId ?? '')
    fd.set('date',         date)
    fd.set('value',        editValue)
    startTransition(async () => {
      const res = await upsertReading(fd)
      showToast(res.success, res.message)
      if (res.success) cancelEdit()
    })
  }

  function handleDelete(date: string) {
    if (!confirm(`Delete reading for ${date}?`)) return
    const fd = new FormData()
    fd.set('indicator_id', indicatorId)
    fd.set('country_id',   countryId ?? '')
    fd.set('date',         date)
    startTransition(async () => {
      const res = await deleteReading(fd)
      showToast(res.success, res.message)
      if (res.success) cancelEdit()
    })
  }

  return (
    <div className="relative">
      {/* Toast */}
      {toast && (
        <div
          className={`absolute top-0 right-0 z-10 px-3 py-1.5 rounded-lg text-xs font-medium ${
            toast.ok
              ? 'bg-green-900/80 text-green-300 border border-green-700'
              : 'bg-red-900/80 text-red-300 border border-red-700'
          }`}
        >
          {toast.ok ? '✓' : '✗'} {toast.msg}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800">
              <th className="text-left py-2 text-zinc-500 font-normal">Date</th>
              <th className="text-right py-2 text-zinc-500 font-normal">Value</th>
              <th className="text-right py-2 text-zinc-500 font-normal">Change</th>
              <th className="w-20" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i, arr) => {
              const prev = arr[i + 1]?.value ?? null
              const chg  = prev !== null ? row.value - prev : null
              const isEditing = editingDate === row.date

              return (
                <tr
                  key={row.date}
                  className="border-b border-zinc-800/50 group hover:bg-zinc-800/30"
                >
                  <td className="py-2 text-zinc-400">{row.date}</td>

                  {/* Value cell — inline input when editing */}
                  <td className="py-1 text-right">
                    {isEditing ? (
                      <input
                        type="number"
                        step="any"
                        value={editValue}
                        onChange={e => setEditValue(e.target.value)}
                        autoFocus
                        onKeyDown={e => {
                          if (e.key === 'Enter') handleSave(row.date)
                          if (e.key === 'Escape') cancelEdit()
                        }}
                        className="w-28 bg-zinc-700 border border-blue-500 rounded px-2 py-0.5 text-white text-sm text-right focus:outline-none"
                      />
                    ) : (
                      <span className="text-white font-medium">
                        {formatValue(row.value, unit)}
                      </span>
                    )}
                  </td>

                  <td className={`py-2 text-right ${
                    chg === null ? 'text-zinc-600' :
                    chg >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {chg !== null
                      ? `${chg >= 0 ? '+' : ''}${formatValue(chg, unit)}`
                      : '—'}
                  </td>

                  {/* Action buttons */}
                  <td className="py-1 text-right">
                    {isEditing ? (
                      <span className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => handleSave(row.date)}
                          disabled={isPending}
                          className="px-2 py-0.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs disabled:opacity-50"
                        >
                          Save
                        </button>
                        <button
                          onClick={cancelEdit}
                          className="px-2 py-0.5 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-300 text-xs"
                        >
                          Cancel
                        </button>
                      </span>
                    ) : (
                      <span className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => openEdit(row)}
                          className="px-2 py-0.5 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-300 text-xs"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(row.date)}
                          disabled={isPending}
                          className="px-2 py-0.5 rounded bg-red-900/60 hover:bg-red-800/60 text-red-400 text-xs disabled:opacity-50"
                        >
                          Del
                        </button>
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="text-zinc-600 text-xs mt-2">
        Hover a row to edit or delete. Press Enter to save, Escape to cancel.
      </p>
    </div>
  )
}
