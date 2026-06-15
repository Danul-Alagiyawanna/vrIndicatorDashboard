'use client'

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Link from 'next/link'
import SparklineChart from './SparklineChart'
import type { HeatmapCell } from '@/types/indicators'

interface Props {
  cell: HeatmapCell
}

const POPOVER_W = 232

const RAG_BG: Record<string, string> = {
  green: 'bg-emerald-950/50 border-emerald-700/40',
  amber: 'bg-amber-950/50 border-amber-600/40',
  red:   'bg-red-950/50 border-red-700/40',
  none:  'bg-zinc-900/50 border-zinc-700/40',
}
const RAG_LABEL: Record<string, string> = {
  green: 'text-emerald-400',
  amber: 'text-amber-300',
  red:   'text-red-400',
  none:  'text-zinc-400',
}
const RAG_DOT: Record<string, string> = {
  green: 'bg-emerald-400',
  amber: 'bg-amber-400',
  red:   'bg-red-500',
  none:  'bg-zinc-600',
}
const REGIME: Record<string, string> = {
  green: 'Subdued',
  amber: 'Mid-range',
  red:   'Elevated',
}

export default function BrentCrudeSignal({ cell }: Props) {
  const statusKey = cell.ragStatus ?? 'none'
  const href = `/indicator/C1/GLOBAL`

  const [open, setOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [pos, setPos] = useState<{ top: number; left: number; below: boolean } | null>(null)

  const tileRef = useRef<HTMLButtonElement>(null)
  const popRef  = useRef<HTMLDivElement>(null)
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => { setMounted(true) }, [])

  useLayoutEffect(() => {
    if (!open || !tileRef.current) return
    function place() {
      const r = tileRef.current!.getBoundingClientRect()
      const margin = 8
      const estH = 200
      const below = r.top < estH + margin
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

  useEffect(() => {
    if (!open) return
    function onDocDown(e: PointerEvent) {
      const t = e.target as Node
      if (tileRef.current?.contains(t) || popRef.current?.contains(t)) return
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

  function cancelClose() { if (closeTimer.current) clearTimeout(closeTimer.current) }
  function scheduleClose() {
    cancelClose()
    closeTimer.current = setTimeout(() => setOpen(false), 140)
  }

  const price = cell.value as number
  const wowPct = cell.wowPct

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
        zIndex: 200,
      }}
      className="panel rounded-xl p-3.5 text-xs text-zinc-200 shadow-2xl"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="font-semibold text-white text-sm leading-tight">Brent Crude</div>
          <div className="text-zinc-500 text-[11px]">Global benchmark · USD/bbl</div>
        </div>
        <span className={`w-2 h-2 rounded-full ${RAG_DOT[statusKey]}`} />
      </div>

      {/* Sparkline */}
      {cell.sparkline.length >= 2 && (
        <div className="mb-2 -mx-1">
          <SparklineChart data={cell.sparkline} ragStatus={cell.ragStatus} />
        </div>
      )}

      {/* Stats */}
      <div className="space-y-1 mb-3">
        <div className="flex justify-between">
          <span className="text-zinc-500">Price</span>
          <span className="text-white font-semibold tnum">${price.toFixed(2)}</span>
        </div>
        {wowPct !== null && (
          <div className="flex justify-between">
            <span className="text-zinc-500">WoW</span>
            <span className={`tnum font-medium ${wowPct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {wowPct >= 0 ? '▲ +' : '▼ '}{Math.abs(wowPct).toFixed(2)}%
            </span>
          </div>
        )}
        {cell.date && (
          <div className="flex justify-between">
            <span className="text-zinc-500">As of</span>
            <span className="text-zinc-300 tnum">{cell.date}</span>
          </div>
        )}
        <div className="flex justify-between">
          <span className="text-zinc-500">Regime</span>
          <span className={RAG_LABEL[statusKey]}>{REGIME[statusKey] ?? '—'}</span>
        </div>
      </div>

      <Link
        href={href}
        className="flex items-center justify-center gap-1.5 rounded-md bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/40 text-amber-300 font-medium py-2 transition-colors text-xs"
      >
        View full history →
      </Link>
    </div>,
    document.body,
  ) : null

  return (
    <div
      className="mt-2"
      onMouseEnter={() => { cancelClose(); setOpen(true) }}
      onMouseLeave={scheduleClose}
    >
      <button
        ref={tileRef}
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        className={`w-full text-left rounded-lg border px-2.5 py-1.5 transition-all duration-150 cursor-pointer
          ${RAG_BG[statusKey]}
          ${open ? 'scale-[1.01] shadow-lg' : 'hover:scale-[1.005]'}`}
      >
        <div className="flex items-center justify-between gap-2 mb-1">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${RAG_DOT[statusKey]}`} />
            <span className="text-zinc-100 font-semibold text-sm leading-tight">Brent Crude</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {wowPct !== null && (
              <span className={`text-[11px] font-medium tnum ${wowPct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {wowPct >= 0 ? '▲' : '▼'} {Math.abs(wowPct).toFixed(2)}%
              </span>
            )}
            <span className="text-white font-bold tnum text-sm">${price.toFixed(2)}</span>
          </div>
        </div>
        {cell.sparkline.length >= 2 && (
          <div className="-mx-0.5">
            <SparklineChart data={cell.sparkline} ragStatus={cell.ragStatus} />
          </div>
        )}
      </button>
      {popover}
    </div>
  )
}
