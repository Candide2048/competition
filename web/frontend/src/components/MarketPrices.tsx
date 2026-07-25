import { useState, useEffect, useCallback, useRef } from 'react'
import { useI18n } from '../i18n'

interface PricePoint {
  value: number
  currency: string
  unit: string
  source: string
  source_url: string
  timestamp: string
  freshness: 'live' | 'cached' | 'static'
  region: string
  note: string
}

interface MarketPricesData {
  fuel_price: PricePoint
  co2_price: PricePoint
  eur_to_usd: PricePoint
  detected_region: string
  detected_timezone: string
  bunker_hub: string
  carbon_market: string
  fetched_at: string
  values: {
    fuel_price_usd_per_kg: number
    co2_price_eur_per_t: number
    eur_to_usd: number
  }
}

function FreshBadge({ freshness }: { freshness: string }) {
  const cls = freshness === 'live' ? 'fresh-live' : freshness === 'cached' ? 'fresh-cached' : 'fresh-static'
  const icon = freshness === 'live' ? '●' : freshness === 'cached' ? '◐' : '○'
  const label = freshness === 'live' ? 'LIVE' : freshness === 'cached' ? 'CACHED' : 'STATIC'
  return <span className={`fresh-badge ${cls}`}>{icon} {label}</span>
}

function PriceRow({ label, point, displayValue }: { label: string; point: PricePoint; displayValue: string }) {
  const [showDetail, setShowDetail] = useState(false)
  const ts = new Date(point.timestamp)
  const timeStr = ts.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })

  return (
    <div className="mp-row" onClick={() => setShowDetail(!showDetail)}>
      <div className="mp-row-main">
        <div className="mp-label">{label}</div>
        <div className="mp-value">
          <b className="num">{displayValue}</b>
          <FreshBadge freshness={point.freshness} />
        </div>
      </div>
      {showDetail && (
        <div className="mp-detail">
          <div className="mp-source">
            {point.source_url ? (
              <a href={point.source_url} target="_blank" rel="noopener noreferrer">{point.source}</a>
            ) : (
              <span>{point.source}</span>
            )}
          </div>
          <div className="mp-meta">
            <span>📍 {point.region}</span>
            <span>🕐 {timeStr}</span>
          </div>
          {point.note && <div className="mp-note">{point.note}</div>}
        </div>
      )}
    </div>
  )
}

export default function MarketPrices({ onApply }: {
  onApply: (fuel: number, co2: number) => void
}) {
  const [data, setData] = useState<MarketPricesData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const autoApplied = useRef(false)
  const { t } = useI18n()

  const fetchPrices = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai'
      const r = await fetch(`/api/prices?timezone=${encodeURIComponent(tz)}`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const json = await r.json() as MarketPricesData
      setData(json)
      // 首次加载自动同步实时价格到 slider（仅一次）
      if (!autoApplied.current) {
        onApply(json.values.fuel_price_usd_per_kg, json.values.co2_price_eur_per_t)
        autoApplied.current = true
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [onApply])

  useEffect(() => { fetchPrices() }, [])

  const handleApply = () => {
    if (!data) return
    onApply(data.values.fuel_price_usd_per_kg, data.values.co2_price_eur_per_t)
  }

  if (error && !data) return null  // 静默失败，不影响主流程

  return (
    <div className="market-prices">
      <div className="mp-header">
        <div className="mp-title">
          <span className="mp-icon">📡</span>
          <span>{t.mp_title ?? 'Market Data'}</span>
        </div>
        <button className="mp-refresh" onClick={fetchPrices} disabled={loading} title={t.mp_refresh ?? 'Refresh'}>
          {loading ? '⟳' : '↻'}
        </button>
      </div>

      {data && (
        <>
          <div className="mp-region">
            <span className="mp-region-icon">🌐</span>
            <span>{data.detected_region === 'asia' ? t.mp_region_asia ?? '亚太区'
              : data.detected_region === 'europe' ? t.mp_region_eu ?? '欧洲区'
              : t.mp_region_am ?? '美洲区'}</span>
            <span className="mp-region-detail">
              ⛽ {data.bunker_hub} · 🏭 {data.carbon_market}
            </span>
          </div>

          <div className="mp-body">
            <PriceRow
              label={t.mp_fuel ?? 'VLSFO'}
              point={data.fuel_price}
              displayValue={`$${data.values.fuel_price_usd_per_kg.toFixed(3)}/kg`}
            />
            <PriceRow
              label={t.mp_co2 ?? 'CO₂'}
              point={data.co2_price}
              displayValue={`€${data.values.co2_price_eur_per_t.toFixed(1)}/t`}
            />
            <PriceRow
              label={t.mp_fx ?? 'EUR/USD'}
              point={data.eur_to_usd}
              displayValue={data.values.eur_to_usd.toFixed(4)}
            />
          </div>

          <button className="mp-apply" onClick={handleApply}>
            {t.mp_apply ?? 'Apply Market Prices'}
          </button>

          <div className="mp-footer">
            <span className="mp-ts">
              {t.mp_updated ?? 'Updated'}: {new Date(data.fetched_at).toLocaleTimeString()}
            </span>
          </div>
        </>
      )}
    </div>
  )
}
