import { useEffect, useMemo, useState } from 'react'
import { getMatrix, type MatrixResult } from '../api'
import { fmtUsd, fmtPayback } from '../lib/format'

type Metric = 'saving_rate_pct' | 'annual_savings_usd' | 'payback_years'

const METRIC_META: Record<Metric, { label: string; better: 'high' | 'low' }> = {
  saving_rate_pct: { label: '节油率 %', better: 'high' },
  annual_savings_usd: { label: '年净节省 $', better: 'high' },
  payback_years: { label: '回收期 年', better: 'low' },
}

/** 深色主题热力色：暗底 → 紫蓝/翠绿发光，t∈[0,1] 越大越「好」。 */
function heatColor(t: number): string {
  const clamped = Math.max(0, Math.min(1, t))
  // 暗灰蓝 → 紫蓝 → 翠绿
  const r = Math.round(20 + (0 - 20) * clamped)
  const g = Math.round(25 + (200 - 25) * clamped)
  const b = Math.round(45 + (100 - 45) * clamped)
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

  useEffect(() => {
    let alive = true
    setError(null)
    getMatrix({ ship, route, season, fuel_price: fuelPrice, co2_price: co2Price, sea_ratio: seaRatio })
      .then((r) => {
        if (alive) setData(r)
      })
      .catch((e: unknown) => {
        if (alive) setError((e as Error).message || '矩阵加载失败')
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
    return fmtPayback(v)
  }

  if (error) return <div className="matrix card matrix-msg">矩阵加载失败：{error}</div>
  if (!data || !grid) return <div className="matrix card matrix-msg">加载效益矩阵…</div>

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
              {METRIC_META[m].label}
            </button>
          ))}
        </div>
        <span className="matrix-sub">{data.route_name} · {season}</span>
      </div>
      <div
        className="matrix-grid"
        style={{ gridTemplateColumns: `160px repeat(${data.speeds.length}, 1fr)` }}
      >
        <div className="matrix-corner">帆型 \ 航速</div>
        {data.speeds.map((sp) => (
          <div key={sp} className="matrix-colhead num">{sp} kn</div>
        ))}
        {data.sail_labels.map((label, ri) => (
          <FragmentRow
            key={label}
            label={label}
            cells={grid[ri]}
            norm={norm}
            fmtCell={fmtCell}
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
}: {
  label: string
  cells: (number | null)[]
  norm: (v: number | null) => number
  fmtCell: (v: number | null) => string
}) {
  return (
    <>
      <div className="matrix-rowhead">{label}</div>
      {cells.map((v, ci) => {
        const t = norm(v)
        return (
          <div
            key={ci}
            className="matrix-cell num"
            style={{ background: heatColor(t), color: t > 0.4 ? '#fff' : 'var(--muted)' }}
          >
            {fmtCell(v)}
          </div>
        )
      })}
    </>
  )
}
