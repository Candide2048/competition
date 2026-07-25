import { useEffect, useRef } from 'react'

/** 顶部 2px 滚动进度条 */
export default function ScrollProgress() {
  const barRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = barRef.current
    if (!el) return

    const update = () => {
      const scrollTop = window.scrollY || document.documentElement.scrollTop
      const scrollH = document.documentElement.scrollHeight - window.innerHeight
      const pct = scrollH > 0 ? Math.min(scrollTop / scrollH, 1) : 0
      el.style.transform = `scaleX(${pct})`
    }

    window.addEventListener('scroll', update, { passive: true })
    update()
    return () => window.removeEventListener('scroll', update)
  }, [])

  return <div className="scroll-progress" ref={barRef} />
}
