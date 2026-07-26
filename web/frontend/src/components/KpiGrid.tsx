import { useEffect, useRef } from 'react'
import { gsap } from 'gsap'
import SpotlightCard from './SpotlightCard'
import CountNumber from './CountNumber'
import { fmtInt, reduceMotion } from '../lib/format'
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
  const { t } = useI18n()

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
  const profitTone: Kpi['tone'] = profit20y >= 0 ? 'pos' : 'warn'
  const profitFoot =
    profit20y >= 0
      ? t.kpi_profit_earning(breakevenYear?.toFixed(1) ?? '—')
      : breakevenYear
        ? t.kpi_profit_expect(breakevenYear.toFixed(1))
        : t.kpi_profit_none

  const kpis: Kpi[] = [
    {
      label: t.kpi_payback,
      tone: paybackTone,
      node:
        cell.payback_years === null ? (
          <span className="num">{t.kpi_payback_unrecoverable}</span>
        ) : (
          <CountNumber value={cell.payback_years} decimals={1} suffix=" yr" />
        ),
      foot: t.kpi_payback_foot(fmtInt(cell.initial_cost_usd)),
    },
    {
      label: t.kpi_annual,
      tone: 'pos',
      node: <CountNumber value={cell.annual_savings_usd} prefix="$" />,
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
      node: (
        <CountNumber
          value={Math.abs(profit20y)}
          prefix={profit20y >= 0 ? '+$' : '-$'}
          decimals={0}
        />
      ),
      foot: profitFoot,
    },
    {
      label: t.kpi_co2,
      tone: 'accent',
      node: <CountNumber value={cell.co2_reduced_t * trips_per_year} decimals={0} suffix=" t" />,
      foot: t.kpi_co2_foot(cell.co2_reduced_t.toFixed(1)),
    },
    {
      label: t.kpi_cii,
      tone: 'pos',
      node: (
        <span className="num">
          {cell.cii_rating_baseline} → {cell.cii_rating_with_sail}
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
