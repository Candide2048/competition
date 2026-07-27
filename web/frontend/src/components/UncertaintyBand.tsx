import { fmtPayback, fmtUsdCompact } from '../lib/format'
import { useI18n } from '../i18n'
import type { QuantileBand, UncertaintyResult } from '../api'

/**
 * P10/P50/P90 不确定性区间条 —— 预计算 block bootstrap 分位数 + 在线经济联动。
 * available=false（live 场景 / 产物未覆盖）时降级为说明文字，不影响主 KPI。
 */

function BandRow({
  label,
  band,
  fmt,
}: {
  label: string
  band: QuantileBand
  fmt: (v: number) => string
}) {
  const range = band.p90 - band.p10
  const midPct = range > 0 ? ((band.p50 - band.p10) / range) * 100 : 50
  return (
    <div className="unc-row">
      <span className="unc-metric">{label}</span>
      <div className="unc-band">
        <span className="unc-val" style={{ left: 0 }}>{fmt(band.p10)}</span>
        <span
          className="unc-val mid"
          style={{ left: `${midPct}%`, transform: 'translateX(-50%)' }}
        >
          {fmt(band.p50)}
        </span>
        <span className="unc-val" style={{ right: 0 }}>{fmt(band.p90)}</span>
        <div className="unc-track" />
        <div className="unc-range" style={{ left: 0, right: 0 }} />
        <div
          className="unc-median"
          style={{ left: `${midPct}%`, transform: 'translateX(-50%)' }}
        />
      </div>
    </div>
  )
}

function riskColor(p: number) {
  if (p >= 0.7) return 'var(--ok, #00ff88)'
  if (p >= 0.4) return 'var(--warn, #ffb347)'
  return 'var(--bad, #ff4466)'
}

function RiskChip({ label, p }: { label: string; p: number }) {
  return (
    <span className="unc-chip">
      {label}
      <b style={{ color: riskColor(p) }}>{(p * 100).toFixed(1)}%</b>
    </span>
  )
}

export default function UncertaintyBand({
  data,
  loading,
  error,
}: {
  data: UncertaintyResult | null
  loading: boolean
  error: string | null
}) {
  const { t, locale } = useI18n()

  if (loading && !data) {
    return (
      <div className="card unc-card">
        <span className="unc-basis">{t.unc_loading}</span>
      </div>
    )
  }
  if (error) return <div className="note">{t.unc_err(error)}</div>
  if (!data) return null
  if (!data.available || !data.saving_rate_pct) {
    return <div className="note">{t.unc_unavailable}</div>
  }

  const pb = data.payback_years
  const years = (data.basis?.weather_years ?? [2025]).join('/')
  const loc = locale as 'zh' | 'en'

  return (
    <div className="card unc-card">
      <BandRow
        label={t.unc_metric_saving}
        band={data.saving_rate_pct}
        fmt={(v) => `${v.toFixed(2)}%`}
      />
      <BandRow
        label={t.unc_metric_annual}
        band={data.annual_savings_usd!}
        fmt={fmtUsdCompact}
      />
      <BandRow
        label={t.unc_metric_npv}
        band={data.npv_20y_usd!}
        fmt={fmtUsdCompact}
      />

      {pb && (
        <div className="unc-basis">
          {t.unc_payback_label}：{t.unc_payback_cases(
            fmtPayback(pb.p10_case, loc),
            fmtPayback(pb.p50_case, loc),
            fmtPayback(pb.p90_case, loc),
          )}
        </div>
      )}

      {data.risk && (
        <div className="unc-risk">
          <RiskChip label={t.unc_risk_fuel} p={data.risk.prob_positive_fuel_saving} />
          <RiskChip label={t.unc_risk_npv} p={data.risk.prob_positive_npv_20y} />
          {data.risk.prob_within_benchmark !== undefined && (
            <RiskChip label={t.unc_risk_bench} p={data.risk.prob_within_benchmark} />
          )}
        </div>
      )}

      <div className="unc-basis">
        {t.unc_basis(years, data.n_samples ?? 500, data.block_h ?? 24)}
      </div>
    </div>
  )
}
