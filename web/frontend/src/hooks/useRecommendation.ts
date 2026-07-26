import { useEffect, useRef, useState } from 'react'
import {
  postRecommendation,
  type RecommendationResult,
  type ScenarioRequest,
} from '../api'

/** Run cross-sail ranking only after the selected scenario has completed. */
export function useRecommendation(req: ScenarioRequest | null, debounceMs = 150) {
  const [data, setData] = useState<RecommendationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const key = req ? JSON.stringify(req) : null

  useEffect(() => {
    abortRef.current?.abort()
    if (!req) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    const timer = setTimeout(() => {
      const controller = new AbortController()
      abortRef.current = controller
      setLoading(true)
      setError(null)
      postRecommendation(req, controller.signal)
        .then((result) => {
          setData(result)
          setError(null)
        })
        .catch((reason: unknown) => {
          if ((reason as Error).name === 'AbortError') return
          setData(null)
          setError((reason as Error).message || '推荐计算失败')
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false)
        })
    }, debounceMs)
    return () => {
      clearTimeout(timer)
      abortRef.current?.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, debounceMs])

  return { data, loading, error }
}
