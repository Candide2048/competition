import CountUp from 'react-countup'
import { reduceMotion } from '../lib/format'

/** react-countup 真·逐位滚动（补 Streamlit 做不到的效果）。reduced-motion 下直接显示终值。 */
export default function CountNumber({
  value,
  decimals = 0,
  prefix = '',
  suffix = '',
  duration = 1.3,
}: {
  value: number
  decimals?: number
  prefix?: string
  suffix?: string
  duration?: number
}) {
  if (reduceMotion()) {
    return (
      <span className="num">
        {prefix}
        {value.toLocaleString('en-US', {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })}
        {suffix}
      </span>
    )
  }
  return (
    <CountUp
      className="num"
      end={value}
      decimals={decimals}
      duration={duration}
      separator=","
      prefix={prefix}
      suffix={suffix}
      preserveValue
      redraw={false}
    />
  )
}
