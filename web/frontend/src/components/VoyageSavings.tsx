import SpotlightCard from './SpotlightCard'
import CountNumber from './CountNumber'
import { fmtUsdCompact } from '../lib/format'
import { useI18n } from '../i18n'
import type { ScenarioResult } from '../api'

/** 单航次省钱横幅：船东视角的直观回本感知（KPI 网格上方）。 */
export default function VoyageSavings({ res }: { res: ScenarioResult }) {
  const { cell, trips_per_year } = res
  const { t } = useI18n()
  const voyage = cell.voyage_savings_usd ?? 0
  return (
    <SpotlightCard className={`voyage-banner ${voyage >= 0 ? 'pos' : 'neg'}`}>
      <span className="vb-eyebrow">{t.vs_eyebrow}</span>
      <div className="vb-stats">
        <div className="vb-stat">
          <span className="vb-value num">
            <CountNumber value={cell.fuel_saved_t} decimals={1} suffix=" t" />
          </span>
          <span className="vb-label">{t.vs_fuel}</span>
        </div>
        <span className="vb-sep" aria-hidden>≈</span>
        <div className="vb-stat">
          <span className="vb-value num">{fmtUsdCompact(voyage)}</span>
          <span className="vb-label">{t.vs_money}</span>
        </div>
        <span className="vb-sep" aria-hidden>·</span>
        <div className="vb-stat">
          <span className="vb-value num">
            <CountNumber value={cell.saving_rate_pct} decimals={2} suffix="%" />
          </span>
          <span className="vb-label">{t.vs_rate}</span>
        </div>
      </div>
      <span className="vb-note">
        {t.vs_note(trips_per_year.toFixed(1), fmtUsdCompact(cell.annual_savings_usd))}
      </span>
    </SpotlightCard>
  )
}
