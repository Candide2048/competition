import { useEffect, useState } from 'react'
import { reduceMotion } from '../lib/format'
import { estimateCiiPenaltyAvoided } from '../lib/cashflow'
import { useI18n } from '../i18n'

const RATING_COLORS: Record<string, string> = {
  A: 'var(--cii-a)',
  B: 'var(--cii-b)',
  C: 'var(--cii-c)',
  D: 'var(--cii-d)',
  E: 'var(--cii-e)',
}

function Pill({ rating, active }: { rating: string; active: boolean }) {
  return (
    <span
      className={`cii-pill ${active ? 'active' : ''}`}
      style={{ '--pill': RATING_COLORS[rating] ?? 'var(--muted)' } as React.CSSProperties}
    >
      {rating}
    </span>
  )
}

/** CII 评级跃迁 + 避免罚款金额估算。 */
export default function CiiBadge({
  baseline,
  withSail,
  improvementPct,
  co2ReducedPerTrip,
  co2Price,
  tripsPerYear,
}: {
  baseline: string
  withSail: string
  improvementPct: number
  co2ReducedPerTrip: number
  co2Price: number
  tripsPerYear: number
}) {
  const [flip, setFlip] = useState(false)
  const { t } = useI18n()

  useEffect(() => {
    if (reduceMotion()) {
      setFlip(true)
      return
    }
    setFlip(false)
    const t = setTimeout(() => setFlip(true), 420)
    return () => clearTimeout(t)
  }, [baseline, withSail])

  const penaltyAvoided = estimateCiiPenaltyAvoided(
    baseline,
    co2ReducedPerTrip,
    co2Price,
    tripsPerYear,
  )

  return (
    <div className="cii-badge">
      <Pill rating={baseline} active={false} />
      <svg className="cii-arrow" width="34" height="16" viewBox="0 0 34 16" aria-hidden>
        <path
          d="M2 8 H28 M22 3 L29 8 L22 13"
          fill="none"
          stroke="var(--accent)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <div className={`cii-flip ${flip ? 'done' : ''}`}>
        <Pill rating={withSail} active={flip} />
      </div>
      <div>
        <span className="cii-imp">{t.cii_improve(improvementPct.toFixed(1))}</span>
        {penaltyAvoided > 0 && (
          <span className="cii-penalty">
            {t.cii_penalty(Math.round(penaltyAvoided / 1000).toLocaleString('en-US'))}
          </span>
        )}
      </div>
    </div>
  )
}
