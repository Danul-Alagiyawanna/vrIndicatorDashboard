'use client'

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import type { RagStatus } from '@/types/indicators'

interface DataPoint {
  date: string
  value: number
}

interface Props {
  data: DataPoint[]
  unit: string
  ragStatus: RagStatus
  referenceValue?: number   // e.g. 50 for PMI, 0 for yield curve
  referenceLabel?: string
}

const LINE_COLOR: Record<NonNullable<RagStatus>, string> = {
  green: '#22c55e',
  amber: '#f59e0b',
  red:   '#ef4444',
}

function formatAxisDate(dateStr: string, frequency: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' })
}

function formatTooltipDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

function formatAxisValue(value: number, unit: string): string {
  if (unit === '% YoY' || unit === '% WoW' || unit === '%') return `${value.toFixed(1)}%`
  if (unit === 'bps') return `${Math.round(value)}`
  if (unit === 'USD bn') return `$${value.toFixed(0)}bn`
  if (unit === 'USD mn') return `$${Math.round(value)}mn`
  if (unit === 'USD/bbl') return `$${value.toFixed(0)}`
  if (unit === 'Index') return value.toLocaleString(undefined, { maximumFractionDigits: 0 })
  if (unit === 'Rate') return value.toFixed(3)
  return value.toFixed(1)
}

interface TooltipProps {
  active?: boolean
  payload?: { value: number }[]
  label?: string
  unit: string
}

function CustomTooltip({ active, payload, label, unit }: TooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-md px-3 py-2 text-xs shadow-xl">
      <div className="text-zinc-400 mb-1">{label ? formatTooltipDate(label) : ''}</div>
      <div className="text-white font-semibold">{formatAxisValue(payload[0].value, unit)}</div>
      <div className="text-zinc-500">{unit}</div>
    </div>
  )
}

export default function TimeSeriesChart({
  data,
  unit,
  ragStatus,
  referenceValue,
  referenceLabel,
}: Props) {
  if (data.length === 0) return (
    <div className="flex items-center justify-center h-64 text-zinc-600 text-sm">
      No data available
    </div>
  )

  const color = ragStatus ? LINE_COLOR[ragStatus] : '#6b7280'

  // Thin out data for daily series to avoid rendering 500+ ticks
  const thinned = data.length > 200
    ? data.filter((_, i) => i % Math.ceil(data.length / 200) === 0 || i === data.length - 1)
    : data

  // Show ~6 x-axis ticks evenly spaced
  const tickInterval = Math.max(1, Math.floor(thinned.length / 6))
  const xTicks = thinned
    .filter((_, i) => i % tickInterval === 0 || i === thinned.length - 1)
    .map(d => d.date)

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={thinned} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis
          dataKey="date"
          ticks={xTicks}
          tickFormatter={d => formatAxisDate(d, '')}
          tick={{ fill: '#71717a', fontSize: 11 }}
          axisLine={{ stroke: '#3f3f46' }}
          tickLine={false}
        />
        <YAxis
          tickFormatter={v => formatAxisValue(v, unit)}
          tick={{ fill: '#71717a', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={56}
        />
        <Tooltip content={<CustomTooltip unit={unit} />} />
        {referenceValue !== undefined && (
          <ReferenceLine
            y={referenceValue}
            stroke="#52525b"
            strokeDasharray="4 3"
            label={{ value: referenceLabel ?? String(referenceValue), fill: '#71717a', fontSize: 10 }}
          />
        )}
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
          activeDot={{ r: 4, fill: color, strokeWidth: 0 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
