export type Classification = 'DM' | 'EM'

export type RagStatus = 'green' | 'amber' | 'red' | null

export interface Country {
  id: string
  name: string
  region: string
  classification: Classification
}

export interface Indicator {
  id: string
  category: string
  name: string
  description: string | null
  unit: string
  frequency: string
  period_days: number
  is_global: boolean
}

// Row returned by latest_readings view
export interface LatestReading {
  indicator_id: string
  indicator_name: string
  category: string
  unit: string
  frequency: string
  country_id: string | null
  country_name: string | null
  classification: Classification | null
  date: string
  value: number
  source: string
  source_series_id: string | null
}

// Row returned by weekly_market view
export interface WeeklyMarket {
  indicator_id: string
  country_id: string | null
  week_ending: string
  value: number
  prior_value: number | null
  wow_pct: number | null
  source_series_id: string | null
}

// Raw reading row (for sparklines)
export interface Reading {
  indicator_id: string
  country_id: string | null
  date: string
  value: number
}

// One cell in the heatmap grid
export interface HeatmapCell {
  indicatorId: string
  indicatorName: string
  category: string
  unit: string
  frequency: string
  countryId: string
  value: number | null
  displayValue: string
  date: string | null
  ragStatus: RagStatus
  wowPct: number | null       // for F1/F2/C1 from weekly_market
  sparkline: number[]         // last N values for mini chart
}

export const CATEGORIES = [
  'Growth',
  'Inflation',
  'Monetary Policy',
  'Labour Market',
  'Financial Markets',
  'External Sector',
  'Commodities',
] as const

export type Category = typeof CATEGORIES[number]

export const COUNTRIES: Country[] = [
  { id: 'US', name: 'United States', region: 'North America', classification: 'DM' },
  { id: 'EA', name: 'Euro Area',     region: 'Europe',        classification: 'DM' },
  { id: 'SG', name: 'Singapore',     region: 'Asia',          classification: 'DM' },
  { id: 'CN', name: 'China',         region: 'Asia',          classification: 'EM' },
  { id: 'IN', name: 'India',         region: 'South Asia',    classification: 'EM' },
  { id: 'SL', name: 'Sri Lanka',     region: 'South Asia',    classification: 'EM' },
]

export const COUNTRY_IDS = COUNTRIES.map(c => c.id)
