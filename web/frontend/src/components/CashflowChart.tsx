import { useMemo } from 'react'
import { computeCashflow, findBreakevenYear } from '../lib/cashflow'
import { fmtInt } from '../lib/format'
import { useI18n } from '../i18n'

/**
 * 累计现金流 SVG 曲线 —— 标注回本时刻，深色科技风配色。
 */
export default function CashflowChart({
  initialCost,
  annualSavings,
}: {
  initialCost: number
  annualSavings: number
}) {
  const { t } = useI18n()
  const points = useMemo(
    () => computeCashflow(initialCost, annualSavings),
    [initialCost, annualSavings],
  )
  const breakevenYear = findBreakevenYear(points)

  const W = 600
  const H = 200
  const padL = 60
  const padR = 20
  const padT = 20
  const padB = 30
  const plotW = W - padL - padR
  const plotH = H - padT - padB

  const maxYear = points[points.length - 1].year
  const values = points.map((p) => p.cumulative)
  const minVal = Math.min(...values)
  const maxVal = Math.max(...values)
  const valRange = Math.max(maxVal - minVal, 1)

  const toX = (year: number) => padL + (year / maxYear) * plotW
  const toY = (val: number) => padT + plotH - ((val - minVal) / valRange) * plotH

  // Zero line Y position
  const zeroY = toY(0)

  // Build SVG path
  const pathD = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${toX(p.year).toFixed(1)} ${toY(p.cumulative).toFixed(1)}`)
    .join(' ')

  // Gradient area path (fill below/above zero line)
  const areaD = `${pathD} L ${toX(maxYear).toFixed(1)} ${zeroY.toFixed(1)} L ${toX(0).toFixed(1)} ${zeroY.toFixed(1)} Z`

  // Breakeven point coordinates
  const bePt = breakevenYear !== null
    ? { x: toX(breakevenYear), y: toY(0) }
    : null

  // X-axis tick positions (adaptive to maxYear)
  const xTicks: number[] = []
  const step = maxYear <= 20 ? 5 : maxYear <= 30 ? 5 : 10
  for (let yr = 0; yr <= maxYear; yr += step) xTicks.push(yr)
  if (xTicks[xTicks.length - 1] !== maxYear) xTicks.push(maxYear)

  return (
    <div className="cashflow-chart card">
      <svg
        className="cashflow-svg"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <linearGradient id="cf-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(0,255,136,0.2)" />
            <stop offset="100%" stopColor="rgba(0,255,136,0)" />
          </linearGradient>
          <linearGradient id="cf-line-grad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#667eea" />
            <stop offset="100%" stopColor="#00ff88" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {xTicks.map((y) => (
          <line
            key={y}
            x1={toX(y)}
            y1={padT}
            x2={toX(y)}
            y2={padT + plotH}
            stroke="rgba(100,200,255,0.06)"
            strokeWidth="1"
          />
        ))}

        {/* Zero line */}
        <line
          x1={padL}
          y1={zeroY}
          x2={padL + plotW}
          y2={zeroY}
          stroke="rgba(255,255,255,0.15)"
          strokeWidth="1"
          strokeDasharray="4 3"
        />

        {/* Area fill */}
        <path d={areaD} fill="url(#cf-grad)" opacity="0.5" />

        {/* Main line */}
        <path
          d={pathD}
          fill="none"
          stroke="url(#cf-line-grad)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Breakeven marker */}
        {bePt && (
          <>
            <line
              x1={bePt.x}
              y1={padT}
              x2={bePt.x}
              y2={padT + plotH}
              stroke="rgba(0,255,136,0.4)"
              strokeWidth="1"
              strokeDasharray="3 2"
            />
            <circle cx={bePt.x} cy={bePt.y} r="5" fill="#00ff88" opacity="0.9" />
            <circle cx={bePt.x} cy={bePt.y} r="9" fill="none" stroke="#00ff88" strokeWidth="1" opacity="0.4" />
            <text
              x={bePt.x}
              y={padT - 4}
              textAnchor="middle"
              className="cashflow-label"
              fill="#00ff88"
              fontSize="11"
            >
              ✓ {breakevenYear!.toFixed(1)}yr
            </text>
          </>
        )}

        {/* Y axis labels */}
        <text x={padL - 6} y={padT + 4} textAnchor="end" className="cashflow-label">
          ${fmtInt(maxVal / 1e6)}M
        </text>
        <text x={padL - 6} y={zeroY + 4} textAnchor="end" className="cashflow-label">
          $0
        </text>
        <text x={padL - 6} y={padT + plotH + 4} textAnchor="end" className="cashflow-label">
          -${fmtInt(Math.abs(minVal) / 1e6)}M
        </text>

        {/* X axis labels */}
        {xTicks.map((yr) => (
          <text
            key={yr}
            x={toX(yr)}
            y={H - 6}
            textAnchor="middle"
            className="cashflow-label"
          >
            {yr}
          </text>
        ))}

        {/* End point value */}
        <text
          x={toX(maxYear) + 4}
          y={toY(points[points.length - 1].cumulative)}
          textAnchor="start"
          fill={points[points.length - 1].cumulative >= 0 ? '#00ff88' : '#ff4466'}
          fontSize="11"
          fontFamily="var(--font-num)"
          fontWeight="600"
        >
          {points[points.length - 1].cumulative >= 0 ? '+' : ''}
          ${fmtInt(points[points.length - 1].cumulative / 1e6)}M
        </text>
      </svg>

      <div className="cashflow-breakeven">
        {breakevenYear !== null ? (
          <>
            <span>{t.cf_breakeven(breakevenYear.toFixed(1))}</span>
            <span style={{ color: 'var(--muted)', fontWeight: 400 }}>
              {t.cf_note(maxYear)}
            </span>
          </>
        ) : (
          <span style={{ color: 'var(--warn)' }}>
            {t.cf_warn}
          </span>
        )}
      </div>
    </div>
  )
}
