'use client'

import { AreaChart, Area, ResponsiveContainer } from 'recharts'
import { useId } from 'react'
import type { RagStatus } from '@/types/indicators'

interface Props {
  data: number[]
  ragStatus: RagStatus
}

const STROKE: Record<NonNullable<RagStatus>, string> = {
  green: '#34d399',
  amber: '#fbbf24',
  red:   '#f87171',
}

export default function SparklineChart({ data, ragStatus }: Props) {
  const id = useId().replace(/:/g, '')
  if (data.length < 2) return null

  const color = ragStatus ? STROKE[ragStatus] : '#94a3b8'
  const chartData = data.map((v, i) => ({ v, i }))

  return (
    <ResponsiveContainer width="100%" height={22}>
      <AreaChart data={chartData} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={`spark-${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={1.4}
          fill={`url(#spark-${id})`}
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
