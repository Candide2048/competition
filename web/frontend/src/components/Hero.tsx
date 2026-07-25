import SplitText from './SplitText'
import type { ScenarioResult, ShipOption, SailOption } from '../api'
import { fmtPayback } from '../lib/format'
import { useI18n } from '../i18n'

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
  const { t, locale } = useI18n()
  const L = (s: string) => t.labels[s] || s
  const { cell, route_name, is_live, speed_used, n_sails } = res

  const verdict = t.hero_verdict(
    L(ship.label),
    n_sails,
    L(sail.label),
    cell.saving_rate_pct.toFixed(2),
    cell.cii_rating_baseline,
    cell.cii_rating_with_sail,
    fmtPayback(cell.payback_years, locale),
  )

  return (
    <header className="hero section">
      <p className="eyebrow">{t.hero_eyebrow}</p>
      <SplitText
        key={verdict}
        as="h1"
        className="hero-title num-mix"
        text={verdict}
      />
      <div className="hero-chips">
        <span className="chip">{L(route_name)}</span>
        <span className="chip">{speed_used.toFixed(0)} kn</span>
        <span className={`chip ${is_live ? 'live' : ''}`}>
          {is_live ? t.chip_live : t.chip_cache}
        </span>
      </div>
    </header>
  )
}
