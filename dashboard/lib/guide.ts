// ── Indicator reference content for the user guide ─────────────────────────────
// These descriptions mirror the RAG logic in lib/data.ts (computeRag) exactly.
// If a threshold changes there, update the matching entry here.

export interface RagRule {
  green: string
  amber: string
  red: string
}

export interface IndicatorGuide {
  id: string
  name: string
  category: string
  unit: string
  frequency: string
  // Plain-English: what it measures and why an investor cares
  what: string
  why: string
  // How RAG is decided. `rule` is null when the indicator is intentionally
  // left uncoloured (no clean single-value threshold).
  rule: RagRule | null
  note?: string
}

export const CATEGORY_BLURB: Record<string, string> = {
  'Growth':
    'How fast an economy is expanding. Strong growth supports earnings and risk appetite; contraction warns of recession.',
  'Inflation':
    'How fast prices are rising. Moderate inflation is healthy; too high erodes purchasing power and forces central banks to hike rates.',
  'Monetary Policy':
    'The cost of money — policy rates and bond yields. Drives borrowing costs, currency strength, and asset valuations.',
  'Labour Market':
    'The health of employment and wages. A tight labour market supports demand but can stoke wage-driven inflation.',
  'Financial Markets':
    'Real-time market signals — equities, currencies, and credit risk. The fastest-moving read on sentiment.',
  'External Sector':
    'A country’s financial relationship with the rest of the world — trade, reserves, and remittance inflows. Key for currency and default risk.',
  'Commodities':
    'Raw-material prices, led by oil. Feed directly into inflation and shift wealth between exporters and importers.',
}

export const INDICATORS: IndicatorGuide[] = [
  // ── Growth ──────────────────────────────────────────────────────────────────
  {
    id: 'G1', name: 'GDP Growth', category: 'Growth', unit: '% YoY', frequency: 'Quarterly',
    what: 'The yearly change in the total value of everything an economy produces.',
    why: 'The single broadest measure of economic momentum. Expanding output usually means rising profits and jobs.',
    rule: {
      green: 'Developed: ≥ 2.5%  ·  Emerging: ≥ 5%',
      amber: 'Developed: 1–2.5%  ·  Emerging: 3–5%',
      red:   'Developed: < 1%  ·  Emerging: < 3%',
    },
    note: 'Thresholds differ for Developed (DM) vs Emerging (EM) economies — emerging markets are expected to grow faster.',
  },
  {
    id: 'G2', name: 'Manufacturing PMI', category: 'Growth', unit: 'Index', frequency: 'Monthly',
    what: 'A survey of factory purchasing managers. Above 50 means the sector is expanding; below 50, contracting.',
    why: 'A timely, forward-looking gauge of industrial activity — it moves before official output data.',
    rule: { green: '≥ 52 (clear expansion)', amber: '50–52 (marginal growth)', red: '< 50 (contraction)' },
  },
  {
    id: 'G3', name: 'Services PMI', category: 'Growth', unit: 'Index', frequency: 'Monthly',
    what: 'The same survey idea as Manufacturing PMI, but for the services sector (the larger part of most modern economies).',
    why: 'Captures momentum in the dominant part of developed economies.',
    rule: { green: '≥ 52 (clear expansion)', amber: '50–52 (marginal growth)', red: '< 50 (contraction)' },
  },
  {
    id: 'G4', name: 'Industrial Production', category: 'Growth', unit: '% YoY', frequency: 'Monthly',
    what: 'The yearly change in output from factories, mines, and utilities.',
    why: 'A hard data check on the manufacturing cycle that confirms (or contradicts) the PMI surveys.',
    rule: { green: '≥ 3%', amber: '0–3%', red: '< 0% (output shrinking)' },
  },

  // ── Inflation ───────────────────────────────────────────────────────────────
  {
    id: 'I1', name: 'Headline CPI', category: 'Inflation', unit: '% YoY', frequency: 'Monthly',
    what: 'The yearly change in the price of a typical basket of consumer goods and services, including food and energy.',
    why: 'The headline measure of inflation that central banks target and households feel.',
    rule: { green: '≤ 4%', amber: '4–8%', red: '> 8%' },
  },
  {
    id: 'I2', name: 'Core CPI', category: 'Inflation', unit: '% YoY', frequency: 'Monthly',
    what: 'Consumer inflation excluding volatile food and energy prices.',
    why: 'Strips out short-term noise to reveal the underlying, persistent inflation trend.',
    rule: { green: '≤ 4%', amber: '4–8%', red: '> 8%' },
  },
  {
    id: 'I3', name: 'Food Inflation', category: 'Inflation', unit: '% YoY', frequency: 'Monthly',
    what: 'The yearly change specifically in food prices.',
    why: 'Especially important in emerging markets, where food is a large share of household spending and a social-stability risk.',
    rule: { green: '≤ 5%', amber: '5–10%', red: '> 10%' },
  },

  // ── Monetary Policy ───────────────────────────────────────────────────────────
  {
    id: 'M1', name: 'Policy Rate', category: 'Monetary Policy', unit: '%', frequency: 'As changed',
    what: 'The benchmark interest rate set by the central bank.',
    why: 'The primary lever for controlling inflation and growth; it anchors all other borrowing costs.',
    rule: null,
    note: 'Left uncoloured: a rate level alone isn’t good or bad — what matters is the direction and context, which a single number can’t capture.',
  },
  {
    id: 'M2', name: '10Y Government Bond Yield', category: 'Monetary Policy', unit: '%', frequency: 'Daily / Weekly',
    what: 'The interest the market demands to lend to the government for 10 years.',
    why: 'A benchmark for long-term borrowing costs and a market read on growth, inflation, and default risk.',
    rule: { green: '≤ 5%', amber: '5–7%', red: '> 7%' },
  },
  {
    id: 'M3', name: 'Yield Curve (10Y − 2Y)', category: 'Monetary Policy', unit: 'bps', frequency: 'Weekly',
    what: 'The gap between long-term (10-year) and short-term (2-year) bond yields, in basis points.',
    why: 'A classic recession warning: when it turns negative (inverted), a downturn has historically followed.',
    rule: { green: '≥ 50 bps (healthy, upward slope)', amber: '0–50 bps (flat)', red: '< 0 bps (inverted — recession signal)' },
  },

  // ── Labour Market ─────────────────────────────────────────────────────────────
  {
    id: 'L1', name: 'Unemployment Rate', category: 'Labour Market', unit: '%', frequency: 'Monthly',
    what: 'The share of the workforce actively looking for a job but unable to find one.',
    why: 'Low unemployment supports consumer spending; rising unemployment is an early recession sign.',
    rule: { green: '≤ 5%', amber: '5–7%', red: '> 7%' },
  },
  {
    id: 'L2', name: 'Wage Growth', category: 'Labour Market', unit: '% YoY', frequency: 'Monthly',
    what: 'The yearly change in average wages.',
    why: 'Rising wages lift demand but can feed back into inflation — central banks watch it closely.',
    rule: null,
    note: 'Left uncoloured: “good” wage growth depends on the inflation backdrop, so a single threshold would mislead.',
  },

  // ── Financial Markets ──────────────────────────────────────────────────────────
  {
    id: 'F1', name: 'Equity Index', category: 'Financial Markets', unit: '% WoW', frequency: 'Weekly',
    what: 'The week-on-week change in the country’s main stock market index.',
    why: 'The most immediate read on investor sentiment and risk appetite.',
    rule: { green: '≥ +1% on the week', amber: '−1% to +1%', red: '< −1% on the week' },
    note: 'Scored on weekly change (momentum), not the index level.',
  },
  {
    id: 'F2', name: 'FX vs USD', category: 'Financial Markets', unit: '% WoW', frequency: 'Weekly',
    what: 'The week-on-week move in the local currency against the US dollar.',
    why: 'A weakening currency raises import and debt-servicing costs; a stable or strengthening one signals confidence.',
    rule: { green: '≥ 0% (stable or stronger)', amber: '−1% to 0% (mild weakness)', red: '< −1% (notable depreciation)' },
    note: 'Scored on weekly change, not the exchange-rate level.',
  },
  {
    id: 'F3', name: 'Credit Spread / CDS', category: 'Financial Markets', unit: 'bps', frequency: 'Weekly',
    what: 'The extra yield (in basis points) investors demand to hold risky debt over safe government debt.',
    why: 'A direct market price of default and stress risk — it widens fast when fear rises.',
    rule: { green: '≤ 300 bps', amber: '300–600 bps', red: '> 600 bps' },
  },

  // ── External Sector ────────────────────────────────────────────────────────────
  {
    id: 'E1', name: 'Trade Balance', category: 'External Sector', unit: 'USD bn', frequency: 'Monthly',
    what: 'Exports minus imports. Positive = surplus, negative = deficit.',
    why: 'A persistent deficit can pressure the currency and reserves; an improving balance is a tailwind.',
    rule: { green: 'Improving > +2% vs prior reading', amber: 'Roughly flat (−2% to +2%)', red: 'Deteriorating < −2% vs prior reading' },
    note: 'Raw USD levels aren’t comparable across economies, so this is scored on the direction of change vs the previous reading.',
  },
  {
    id: 'E2', name: 'FX Reserves', category: 'External Sector', unit: 'USD bn', frequency: 'Monthly',
    what: 'Foreign currency and gold held by the central bank.',
    why: 'A buffer for defending the currency and paying foreign debt — critical for emerging-market stability.',
    rule: null,
    note: 'Left uncoloured: the meaningful metric is “months of import cover,” not a raw USD figure, which this view doesn’t yet compute.',
  },
  {
    id: 'E3', name: 'Remittances', category: 'External Sector', unit: 'USD mn', frequency: 'Monthly',
    what: 'Money sent home by workers living abroad.',
    why: 'A major, stable source of foreign currency for several emerging economies (notably Sri Lanka).',
    rule: { green: 'Rising > +2% vs prior reading', amber: 'Roughly flat (−2% to +2%)', red: 'Falling < −2% vs prior reading' },
    note: 'Scored on the direction of change vs the previous reading.',
  },

  // ── Commodities ────────────────────────────────────────────────────────────────
  {
    id: 'C1', name: 'Brent Crude Oil', category: 'Commodities', unit: 'USD/bbl', frequency: 'Weekly',
    what: 'The price of a barrel of Brent crude, the global oil benchmark.',
    why: 'Oil feeds straight into inflation and transfers wealth between exporters and importers — a master macro variable.',
    rule: { green: '≤ $80 (subdued)', amber: '$80–$100 (mid-range)', red: '> $100 (elevated, inflationary)' },
  },
]

// Order categories the same way the dashboard does.
export const GUIDE_CATEGORY_ORDER = [
  'Growth', 'Inflation', 'Monetary Policy', 'Labour Market',
  'Financial Markets', 'External Sector', 'Commodities',
] as const
