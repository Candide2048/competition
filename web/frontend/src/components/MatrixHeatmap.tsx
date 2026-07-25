import { useEffect, useMemo, useState } from 'react'
import { getMatrix, type MatrixResult } from '../api'
import { fmtUsd, fmtPayback } from '../lib/format'
import { useI18n } from '../i18n'
import { useTheme } from '../hooks/useTheme'

type Metric = 'saving_rate_pct' | 'annual_savings_usd' | 'payback_years'

const METRIC_META: Record<Metric, { better: 'high' | 'low' }> = {
  saving_rate_pct: { better: 'high' },
  annual_savings_usd: { better: 'high' },
  payback_years: { better: 'low' },
}

/** 深色主题热力色：暗底 → 紫蓝/翠绿发光，t∈[0,1] 越大越「好」。 */
function heatColorDark(t: number): string {
  const clamped = Math.max(0, Math.min(1, t))
  const r = Math.round(20 + (0 - 20) * clamped)
  const g = Math.round(25 + (200 - 25) * clamped)
  const b = Math.round(45 + (100 - 45) * clamped)
  return `rgb(${r}, ${g}, ${b})`
}

/** 亮色主题热力色：浅灰 → 绿色，t∈[0,1] 越大越「好」。 */
function heatColorLight(t: number): string {
  const clamped = Math.max(0, Math.min(1, t))
  const r = Math.round(230 + (30 - 230) * clamped)
  const g = Math.round(235 + (185 - 235) * clamped)
  const b = Math.round(240 + (80 - 240) * clamped)
  return `rgb(${r}, ${g}, ${b})`
}

/**
 * 效益矩阵热力图（自研 CSS 网格，全离线）:
 *   行=帆型、列=网格航速，随 metric 切换着色。数值真源 /api/matrix（后端 postprocess）。
 */
export default function MatrixHeatmap({
  ship,
  route,
  season,
  fuelPrice,
  co2Price,
  seaRatio,
}: {
  ship: string
  route: string
  season: string
  fuelPrice: number
  co2Price: number
  seaRatio: number
}) {
  const [data, setData] = useState<MatrixResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [metric, setMetric] = useState<Metric>('saving_rate_pct')
  const { t, locale } = useI18n()
  const { theme } = useTheme()
  const L = (s: string) => t.labels[s] || s

  const METRIC_LABELS: Record<Metric, string> = {
    saving_rate_pct: t.matrix_saving,
    annual_savings_usd: t.matrix_annual,
    payback_years: t.matrix_payback,
  }

  useEffect(() => {
    let alive = true
    setError(null)
    getMatrix({ ship, route, season, fuel_price: fuelPrice, co2_price: co2Price, sea_ratio: seaRatio })
      .then((r) => {
        if (alive) setData(r)
      })
      .catch((e: unknown) => {
        if (alive) setError((e as Error).message || 'unknown')
      })
    return () => {
      alive = false
    }
  }, [ship, route, season, fuelPrice, co2Price, seaRatio])

  const grid = data ? data[metric] : null
  const { lo, hi } = useMemo(() => {
    if (!grid) return { lo: 0, hi: 1 }
    const flat = grid.flat().filter((v): v is number => v !== null && Number.isFinite(v))
    return { lo: Math.min(...flat), hi: Math.max(...flat) }
  }, [grid])

  const norm = (v: number | null): number => {
    if (v === null || hi === lo) return v === null ? 0 : 0.5
    const t = (v - lo) / (hi - lo)
    return METRIC_META[metric].better === 'high' ? t : 1 - t
  }

  const fmtCell = (v: number | null): string => {
    if (v === null) return '—'
    if (metric === 'saving_rate_pct') return `${v.toFixed(1)}%`
    if (metric === 'annual_savings_usd') return fmtUsd(v)
    return fmtPayback(v, locale)
  }

  if (error) return <div className="matrix card matrix-msg">{t.matrix_err(error)}</div>
  if (!data || !grid) return <div className="matrix card matrix-msg">{t.matrix_loading}</div>

  return (
    <div className="matrix card">
      <div className="matrix-head">
        <div className="matrix-tabs">
          {(Object.keys(METRIC_META) as Metric[]).map((m) => (
            <button
              key={m}
              className={`matrix-tab ${metric === m ? 'on' : ''}`}
              onClick={() => setMetric(m)}
            >
              {METRIC_LABELS[m]}
            </button>
          ))}
        </div>
        <span className="matrix-sub">{L(data.route_name)} · {L(season)}</span>
      </div>
      <div
        className="matrix-grid"
        style={{ gridTemplateColumns: `160px repeat(${data.speeds.length}, 1fr)` }}
      >
        <div className="matrix-corner">{t.matrix_corner}</div>
        {data.speeds.map((sp) => (
          <div key={sp} className="matrix-colhead num">{sp} kn</div>
        ))}
        {data.sail_labels.map((label, ri) => (
          <FragmentRow
            key={label}
            label={L(label)}
            cells={grid[ri]}
            norm={norm}
            fmtCell={fmtCell}
            theme={theme}
          />
        ))}
      </div>
    </div>
  )
}

function FragmentRow({
  label,
  cells,
  norm,
  fmtCell,
  theme,
}: {
  label: string
  cells: (number | null)[]
  norm: (v: number | null) => number
  fmtCell: (v: number | null) => string
  theme: 'dark' | 'light'
}) {
  const heatColor = theme === 'light' ? heatColorLight : heatColorDark
  const textThreshold = theme === 'light' ? 0.6 : 0.4
  return (
    <>
      <div className="matrix-rowhead">{label}</div>
      {cells.map((v, ci) => {
        const t = norm(v)
        return (
          <div
            key={ci}
            className="matrix-cell num"
            style={{ background: heatColor(t), color: t > textThreshold ? '#fff' : 'var(--text)' }}
          >
            {fmtCell(v)}
          </div>
        )
      })}
    </>
  )
}
