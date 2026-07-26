import { useEffect, useRef, useState } from 'react'
import { postScenario, type ScenarioRequest, type ScenarioResult } from '../api'

/** 输入变更 → debounce → POST /api/scenario。live 场景首次数秒，故单独 loading 态。 */
export function useScenario(req: ScenarioRequest | null, debounceMs = 250) {
  const [data, setData] = useState<ScenarioResult | null>(null)
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
      postScenario(req, ac.signal)
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
