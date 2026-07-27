import { fmtPayback, fmtUsdCompact, fmtInt } from '../lib/format'
import { useI18n } from '../i18n'
import type { ParetoCandidate, ParetoResult } from '../api'

/**
 * Pareto 决策前沿 —— 帆型 × 网格航速全候选的多目标非支配排序。
 * 散点图（x=年 CO₂ 减排，y=20 年 NPV）+ 排序表；前沿候选高亮，
 * 解释"为什么推荐这个组合"：前沿上的候选任何目标的改进都要付出代价。
 */

const W = 640
const H = 300
const PAD = { left: 64, right: 20, top: 16, bottom: 40 }

function Scatter({
  cands,
  selectedId,
  npvLabel,
  co2Label,
  L,
}: {
  cands: ParetoCandidate[]
  selectedId: string | null
  npvLabel: string
  co2Label: string
  L: (s: string) => string
}) {
  const xs = cands.map((c) => c.annual_co2_reduced_t)
  const ys = cands.map((c) => c.npv_20y_usd)
  const xMin = Math.min(...xs)
  const xMax = Math.max(...xs)
  const yMin = Math.min(...ys)
  const yMax = Math.max(...ys)
  const xSpan = xMax - xMin || 1
  const ySpan = yMax - yMin || 1
  const sx = (v: number) =>
    PAD.left + ((v - xMin) / xSpan) * (W - PAD.left - PAD.right)
  const sy = (v: number) =>
    H - PAD.bottom - ((v - yMin) / ySpan) * (H - PAD.top - PAD.bottom)

  // 前沿点按 CO₂ 升序连成折线，直观呈现"前沿"形状
  const front = cands
    .filter((c) => c.is_front)
    .sort((a, b) => a.annual_co2_reduced_t - b.annual_co2_reduced_t)
  const path = front
    .map((c, i) => `${i === 0 ? 'M' : 'L'}${sx(c.annual_co2_reduced_t)},${sy(c.npv_20y_usd)}`)
    .join(' ')

  const zeroY = yMin < 0 && yMax > 0 ? sy(0) : null

  return (
    <svg
      className="pareto-svg"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`${co2Label} vs ${npvLabel}`}
    >
      <line
        x1={PAD.left} y1={H - PAD.bottom} x2={W - PAD.right} y2={H - PAD.bottom}
        className="pareto-axis"
      />
      <line
        x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={H - PAD.bottom}
        className="pareto-axis"
      />
      {zeroY !== null && (
        <line
          x1={PAD.left} y1={zeroY} x2={W - PAD.right} y2={zeroY}
          className="pareto-zero"
        />
      )}
      <text x={(PAD.left + W - PAD.right) / 2} y={H - 8} className="pareto-axis-label">
        {co2Label} (t)
      </text>
      <text
        x={14} y={(PAD.top + H - PAD.bottom) / 2}
        className="pareto-axis-label"
        transform={`rotate(-90 14 ${(PAD.top + H - PAD.bottom) / 2})`}
      >
        {npvLabel}
      </text>
      {path && <path d={path} className="pareto-front-line" />}
      {cands.map((c) => {
        const x = sx(c.annual_co2_reduced_t)
        const y = sy(c.npv_20y_usd)
        const cls = c.is_front ? 'pareto-pt front' : 'pareto-pt'
        return (
          <g key={c.id}>
            {c.id === selectedId && (
              <circle cx={x} cy={y} r={11} className="pareto-pt-ring" />
            )}
            <circle cx={x} cy={y} r={c.is_front ? 6 : 4.5} className={cls}>
              <title>
                {`${L(c.label)} @ ${c.speed_kn.toFixed(0)} kn\n${npvLabel}: ${fmtUsdCompact(c.npv_20y_usd)}\n${co2Label}: ${fmtInt(c.annual_co2_reduced_t)} t`}
              </title>
            </circle>
            <text x={x} y={y - 10} className="pareto-pt-label">
              {c.speed_kn.toFixed(0)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export default function ParetoFront({
  data,
  loading,
  error,
  selectedSail,
  speed,
}: {
  data: ParetoResult | null
  loading: boolean
  error: string | null
  selectedSail: string
  speed: number
}) {
  const { t, locale } = useI18n()
  const L = (s: string) => t.labels[s] || s

  if (loading) return <div className="card pareto-card">{t.pareto_loading}</div>
  if (error) return <div className="note">{t.pareto_err(error)}</div>
  if (!data || data.candidates.length === 0) return null

  // 当前详细分析选中的候选：同帆型中离滑杆航速最近的网格点
  const sameSail = data.candidates.filter((c) => c.sail === selectedSail)
  const selected = sameSail.length
    ? sameSail.reduce((a, b) =>
        Math.abs(a.speed_kn - speed) <= Math.abs(b.speed_kn - speed) ? a : b)
    : null
  const selectedId = selected ? selected.id : null

  const sorted = [...data.candidates].sort(
    (a, b) => a.pareto_rank - b.pareto_rank || b.npv_20y_usd - a.npv_20y_usd)

  return (
    <div className="card pareto-card">
      <Scatter
        cands={data.candidates}
        selectedId={selectedId}
        npvLabel={t.pareto_npv}
        co2Label={t.pareto_co2}
        L={L}
      />
      <div className="pareto-table-wrap">
        <table className="pareto-table">
          <thead>
            <tr>
              <th>{t.pareto_rank}</th>
              <th />
              <th>{t.pareto_npv}</th>
              {data.robust_npv_available && <th>{t.pareto_robust_npv}</th>}
              <th>{t.pareto_co2}</th>
              <th>{t.pareto_payback}</th>
              <th>{t.pareto_cost}</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((c) => (
              <tr
                key={c.id}
                className={
                  (c.is_front ? 'front' : 'dom')
                  + (c.id === selectedId ? ' selected' : '')
                }
              >
                <td>
                  {c.is_front
                    ? <span className="pareto-badge front">{t.pareto_front}</span>
                    : <span className="pareto-badge">{t.pareto_dominated(c.dominated_by.length)}</span>}
                </td>
                <td className="pareto-name">
                  {L(c.label)} @ {c.speed_kn.toFixed(0)} kn
                  {c.id === selectedId && (
                    <span className="pareto-badge sel">{t.pareto_selected}</span>
                  )}
                </td>
                <td>{fmtUsdCompact(c.npv_20y_usd)}</td>
                {data.robust_npv_available && (
                  <td>
                    {c.npv_20y_p10_usd !== undefined
                      ? fmtUsdCompact(c.npv_20y_p10_usd)
                      : '—'}
                  </td>
                )}
                <td>{fmtInt(c.annual_co2_reduced_t)} t</td>
                <td>{fmtPayback(c.payback_years, locale)}</td>
                <td>{fmtUsdCompact(c.initial_cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="pareto-note">{t.pareto_note}</p>
    </div>
  )
}
