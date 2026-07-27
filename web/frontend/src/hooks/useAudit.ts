import { useEffect, useState } from 'react'
import { getAudit, type AuditResult } from '../api'

/**
 * 模型审计信息：一次性 GET，不依赖任何场景参数。
 * 内容为启动时汇总的静态 metadata，页面生命周期内加载一次即可。
 */
export function useAudit() {
  const [data, setData] = useState<AuditResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    getAudit()
      .then((d) => {
        if (alive) setData(d)
      })
      .catch((e: Error) => {
        if (alive) setError(e.message)
      })
    return () => {
      alive = false
    }
  }, [])

  return { data, error }
}
