import { useRef, type ReactNode, type MouseEvent } from 'react'

/** react-bits「SpotlightCard」概念：光斑随鼠标（CSS 径向渐变 + CSS 变量）。 */
export default function SpotlightCard({
  children,
  className = '',
  style,
}: {
  children: ReactNode
  className?: string
  style?: React.CSSProperties
}) {
  const ref = useRef<HTMLDivElement | null>(null)

  const onMove = (e: MouseEvent<HTMLDivElement>) => {
    const el = ref.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    el.style.setProperty('--mx', `${e.clientX - rect.left}px`)
    el.style.setProperty('--my', `${e.clientY - rect.top}px`)
  }

  return (
    <div
      ref={ref}
      className={`spotlight ${className}`}
      style={style}
      onMouseMove={onMove}
    >
      <div className="spotlight-glow" aria-hidden />
      <div className="spotlight-body">{children}</div>
    </div>
  )
}
