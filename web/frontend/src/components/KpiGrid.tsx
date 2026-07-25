import { useEffect, useRef, useMemo } from 'react'
import { gsap } from 'gsap'
import SpotlightCard from './SpotlightCard'
import CountNumber from './CountNumber'
import { fmtInt, reduceMotion } from '../lib/format'
import { computeCashflow, findBreakevenYear } from '../lib/cashflow'
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

  // 计算 20 年累计收益（正向框架）
  const cashflow = useMemo(
    () => computeCashflow(cell.initial_cost_usd, cell.annual_savings_usd),
    [cell.initial_cost_usd, cell.annual_savings_usd],
  )
  const profit20y = cashflow[cashflow.length - 1].cumulative
  const breakevenYear = findBreakevenYear(cashflow)

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
      ? `第 ${breakevenYear?.toFixed(1) ?? '—'} 年开始盈利`
      : breakevenYear
        ? `预计第 ${breakevenYear.toFixed(1)} 年回本`
        : '20年内未回本，建议调整参数'

  const kpis: Kpi[] = [
    {
      label: '投资回收期',
      tone: paybackTone,
      node:
        cell.payback_years === null ? (
          <span className="num">不可回收</span>
        ) : (
          <CountNumber value={cell.payback_years} decimals={1} suffix=" 年" />
        ),
      foot: `初始投资 $${fmtInt(cell.initial_cost_usd)}`,
    },
    {
      label: '年净节省',
      tone: 'pos',
      node: <CountNumber value={cell.annual_savings_usd} prefix="$" />,
      foot: `${trips_per_year.toFixed(1)} 航次/年 · 含碳价收益`,
    },
    {
      label: '节油率',
      tone: 'accent',
      node: <CountNumber value={cell.saving_rate_pct} decimals={2} suffix="%" />,
      foot: `单航次节油 ${cell.fuel_saved_t.toFixed(1)} t`,
    },
    {
      label: '20年累计收益',
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
      label: '年 CO₂ 减排',
      tone: 'accent',
      node: <CountNumber value={cell.co2_reduced_t * trips_per_year} decimals={0} suffix=" t" />,
      foot: `单航次 ${cell.co2_reduced_t.toFixed(1)} t`,
    },
    {
      label: 'CII 跃迁',
      tone: 'pos',
      node: (
        <span className="num">
          {cell.cii_rating_baseline} → {cell.cii_rating_with_sail}
        </span>
      ),
      foot: `碳强度改善 ${cell.cii_improvement_pct.toFixed(1)}%`,
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
