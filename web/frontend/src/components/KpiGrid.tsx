import { useEffect, useRef } from 'react'
import { gsap } from 'gsap'
import SpotlightCard from './SpotlightCard'
import CountNumber from './CountNumber'
import { fmtInt, fmtPayback, fmtUsdCompact, reduceMotion } from '../lib/format'
import { useI18n } from '../i18n'
import type { ScenarioResult } from '../api'

interface Kpi {
  label: string
  node: React.ReactNode
  foot?: string
  tone: 'pos' | 'accent' | 'neg' | 'warn' | 'neutral'
}

export default function KpiGrid({ res }: { res: ScenarioResult }) {
  const gridRef = useRef<HTMLDivElement | null>(null)
  const { cell, trips_per_year } = res
  const { t, locale } = useI18n()

  useEffect(() => {
    const el = gridRef.current
    if (!el || reduceMotion()) return
    const cards = el.querySelectorAll<HTMLElement>('.kpi')
    const ctx = gsap.context(() => {
      gsap.fromTo(
        cards,
        { opacity: 0, y: 22 },
        { opacity: 1, y: 0, duration: 0.6, ease: 'power2.out', stagger: 0.07 },
      )
    }, el)
    return () => ctx.revert()
  }, [])

  const profit20y = cell.npv_20y_usd
  const breakevenYear = cell.payback_years

  // 回收期 tone
  const paybackTone: Kpi['tone'] =
    cell.payback_years === null
      ? 'neg'
      : cell.payback_years <= 5
        ? 'pos'
        : cell.payback_years <= 10
          ? 'warn'
          : 'neg'

  // 20年累计收益 tone
  const profitTone: Kpi['tone'] = profit20y >= 0 ? 'pos' : 'neg'
  const profitFoot = profit20y >= 0
    ? t.kpi_profit_earning(breakevenYear?.toFixed(1) ?? '—')
    : t.kpi_profit_none
  const sameCiiGrade = cell.cii_rating_baseline === cell.cii_rating_with_sail

  const kpis: Kpi[] = [
    {
      label: t.kpi_payback,
      tone: paybackTone,
      node: <span className="num">{fmtPayback(cell.payback_years, locale)}</span>,
      foot: t.kpi_payback_foot(fmtInt(cell.initial_cost_usd)),
    },
    {
      label: t.kpi_annual,
      tone: cell.annual_savings_usd >= 0 ? 'pos' : 'neg',
      node: <span className="num">{fmtUsdCompact(cell.annual_savings_usd)}</span>,
      foot: t.kpi_annual_foot(trips_per_year.toFixed(1)),
    },
    {
      label: t.kpi_saving,
      tone: 'accent',
      node: <CountNumber value={cell.saving_rate_pct} decimals={2} suffix="%" />,
      foot: t.kpi_saving_foot(cell.fuel_saved_t.toFixed(1)),
    },
    {
      label: t.kpi_profit,
      tone: profitTone,
      node: <span className="num">{fmtUsdCompact(profit20y)}</span>,
      foot: profitFoot,
    },
    {
      label: t.kpi_co2,
      tone: 'accent',
      node: <CountNumber value={cell.co2_reduced_t * trips_per_year} decimals={0} suffix=" t" />,
      foot: t.kpi_co2_foot(cell.co2_reduced_t.toFixed(1)),
    },
    {
      label: sameCiiGrade ? t.kpi_cii_status : t.kpi_cii_change,
      tone: sameCiiGrade ? 'neutral' : 'pos',
      node: (
        <span className="num">
          {sameCiiGrade
            ? t.kpi_cii_same(cell.cii_rating_with_sail)
            : `${cell.cii_rating_baseline} → ${cell.cii_rating_with_sail}`}
        </span>
      ),
      foot: t.kpi_cii_foot(cell.cii_improvement_pct.toFixed(1)),
    },
  ]

  return (
    <div className="kpi-grid" ref={gridRef}>
      {kpis.map((k) => (
        <SpotlightCard key={k.label} className={`kpi tone-${k.tone}`}>
          <span className="kpi-label">{k.label}</span>
          <span className="kpi-value">{k.node}</span>
          {k.foot && <span className="kpi-foot">{k.foot}</span>}
        </SpotlightCard>
      ))}
    </div>
  )
}
