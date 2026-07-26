import SplitText from './SplitText'
import type { ScenarioResult, ShipOption, SailOption } from '../api'
import { fmtPayback, fmtUsdCompact } from '../lib/format'
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
  const payback = cell.payback_years
  const negativeEconomics = cell.npv_20y_usd < 0 || payback === null || payback > 20
  const needsValidation = res.quality.guardrail_applied || !res.quality.within_benchmark
  const decision = negativeEconomics
    ? 'negative'
    : payback > 10 || needsValidation
      ? 'conditional'
      : 'positive'
  const decisionLabel = decision === 'negative'
    ? t.decision_state_negative
    : decision === 'conditional'
      ? t.decision_state_conditional
      : t.decision_state_positive

  const reasons: string[] = []
  if (cell.npv_20y_usd < 0) reasons.push(t.decision_npv_negative(fmtUsdCompact(cell.npv_20y_usd)))
  if (payback === null || payback > 20) reasons.push(t.decision_payback_long(payback === null ? null : payback.toFixed(1)))
  if (cell.cii_rating_baseline === cell.cii_rating_with_sail) {
    reasons.push(t.decision_cii_same(cell.cii_rating_with_sail, cell.cii_improvement_pct.toFixed(1)))
  }
  if (res.quality.guardrail_applied) reasons.push(t.decision_guardrail)
  else if (!res.quality.within_benchmark) reasons.push(t.decision_outside_benchmark)
  if (reasons.length === 0) reasons.push(t.decision_positive_reason)

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
      <div className={`decision-state decision-${decision}`}>
        <span className="decision-dot" aria-hidden />
        {decisionLabel}
      </div>
      <SplitText
        key={verdict}
        as="h1"
        className="hero-title num-mix"
        text={verdict}
      />
      <ul className="decision-reasons">
        {reasons.slice(0, 3).map((reason) => <li key={reason}>{reason}</li>)}
      </ul>
      <div className="hero-chips">
        <span className="chip">{L(route_name)}</span>
        <span className="chip">{speed_used.toFixed(0)} kn</span>
        <span className={`chip ${is_live ? 'live' : ''}`}>
          {is_live ? t.chip_live : t.chip_cache}
        </span>
        <span className="chip">
          {t.quality_weather_basis(
            res.quality.weather_years.join(', '),
            res.quality.departure_samples_per_season,
          )}
        </span>
        {!res.quality.uncertainty_interval_available && (
          <span className="chip quality-warning">{t.quality_interval_unavailable}</span>
        )}
      </div>
    </header>
  )
}
