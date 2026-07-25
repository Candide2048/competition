import { useEffect, useRef, type ElementType } from 'react'
import { gsap } from 'gsap'
import { reduceMotion } from '../lib/format'

/** react-bits「SplitText」概念：逐词 blur+上移 揭示（GSAP 复刻，非抄源码）。 */
export default function SplitText({
  text,
  className,
  as: Tag = 'h1',
  delay = 0,
}: {
  text: string
  className?: string
  as?: ElementType
  delay?: number
}) {
  const ref = useRef<HTMLElement | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const words = el.querySelectorAll<HTMLElement>('.st-word')
    if (reduceMotion()) {
      gsap.set(words, { opacity: 1, y: 0, filter: 'blur(0px)' })
      return
    }
    const isCjk = !text.includes(' ')
    const ctx = gsap.context(() => {
      gsap.fromTo(
        words,
        { opacity: 0, y: 26, filter: 'blur(8px)' },
        {
          opacity: 1,
          y: 0,
          filter: 'blur(0px)',
          duration: 0.7,
          ease: 'power3.out',
          stagger: isCjk ? 0.022 : 0.055,
          delay,
        },
      )
    }, el)
    return () => ctx.revert()
  }, [text, delay])

  // 英文按词、中文按字切分（中文无空格）
  const byWord = text.includes(' ')
  const words = byWord ? text.split(' ') : Array.from(text)
  return (
    <Tag ref={ref as never} className={className}>
      {words.map((w, i) => (
        <span
          key={i}
          className="st-word"
          style={{ display: 'inline-block', whiteSpace: 'pre' }}
        >
          {w}
          {byWord && i < words.length - 1 ? ' ' : ''}
        </span>
      ))}
    </Tag>
  )
}
