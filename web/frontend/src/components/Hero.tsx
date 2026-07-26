import SplitText from './SplitText'
import type { RecommendationResult, ScenarioResult, ShipOption, SailOption } from '../api'
import { fmtPayback, fmtUsdCompact } from '../lib/format'
import { useI18n } from '../i18n'

/** Hero：一句话结论，SplitText 逐字揭示 + 场景 chips。 */
export default function Hero({
  res,
  ship,
  sail,
  recommendation,
  recommendationLoading,
  recommendationError,
}: {
  res: ScenarioResult
  ship: ShipOption
  sail: SailOption
  recommendation: RecommendationResult | null
  recommendationLoading: boolean
  recommendationError: string | null
}) {
  const { t, locale } = useI18n()
  const L = (s: string) => t.labels[s] || s
  const { cell, route_name, speed_used } = res
  const leadSail = recommendation?.recommended_sail || recommendation?.best_candidate
  const lead = recommendation?.candidates.find((candidate) => candidate.sail === leadSail)
  const leadNeedsValidation = Boolean(lead && (lead.guardrail_applied || !lead.within_benchmark))
  const decision = recommendation?.decision === 'do_not_install'
    ? 'negative'
    : lead && (lead.payback_years !== null && lead.payback_years > 10 || leadNeedsValidation)
      ? 'conditional'
      : 'positive'
  const decisionLabel = recommendationLoading && !recommendation
    ? t.rec_loading
    : recommendationError && !recommendation
      ? t.rec_error(recommendationError)
      : decision === 'negative'
        ? t.decision_state_negative
        : decision === 'conditional'
          ? t.decision_state_conditional
          : t.decision_state_positive

  const reasons: string[] = []
  if (recommendation?.decision === 'do_not_install' && lead) {
    reasons.push(t.rec_no_install(L(lead.label), fmtUsdCompact(lead.npv_20y_usd)))
  }
  if (lead?.guardrail_applied) reasons.push(t.decision_guardrail)
  else if (lead && !lead.within_benchmark) reasons.push(t.decision_outside_benchmark)
  if (lead && lead.cii_rating_baseline === lead.cii_rating_with_sail) {
    reasons.push(t.decision_cii_same(lead.cii_rating_with_sail, lead.cii_improvement_pct.toFixed(1)))
  }
  if (lead && reasons.length === 0) reasons.push(t.decision_positive_reason)
  if (!lead) reasons.push(t.rec_basis)

  const verdict = lead && recommendation?.decision === 'install'
    ? t.hero_rec_install(
        L(ship.label),
        lead.n_sails,
        L(lead.label),
        lead.saving_rate_pct.toFixed(2),
        fmtPayback(lead.payback_years, locale),
        fmtUsdCompact(lead.npv_20y_usd),
      )
    : lead
      ? t.hero_rec_no_install(L(ship.label), L(lead.label))
      : recommendationLoading
        ? t.hero_rec_loading(L(ship.label))
        : t.hero_verdict(
            L(ship.label),
            res.n_sails,
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
        {recommendation && (
          <span className="chip">{t.hero_compared(recommendation.candidates.length)}</span>
        )}
        <span className={`chip ${(lead?.is_live ?? res.is_live) ? 'live' : ''}`}>
          {(lead?.is_live ?? res.is_live) ? t.chip_live : t.chip_cache}
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
