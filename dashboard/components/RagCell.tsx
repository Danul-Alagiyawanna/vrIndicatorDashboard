'use client'

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import type { HeatmapCell } from '@/types/indicators'
import SparklineChart from './SparklineChart'

interface Props {
  cell: HeatmapCell
  dimmed?: boolean
}

const BG: Record<string, string> = {
  green: 'bg-emerald-950/40 glow-green',
  amber: 'bg-amber-950/40 glow-amber',
  red:   'bg-red-950/40 glow-red',
  none:  'bg-zinc-900/40 border border-zinc-800',
}

const DOT: Record<string, string> = {
  green: 'bg-emerald-400',
  amber: 'bg-amber-400',
  red:   'bg-red-500',
}

const POPOVER_W = 224 // px (w-56)

export default function RagCell({ cell, dimmed = false }: Props) {
  const statusKey = cell.ragStatus ?? 'none'
  const bg = BG[statusKey]
  const href = `/indicator/${cell.indicatorId}/${cell.countryId}`

  const [open, setOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [pos, setPos] = useState<{ top: number; left: number; below: boolean } | null>(null)

  const cellRef = useRef<HTMLButtonElement>(null)
  const popRef = useRef<HTMLDivElement>(null)
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const router = useRouter()

  useEffect(() => { setMounted(true) }, [])
  useEffect(() => { router.prefetch(href) }, [href, router]) // instant nav

  // Position the popover relative to the cell, in viewport (fixed) coordinates.
  // Rendered through a portal to document.body so no scroll container can clip it.
  useLayoutEffect(() => {
    if (!open || !cellRef.current) return
    function place() {
      const r = cellRef.current!.getBoundingClientRect()
      const margin = 8
      const estH = 150
      const below = r.top < estH + margin // not enough room above → flip below
      let left = r.left + r.width / 2 - POPOVER_W / 2
      left = Math.max(8, Math.min(left, window.innerWidth - POPOVER_W - 8))
      const top = below ? r.bottom + margin : r.top - margin
      setPos({ top, left, below })
    }
    place()
    window.addEventListener('scroll', place, true)
    window.addEventListener('resize', place)
    return () => {
      window.removeEventListener('scroll', place, true)
      window.removeEventListener('resize', place)
    }
  }, [open])

  // Close on outside tap/click or Escape.
  useEffect(() => {
    if (!open) return
    function onDocDown(e: PointerEvent) {
      const t = e.target as Node
      if (cellRef.current?.contains(t) || popRef.current?.contains(t)) return
      setOpen(false)
    }
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', onDocDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onDocDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  // Desktop hover: open on enter, close a beat after leaving so the pointer can
  // travel into the popover without it vanishing.
  function cancelClose() { if (closeTimer.current) clearTimeout(closeTimer.current) }
  function scheduleClose() {
    cancelClose()
    closeTimer.current = setTimeout(() => setOpen(false), 140)
  }

  const popover = open && pos && mounted ? createPortal(
    <div
      ref={popRef}
      role="dialog"
      onMouseEnter={cancelClose}
      onMouseLeave={scheduleClose}
      style={{
        position: 'fixed',
        top: pos.top,
        left: pos.left,
        width: POPOVER_W,
        transform: pos.below ? undefined : 'translateY(-100%)',
      }}
      className="panel rounded-lg p-3 text-xs text-zinc-200 shadow-2xl z-[100]"
    >
      <div className="font-semibold text-white mb-0.5 leading-tight">{cell.indicatorName}</div>
      <div className="text-zinc-500 text-[11px] mb-2">{cell.countryId} &middot; {cell.unit}</div>

      <div className="space-y-1">
        <div className="flex justify-between"><span className="text-zinc-500">Value</span><span className="text-white tnum">{cell.displayValue}</span></div>
        {cell.date && <div className="flex justify-between"><span className="text-zinc-500">As of</span><span className="text-zinc-300 tnum">{cell.date}</span></div>}
        {cell.wowPct !== null && (
          <div className="flex justify-between">
            <span className="text-zinc-500">WoW</span>
            <span className={`tnum ${cell.wowPct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {cell.wowPct >= 0 ? '+' : ''}{cell.wowPct.toFixed(2)}%
            </span>
          </div>
        )}
      </div>

      <Link
        href={href}
        className="mt-2.5 flex items-center justify-center gap-1.5 rounded-md bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-500/40 text-cyan-300 font-medium py-2 transition-colors"
      >
        View full history →
      </Link>
    </div>,
    document.body,
  ) : null

  return (
    <div className="relative" onMouseEnter={() => { cancelClose(); setOpen(true) }} onMouseLeave={scheduleClose}>
      {/* A tap/click toggles the detail box instead of navigating, so the box
          never hands the tap to the row below it. */}
      <button
        ref={cellRef}
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        className={`rag-cell w-full text-left relative rounded-lg px-2 py-1.5 cursor-pointer block min-h-[52px]
          transition-transform duration-150 ${bg}
          ${open ? 'z-20 scale-[1.04]' : ''}
          ${dimmed ? 'opacity-25 grayscale' : 'opacity-100'}`}
      >
        {cell.ragStatus && (
          <span className={`absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full ${DOT[cell.ragStatus]}`} />
        )}

        <div className="text-white text-xs font-semibold leading-tight truncate tnum pr-2.5">
          {cell.value !== null ? cell.displayValue : <span className="text-zinc-600">—</span>}
        </div>

        {cell.wowPct !== null && (
          <div className={`text-[11px] leading-tight tnum font-medium ${cell.wowPct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {cell.wowPct >= 0 ? '▲' : '▼'} {Math.abs(cell.wowPct).toFixed(2)}%
          </div>
        )}

        {cell.sparkline.length >= 2 && (
          <div className="mt-0.5 -mx-0.5">
            <SparklineChart data={cell.sparkline} ragStatus={cell.ragStatus} />
          </div>
        )}
      </button>

      {popover}
    </div>
  )
}
