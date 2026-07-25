import SplitText from './SplitText'
import type { ScenarioResult, ShipOption, SailOption } from '../api'
import { fmtPayback } from '../lib/format'

/** Hero：一句话结论，SplitText 逐字揭示 + 场景 chips。 */
export default function Hero({
  res,
  ship,
  sail,
}: {
  res: ScenarioResult
  ship: ShipOption
  sail: SailOption
}) {
  const { cell, route_name, is_live, speed_used, n_sails } = res

  const verdict = `为 ${ship.label} 加装 ${n_sails} 台${sail.label}，节油 ${cell.saving_rate_pct.toFixed(
    2,
  )}%，CII ${cell.cii_rating_baseline}→${cell.cii_rating_with_sail}，回收 ${fmtPayback(
    cell.payback_years,
  )}。`

  return (
    <header className="hero section">
      <p className="eyebrow">Wind-Assisted Ship Propulsion · 效益决策</p>
      <SplitText
        key={verdict}
        as="h1"
        className="hero-title num-mix"
        text={verdict}
      />
      <div className="hero-chips">
        <span className="chip">{route_name}</span>
        <span className="chip">{speed_used.toFixed(0)} kn</span>
        <span className={`chip ${is_live ? 'live' : ''}`}>
          {is_live ? '实时物理重算 (live)' : '预计算网格 (缓存)'}
        </span>
      </div>
    </header>
  )
}
