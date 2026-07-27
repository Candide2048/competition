import { useEffect, useRef, useState } from 'react'
import { postWindResource, type ScenarioRequest, type WindResourceResult } from '../api'

/** 场景就绪后 → debounce → POST /api/wind-resource（纯查表，秒回）。 */
export function useWindResource(req: ScenarioRequest | null, debounceMs = 250) {
  const [data, setData] = useState<WindResourceResult | null>(null)
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
      postWindResource(req, ac.signal)
        .then((r) => {
          setData(r)
          setError(null)
        })
        .catch((e: unknown) => {
          if ((e as Error).name === 'AbortError') return
          setError((e as Error).message || '计算失败')
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
