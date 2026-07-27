import { useEffect, useRef, useState } from 'react'
import { postUncertainty, type ScenarioRequest, type UncertaintyResult } from '../api'

/** 场景就绪后 → debounce → POST /api/uncertainty（纯查表+算术，秒回）。 */
export function useUncertainty(req: ScenarioRequest | null, debounceMs = 250) {
  const [data, setData] = useState<UncertaintyResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const key = req ? JSON.stringify(req) : null

  useEffect(() => {
    if (!req) return
    abortRef.current?.abort()
    setData(null)
    const t = setTimeout(() => {
      const ac = new AbortController()
      abortRef.current = ac
      setLoading(true)
      setError(null)
      postUncertainty(req, ac.signal)
        .then((r) => {
          setData(r)
          setError(null)
        })
        .catch((e: unknown) => {
          if ((e as Error).name === 'AbortError') return
          setError((e as Error).message ||
            (req.locale === 'zh' ? '计算失败' : 'Computation failed'))
        })
        .finally(() => {
          if (!ac.signal.aborted) setLoading(false)
        })
    }, debounceMs)
    return () => {
      clearTimeout(t)
      abortRef.current?.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, debounceMs])

  return { data, loading, error }
}
