import { useI18n } from '../i18n'
import type { WindResourceResult } from '../api'

/** 单个直方图：CSS 条形行（bins n+1 个边界 → n 行） */
function Hist({
  title,
  bins,
  pct,
  unit,
}: {
  title: string
  bins: number[]
  pct: number[]
  unit: string
}) {
  const max = Math.max(...pct, 1)
  return (
    <div className="wind-hist">
      <h4 className="wind-hist-title">{title}</h4>
      {pct.map((p, i) => (
        <div className="wind-bar-row" key={bins[i]}>
          <span className="wind-bin">{`${bins[i]}–${bins[i + 1]}${unit}`}</span>
          <div className="wind-bar-track">
            <div className="wind-bar" style={{ width: `${(p / max) * 100}%` }} />
          </div>
          <span className="wind-pct">{p.toFixed(1)}%</span>
        </div>
      ))}
    </div>
  )
}

export default function WindResourcePanel({
  data,
  loading,
  error,
}: {
  data: WindResourceResult | null
  loading: boolean
  error: string | null
}) {
  const { t } = useI18n()

  if (loading) return <div className="card wind-card">{t.wind_loading}</div>
  if (error) return <div className="note">{t.wind_err(error)}</div>
  if (!data) return null
  if (!data.available || !data.summary) {
    return <div className="note">{t.wind_unavailable}</div>
  }

  const s = data.summary
  const fit = data.interpretation?.fit_level ?? 'medium'
  const fitLabel =
    fit === 'good' ? t.wind_fit_good : fit === 'poor' ? t.wind_fit_poor : t.wind_fit_medium
  const reasonMap: Record<string, string> = {
    low_wind_dominant: t.wind_reason_low_wind,
    beam_reach_dominant: t.wind_reason_beam,
    headwind_dominant: t.wind_reason_head,
    tailwind_dominant: t.wind_reason_tail,
  }
  const reason = reasonMap[data.interpretation?.main_reason_key ?? ''] ?? ''

  return (
    <div className="card wind-card">
      {/* 适配判级 + 主因 */}
      <div className="wind-head">
        <span className={`wind-fit ${fit}`}>{fitLabel}</span>
        {reason && <span className="wind-reason">{reason}</span>}
      </div>

      {/* 关键占比统计 */}
      <div className="wind-stats">
        <div className="wind-stat">
          <b>{s.mean_true_wind_ms.toFixed(1)} m/s</b>
          <span>{t.wind_mean_true}</span>
        </div>
        <div className="wind-stat">
          <b>{s.mean_apparent_wind_ms.toFixed(1)} m/s</b>
          <span>{t.wind_mean_apparent}</span>
        </div>
        <div className="wind-stat">
          <b>{s.net_saving_contribution_hours_pct.toFixed(1)}%</b>
          <span>{t.wind_net_saving_hours}</span>
        </div>
        <div className="wind-stat">
          <b>{s.low_wind_hours_pct.toFixed(1)}%</b>
          <span>{t.wind_low_wind}</span>
        </div>
      </div>

      {/* 双直方图 */}
      <div className="wind-hists">
        <Hist
          title={t.wind_speed_dist}
          bins={s.wind_speed_hist.bins}
          pct={s.wind_speed_hist.pct}
          unit=" m/s"
        />
        <Hist
          title={t.wind_angle_dist}
          bins={s.relative_angle_hist.bins_deg}
          pct={s.relative_angle_hist.pct}
          unit="°"
        />
      </div>

      <p className="wind-note">
        {t.wind_basis(data.basis?.weather_years?.join('/') ?? '2025')}
      </p>
    </div>
  )
}
