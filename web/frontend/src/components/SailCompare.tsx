import { useEffect, useState } from 'react'
import { getMatrix, type MatrixResult } from '../api'
import { fmtInt } from '../lib/format'
import { useI18n } from '../i18n'

/**
 * 三帆型横向 PK —— 同条件下比较回收期/节油率/年净节省。
 * 数据源：/api/matrix 取三帆型在当前航速对应的网格速度列。
 */
export default function SailCompare({
  ship,
  route,
  season,
  fuelPrice,
  co2Price,
  seaRatio,
  fuelType,
  ciiYear,
  currentSpeed,
}: {
  ship: string
  route: string
  season: string
  fuelPrice: number
  co2Price: number
  seaRatio: number
  fuelType: string
  ciiYear: number
  currentSpeed: number
}) {
  const [data, setData] = useState<MatrixResult | null>(null)
  const { t } = useI18n()
  const L = (s: string) => t.labels[s] || s

  useEffect(() => {
    let alive = true
    getMatrix({
      ship,
      route,
      season,
      fuel_price: fuelPrice,
      co2_price: co2Price,
      sea_ratio: seaRatio,
      fuel_type: fuelType,
      cii_year: ciiYear,
    })
      .then((r) => { if (alive) setData(r) })
      .catch(() => {})
    return () => { alive = false }
  }, [ship, route, season, fuelPrice, co2Price, seaRatio, fuelType, ciiYear])

  if (!data) return null

  // Find the column index closest to currentSpeed
  const speedIdx = data.speeds.reduce(
    (best, sp, i) => (Math.abs(sp - currentSpeed) < Math.abs(data.speeds[best] - currentSpeed) ? i : best),
    0,
  )

  // Build comparison data for each sail type
  const sails = data.sail_labels.map((label, ri) => ({
    label,
    saving: data.saving_rate_pct[ri][speedIdx],
    annual: data.annual_savings_usd[ri][speedIdx],
    payback: data.payback_years[ri][speedIdx],
  }))

  // Determine "best" = shortest finite payback
  const validPaybacks = sails
    .map((s, i) => ({ idx: i, pb: s.payback }))
    .filter((x) => x.pb !== null && Number.isFinite(x.pb))
  const bestIdx = validPaybacks.length > 0
    ? validPaybacks.reduce((a, b) => (a.pb! < b.pb! ? a : b)).idx
    : -1


  return (
    <div className="sail-compare">
      {sails.map((s, i) => (
        <div key={s.label} className={`sail-card ${i === bestIdx ? 'best' : ''}`}>
          <div className="sail-card-head">{L(s.label)}</div>
          <div className="sail-card-metric">
            <span className="sail-card-metric-label">{t.sail_payback}</span>
            <span className="sail-card-metric-value num">
              {s.payback === null ? '—' : `${s.payback.toFixed(1)} yr`}
            </span>
          </div>
          <div className="sail-card-metric">
            <span className="sail-card-metric-label">{t.sail_saving}</span>
            <span className="sail-card-metric-value num">{s.saving.toFixed(2)}%</span>
          </div>
          <div className="sail-card-metric">
            <span className="sail-card-metric-label">{t.sail_annual}</span>
            <span className="sail-card-metric-value num">${fmtInt(s.annual)}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
