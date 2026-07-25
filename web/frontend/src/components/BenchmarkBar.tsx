import { useI18n } from '../i18n'

/** 本场景节油率 vs 实船报道区间（bench.lo–bench.hi），横条对照。 */
export default function BenchmarkBar({
  value,
  lo,
  hi,
  refs,
}: {
  value: number
  lo: number
  hi: number
  refs: string
}) {
  const { t } = useI18n()
  // 坐标轴上限留 15% 余量，保证标记不贴边
  const axisMax = Math.max(hi, value) * 1.15 || 10
  const pct = (v: number) => `${Math.min(100, (v / axisMax) * 100)}%`
  const inRange = value >= lo && value <= hi

  return (
    <div className="bench">
      <div className="bench-track">
        <div
          className="bench-range"
          style={{ left: pct(lo), width: `calc(${pct(hi)} - ${pct(lo)})` }}
        />
        <div
          className={`bench-marker ${inRange ? 'in' : 'out'}`}
          style={{ left: pct(value) }}
        >
          <span className="bench-marker-val num">{value.toFixed(2)}%</span>
        </div>
      </div>
      <div className="bench-scale">
        <span className="num">0</span>
        <span>
          {t.bench_range} <b className="num">{lo}–{hi}%</b>
        </span>
        <span className="num">{axisMax.toFixed(0)}%</span>
      </div>
      <p className="bench-refs">{refs}</p>
    </div>
  )
}
