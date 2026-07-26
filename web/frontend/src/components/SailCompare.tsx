import type { RecommendationResult } from '../api'
import { fmtPayback, fmtUsdCompact } from '../lib/format'
import { useI18n } from '../i18n'

export default function SailCompare({
  data,
  loading,
  error,
}: {
  data: RecommendationResult | null
  loading: boolean
  error: string | null
}) {
  const { t, locale } = useI18n()
  const L = (value: string) => t.labels[value] || value

  if (loading) return <div className="recommendation-message">{t.rec_loading}</div>
  if (error) return <div className="recommendation-message recommendation-error">{t.rec_error(error)}</div>
  if (!data) return null

  const leadSail = data.recommended_sail || data.best_candidate
  const lead = data.candidates.find((candidate) => candidate.sail === leadSail)
  const conclusion = data.decision === 'install' && lead
    ? t.rec_install(
        L(lead.label),
        fmtPayback(lead.payback_years, locale),
        fmtUsdCompact(lead.npv_20y_usd),
      )
    : lead
      ? t.rec_no_install(L(lead.label), fmtUsdCompact(lead.npv_20y_usd))
      : t.rec_no_candidate

  return (
    <div className="sail-recommendation">
      <div className={`recommendation-summary ${data.decision}`}>
        <strong>{conclusion}</strong>
        <span>{t.rec_basis}</span>
      </div>
      <div className="sail-compare">
        {data.candidates.map((candidate) => {
          const recommended = candidate.sail === data.recommended_sail
          const bestAvailable = data.decision === 'do_not_install'
            && candidate.sail === data.best_candidate
          return (
            <div
              key={candidate.sail}
              className={`sail-card ${recommended ? 'best' : ''} ${bestAvailable ? 'best-available' : ''}`}
            >
              <div className="sail-card-head">
                {L(candidate.label)}
                {recommended && <span className="sail-tag">{t.rec_recommended}</span>}
                {bestAvailable && <span className="sail-tag muted">{t.rec_best_available}</span>}
              </div>
              <div className="sail-card-metric">
                <span className="sail-card-metric-label">{t.sail_payback}</span>
                <span className="sail-card-metric-value num">
                  {fmtPayback(candidate.payback_years, locale)}
                </span>
              </div>
              <div className="sail-card-metric">
                <span className="sail-card-metric-label">{t.sail_saving}</span>
                <span className="sail-card-metric-value num">{candidate.saving_rate_pct.toFixed(2)}%</span>
              </div>
              <div className="sail-card-metric">
                <span className="sail-card-metric-label">{t.sail_npv20}</span>
                <span className="sail-card-metric-value num">{fmtUsdCompact(candidate.npv_20y_usd)}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
