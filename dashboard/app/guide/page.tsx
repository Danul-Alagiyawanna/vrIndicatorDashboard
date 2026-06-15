import Link from 'next/link'
import {
  INDICATORS,
  CATEGORY_BLURB,
  GUIDE_CATEGORY_ORDER,
  type IndicatorGuide,
} from '@/lib/guide'

export const metadata = {
  title: 'Methodology & Guide — VR Investments',
  description: 'How the macro dashboard works: indicators, RAG status, and the composite health score explained.',
}

const CATEGORY_COLOR: Record<string, { bar: string; text: string }> = {
  'Growth':            { bar: 'bg-blue-500',    text: 'text-blue-400' },
  'Inflation':         { bar: 'bg-orange-500',  text: 'text-orange-400' },
  'Monetary Policy':   { bar: 'bg-purple-500',  text: 'text-purple-400' },
  'Labour Market':     { bar: 'bg-cyan-500',    text: 'text-cyan-400' },
  'Financial Markets': { bar: 'bg-emerald-500', text: 'text-emerald-400' },
  'External Sector':   { bar: 'bg-yellow-500',  text: 'text-yellow-400' },
  'Commodities':       { bar: 'bg-rose-500',    text: 'text-rose-400' },
}

export default function GuidePage() {
  return (
    <main className="min-h-screen text-white px-4 py-6 md:px-8 max-w-[900px] mx-auto w-full overflow-x-clip">
      {/* Back nav */}
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-zinc-500 hover:text-cyan-300 text-sm mb-6 transition-colors"
      >
        ← Back to terminal
      </Link>

      {/* Hero */}
      <header className="mb-8 rise">
        <div className="heading-mono text-[10px] uppercase text-cyan-400 mb-2">Methodology &amp; Guide</div>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
          How to read this dashboard
        </h1>
        <p className="text-zinc-400 text-sm md:text-base mt-3 leading-relaxed">
          This terminal tracks <strong className="text-white">19 economic indicators</strong> across{' '}
          <strong className="text-white">6 economies</strong> and turns each reading into a simple
          traffic-light signal. No finance background needed — this page explains every part, from a
          single colour to the overall economy score.
        </p>
      </header>

      {/* Quick nav */}
      <nav className="panel rounded-xl p-4 mb-8 rise" style={{ animationDelay: '40ms' }}>
        <div className="heading-mono text-[10px] uppercase text-zinc-500 mb-2.5">On this page</div>
        <div className="flex flex-wrap gap-2">
          {[
            ['#rag', '1 · The RAG traffic light'],
            ['#composite', '2 · The composite health score'],
            ['#regime', '3 · Market regime & signals'],
            ['#indicators', '4 · Every indicator explained'],
            ['#glossary', '5 · Glossary'],
          ].map(([href, label]) => (
            <a key={href} href={href}
              className="text-xs px-2.5 py-1 rounded-lg border border-zinc-800 text-zinc-400 hover:text-cyan-300 hover:border-cyan-700 transition-colors">
              {label}
            </a>
          ))}
        </div>
      </nav>

      {/* 1 · RAG */}
      <Section id="rag" n="1" title="The RAG traffic light">
        <p>
          Every data point is scored with one of four states. <strong className="text-white">RAG</strong> stands
          for <strong className="text-white">R</strong>ed, <strong className="text-white">A</strong>mber,{' '}
          <strong className="text-white">G</strong>reen — the colours of a traffic light.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 my-5">
          <RagExplainer color="emerald" dot="bg-emerald-500" title="Green · Positive"
            body="The indicator is in a healthy range. A supportive backdrop for that part of the economy." />
          <RagExplainer color="amber" dot="bg-amber-400" title="Amber · Watch"
            body="Neither clearly good nor bad — borderline, or showing early signs of strain. Worth monitoring." />
          <RagExplainer color="red" dot="bg-red-500" title="Red · Risk"
            body="The indicator is in a concerning range. A potential headwind or warning sign." />
          <RagExplainer color="zinc" dot="bg-zinc-500" title="Grey · No signal"
            body="No clean traffic-light rule applies (e.g. policy rate), so the cell is left uncoloured rather than guessed." />
        </div>

        <p>
          How a colour is decided depends on the indicator. Most use a fixed{' '}
          <strong className="text-white">level</strong> (e.g. inflation under 4% is green). A few — equities,
          currencies, trade — use the <strong className="text-white">direction of change</strong> instead, because
          their raw level isn’t comparable across countries. The exact rule for each one is in{' '}
          <a href="#indicators" className="text-cyan-400 hover:underline">section 4</a>.
        </p>

        <Callout>
          <strong className="text-white">Why some thresholds differ by country.</strong> Emerging markets (EM)
          are expected to grow faster than developed markets (DM), so GDP growth of 3% is healthy for the US but
          weak for India. Where it matters, the rule is split DM vs EM.
        </Callout>
      </Section>

      {/* 2 · Composite */}
      <Section id="composite" n="2" title="The composite health score">
        <p>
          Each economy on the <Link href="/" className="text-cyan-400 hover:underline">main page</Link> gets a single
          <strong className="text-white"> 0–100 score</strong>. It’s a plain average of its traffic lights, turned
          into points:
        </p>

        <div className="grid grid-cols-3 gap-3 my-5">
          <PointCard dot="bg-emerald-500" label="Green" pts="100" />
          <PointCard dot="bg-amber-400" label="Amber" pts="55" />
          <PointCard dot="bg-red-500" label="Red" pts="12" />
        </div>

        <p className="mb-4">The score is the average of those points across every coloured cell for that country:</p>

        <div className="panel rounded-xl p-4 font-mono text-xs sm:text-sm text-zinc-300 overflow-x-auto mb-5">
          <div className="text-zinc-500 mb-2">// for one country</div>
          <div>score = round( <span className="text-cyan-400">sum of points</span> ÷ <span className="text-cyan-400">number of coloured cells</span> )</div>
        </div>

        <div className="panel rounded-xl p-4 mb-5">
          <div className="heading-mono text-[10px] uppercase text-zinc-500 mb-2">Worked example</div>
          <p className="text-sm text-zinc-300 leading-relaxed">
            Say a country has <span className="text-emerald-400">5 green</span>,{' '}
            <span className="text-amber-300">4 amber</span>, and <span className="text-red-400">3 red</span> (12 coloured cells):
          </p>
          <div className="font-mono text-xs sm:text-sm text-zinc-300 mt-3 leading-relaxed">
            (5×100 + 4×55 + 3×12) ÷ 12<br />
            = (500 + 220 + 36) ÷ 12<br />
            = 756 ÷ 12 = <span className="text-cyan-400 font-bold">63</span>
          </div>
        </div>

        <div className="space-y-2.5 my-5">
          <ScoreBand range="70–100" tone="text-emerald-400" bar="bg-emerald-500" w="100%" label="Healthy — mostly positive signals" />
          <ScoreBand range="45–69" tone="text-amber-300" bar="bg-amber-400" w="60%" label="Mixed — a balance of strengths and concerns" />
          <ScoreBand range="0–44" tone="text-red-400" bar="bg-red-500" w="28%" label="Stressed — risk signals dominate" />
        </div>

        <Callout>
          <strong className="text-white">Two things to keep in mind.</strong> (1) Grey cells with no signal are
          left out of the average entirely — a country is only judged on signals it actually has, shown as the
          green/amber/red tally on each card. (2) Every indicator carries equal weight; a yield-curve inversion
          counts the same as food inflation.
        </Callout>
      </Section>

      {/* 3 · Regime */}
      <Section id="regime" n="3" title="Market regime & key signals">
        <p>
          The <strong className="text-white">Macro Pulse</strong> strip at the top of the dashboard summarises
          everything in one line — the <strong className="text-white">market regime</strong> — based on the share
          of all signals that are red vs green:
        </p>
        <ul className="my-4 space-y-2 text-sm">
          <li className="flex gap-2.5"><span className="text-red-400 font-semibold shrink-0 w-40">Risk-off regime</span><span className="text-zinc-400">a third or more of signals are red</span></li>
          <li className="flex gap-2.5"><span className="text-amber-300 font-semibold shrink-0 w-40">Defensive / late cycle</span><span className="text-zinc-400">a fifth or more are red</span></li>
          <li className="flex gap-2.5"><span className="text-emerald-400 font-semibold shrink-0 w-40">Risk-on / expansion</span><span className="text-zinc-400">half or more are green</span></li>
          <li className="flex gap-2.5"><span className="text-cyan-300 font-semibold shrink-0 w-40">Mixed / transitional</span><span className="text-zinc-400">anything in between</span></li>
        </ul>
        <p>
          <strong className="text-white">Key Signals</strong> highlights specific structural reads the model
          watches for — inverted yield curves, oil above $100, economies with manufacturing in contraction, and
          unusually hot inflation prints. <strong className="text-white">Weekly Movers</strong> ranks the biggest
          week-on-week market moves.
        </p>
      </Section>

      {/* 4 · Indicators */}
      <Section id="indicators" n="4" title="Every indicator explained">
        <p className="mb-5">
          The 19 indicators are grouped into 7 categories. Each card shows what it measures, why it matters, and
          the exact rule used to colour it.
        </p>

        {GUIDE_CATEGORY_ORDER.map(cat => {
          const items = INDICATORS.filter(i => i.category === cat)
          const color = CATEGORY_COLOR[cat]
          return (
            <div key={cat} className="mb-7">
              <div className="flex items-center gap-2 mb-1.5">
                <div className={`w-1 h-4 rounded-full ${color.bar}`} />
                <h3 className={`text-sm font-semibold uppercase tracking-wider ${color.text}`}>{cat}</h3>
              </div>
              <p className="text-zinc-500 text-xs mb-3 leading-relaxed">{CATEGORY_BLURB[cat]}</p>
              <div className="space-y-3">
                {items.map(ind => <IndicatorCard key={ind.id} ind={ind} accent={color.text} />)}
              </div>
            </div>
          )
        })}
      </Section>

      {/* 5 · Glossary */}
      <Section id="glossary" n="5" title="Glossary">
        <dl className="space-y-3.5">
          {GLOSSARY.map(([term, def]) => (
            <div key={term} className="border-b border-zinc-800/50 pb-3 last:border-0">
              <dt className="text-white font-semibold text-sm">{term}</dt>
              <dd className="text-zinc-400 text-sm mt-0.5 leading-relaxed">{def}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <footer className="mt-10 text-center text-[11px] text-zinc-600">
        Sources: FRED · World Bank · Yahoo Finance · Trading Economics · CBSL ·
        RAG thresholds per the VR Investments framework.
      </footer>
    </main>
  )
}

// ── Building blocks ─────────────────────────────────────────────────────────────

function Section({ id, n, title, children }: { id: string; n: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mb-12 scroll-mt-6 rise">
      <div className="flex items-baseline gap-3 mb-4">
        <span className="text-cyan-400/40 font-bold text-2xl tnum">{n}</span>
        <h2 className="text-xl md:text-2xl font-bold tracking-tight">{title}</h2>
      </div>
      <div className="space-y-3 text-zinc-300 text-sm md:text-[15px] leading-relaxed">{children}</div>
    </section>
  )
}

function RagExplainer({ dot, title, body }: { color: string; dot: string; title: string; body: string }) {
  return (
    <div className="panel rounded-xl p-4">
      <div className="flex items-center gap-2 mb-1.5">
        <span className={`w-2.5 h-2.5 rounded-full ${dot}`} />
        <span className="font-semibold text-white text-sm">{title}</span>
      </div>
      <p className="text-zinc-400 text-xs leading-relaxed">{body}</p>
    </div>
  )
}

function PointCard({ dot, label, pts }: { dot: string; label: string; pts: string }) {
  return (
    <div className="panel rounded-xl p-3 text-center">
      <span className={`inline-block w-2.5 h-2.5 rounded-full ${dot} mb-1.5`} />
      <div className="text-zinc-400 text-xs">{label}</div>
      <div className="text-2xl font-bold text-white tnum">{pts}</div>
      <div className="text-zinc-600 text-[10px]">points</div>
    </div>
  )
}

function ScoreBand({ range, tone, bar, w, label }: { range: string; tone: string; bar: string; w: string; label: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className={`w-16 text-xs font-bold tnum shrink-0 ${tone}`}>{range}</span>
      <div className="flex-1 h-2 rounded-full bg-zinc-800/60 overflow-hidden">
        <div className={`h-full rounded-full ${bar}`} style={{ width: w }} />
      </div>
      <span className="hidden sm:block text-xs text-zinc-400 w-64 shrink-0">{label}</span>
    </div>
  )
}

function Callout({ children }: { children: React.ReactNode }) {
  return (
    <div className="panel rounded-xl p-4 border-l-2 border-l-cyan-500/60 text-sm text-zinc-300 leading-relaxed my-5">
      {children}
    </div>
  )
}

function RuleRow({ dot, label, text }: { dot: string; label: string; text: string }) {
  return (
    <div className="flex items-start gap-2 text-xs">
      <span className={`mt-1 w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />
      <span className="text-zinc-500 w-12 shrink-0">{label}</span>
      <span className="text-zinc-300">{text}</span>
    </div>
  )
}

function IndicatorCard({ ind, accent }: { ind: IndicatorGuide; accent: string }) {
  return (
    <div className="panel rounded-xl p-4">
      <div className="flex items-baseline gap-2 flex-wrap mb-2">
        <span className={`font-mono text-xs font-bold ${accent}`}>{ind.id}</span>
        <h4 className="font-semibold text-white text-sm">{ind.name}</h4>
        <span className="text-zinc-600 text-[11px]">{ind.unit} · {ind.frequency}</span>
      </div>

      <p className="text-zinc-300 text-sm leading-relaxed">{ind.what}</p>
      <p className="text-zinc-500 text-xs mt-1.5 leading-relaxed">
        <span className="text-zinc-400 font-medium">Why it matters: </span>{ind.why}
      </p>

      {ind.rule ? (
        <div className="mt-3 pt-3 border-t border-zinc-800/60 space-y-1.5">
          <RuleRow dot="bg-emerald-500" label="Green" text={ind.rule.green} />
          <RuleRow dot="bg-amber-400" label="Amber" text={ind.rule.amber} />
          <RuleRow dot="bg-red-500" label="Red" text={ind.rule.red} />
        </div>
      ) : (
        <div className="mt-3 pt-3 border-t border-zinc-800/60 flex items-start gap-2 text-xs">
          <span className="mt-1 w-1.5 h-1.5 rounded-full bg-zinc-500 shrink-0" />
          <span className="text-zinc-400">Left uncoloured — no clean traffic-light rule.</span>
        </div>
      )}

      {ind.note && (
        <p className="text-zinc-500 text-[11px] mt-2.5 italic leading-relaxed">{ind.note}</p>
      )}
    </div>
  )
}

const GLOSSARY: [string, string][] = [
  ['Basis point (bps)', 'One hundredth of a percentage point. 100 bps = 1%. Used for interest rates and spreads where small moves matter.'],
  ['YoY (year-on-year)', 'Compared with the same point one year earlier — the standard way to measure inflation and growth, stripping out seasonal effects.'],
  ['WoW (week-on-week)', 'Compared with one week earlier — used for fast-moving market data like equities and currencies.'],
  ['DM / EM', 'Developed Market (e.g. US, Euro Area, Singapore) vs Emerging Market (e.g. China, India, Sri Lanka). EM economies are held to higher growth thresholds.'],
  ['PMI', 'Purchasing Managers’ Index. A survey-based score where above 50 signals expansion and below 50 signals contraction.'],
  ['Yield curve inversion', 'When short-term bond yields rise above long-term yields. Historically one of the most reliable recession warnings.'],
  ['Credit spread / CDS', 'The extra return investors demand for holding risky debt instead of safe government debt. Widening spreads signal rising stress.'],
  ['Sparkline', 'The tiny chart inside each cell showing the recent trend at a glance, without needing to open the full history.'],
]
