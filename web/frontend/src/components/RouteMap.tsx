import { useEffect, useRef } from 'react'
import { reduceMotion } from '../lib/format'

type LatLon = [number, number]

/**
 * 航线动态绘制（Canvas，全离线，无地图 token）:
 *   - 等距投影把 [lat,lon] 航路点映射到画布
 *   - 进入时航线「画出来」+ 船位沿航线行进 + 航路点辉光
 *   - 柔和海洋渐变 + 经纬网格，bound4blue 亮色克制基调
 */
export default function RouteMap({
  waypoints,
  routeName,
  distanceNm,
  durationH,
  windMs,
}: {
  waypoints: LatLon[]
  routeName: string
  distanceNm: number
  durationH: number
  windMs: number
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || waypoints.length < 2) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const parent = canvas.parentElement!
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const W = parent.clientWidth
    const H = parent.clientHeight
    canvas.width = W * dpr
    canvas.height = H * dpr
    canvas.style.width = `${W}px`
    canvas.style.height = `${H}px`
    ctx.scale(dpr, dpr)

    const lats = waypoints.map((w) => w[0])
    const lons = waypoints.map((w) => w[1])
    const minLat = Math.min(...lats)
    const maxLat = Math.max(...lats)
    const minLon = Math.min(...lons)
    const maxLon = Math.max(...lons)
    const pad = 46
    const spanLat = Math.max(maxLat - minLat, 1)
    const spanLon = Math.max(maxLon - minLon, 1)
    // 保持等比，避免航线拉伸变形
    const scale = Math.min((W - pad * 2) / spanLon, (H - pad * 2) / spanLat)
    const offX = (W - spanLon * scale) / 2
    const offY = (H - spanLat * scale) / 2
    const project = (lat: number, lon: number): [number, number] => [
      offX + (lon - minLon) * scale,
      offY + (maxLat - lat) * scale, // 纬度向上为正 → y 反转
    ]
    const pts = waypoints.map((w) => project(w[0], w[1]))

    // 预计算累积弧长，供船位插值
    const seg: number[] = [0]
    for (let i = 1; i < pts.length; i++) {
      const dx = pts[i][0] - pts[i - 1][0]
      const dy = pts[i][1] - pts[i - 1][1]
      seg.push(seg[i - 1] + Math.hypot(dx, dy))
    }
    const total = seg[seg.length - 1]

    const posAt = (dist: number): [number, number] => {
      if (dist <= 0) return pts[0]
      if (dist >= total) return pts[pts.length - 1]
      let i = 1
      while (i < seg.length && seg[i] < dist) i++
      const t = (dist - seg[i - 1]) / (seg[i] - seg[i - 1])
      return [
        pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t,
        pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t,
      ]
    }

    const drawBackdrop = () => {
      const g = ctx.createLinearGradient(0, 0, 0, H)
      g.addColorStop(0, '#0c1020')
      g.addColorStop(1, '#0a0e1a')
      ctx.fillStyle = g
      ctx.fillRect(0, 0, W, H)
      // 经纬网格
      ctx.strokeStyle = 'rgba(100,200,255,0.04)'
      ctx.lineWidth = 1
      for (let gx = 0; gx <= W; gx += 46) {
        ctx.beginPath()
        ctx.moveTo(gx, 0)
        ctx.lineTo(gx, H)
        ctx.stroke()
      }
      for (let gy = 0; gy <= H; gy += 46) {
        ctx.beginPath()
        ctx.moveTo(0, gy)
        ctx.lineTo(W, gy)
        ctx.stroke()
      }
    }

    const drawPathUpTo = (dist: number) => {
      ctx.strokeStyle = '#667eea'
      ctx.lineWidth = 3
      ctx.lineJoin = 'round'
      ctx.lineCap = 'round'
      ctx.shadowColor = 'rgba(102,126,234,0.5)'
      ctx.shadowBlur = 12
      ctx.beginPath()
      ctx.moveTo(pts[0][0], pts[0][1])
      let acc = 0
      for (let i = 1; i < pts.length; i++) {
        const segLen = seg[i] - seg[i - 1]
        if (acc + segLen <= dist) {
          ctx.lineTo(pts[i][0], pts[i][1])
          acc += segLen
        } else {
          const t = (dist - acc) / segLen
          ctx.lineTo(
            pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t,
            pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t,
          )
          break
        }
      }
      ctx.stroke()
      ctx.shadowBlur = 0
    }

    const drawWaypoints = (dist: number) => {
      pts.forEach((p, i) => {
        if (seg[i] > dist + 1) return
        const isEnd = i === 0 || i === pts.length - 1
        ctx.beginPath()
        ctx.fillStyle = isEnd ? '#88ccff' : 'rgba(102,126,234,0.85)'
        ctx.arc(p[0], p[1], isEnd ? 5 : 3, 0, Math.PI * 2)
        ctx.fill()
        if (isEnd) {
          ctx.beginPath()
          ctx.strokeStyle = 'rgba(136,204,255,0.3)'
          ctx.lineWidth = 1.5
          ctx.arc(p[0], p[1], 9, 0, Math.PI * 2)
          ctx.stroke()
        }
      })
    }

    const drawShip = (dist: number, pulse: number) => {
      const [x, y] = posAt(dist)
      ctx.beginPath()
      ctx.fillStyle = 'rgba(0,255,136,0.12)'
      ctx.arc(x, y, 10 + pulse * 4, 0, Math.PI * 2)
      ctx.fill()
      ctx.beginPath()
      ctx.fillStyle = '#00ff88'
      ctx.arc(x, y, 5, 0, Math.PI * 2)
      ctx.fill()
      ctx.strokeStyle = 'rgba(0,255,136,0.6)'
      ctx.lineWidth = 2
      ctx.stroke()
    }

    const render = (dist: number, pulse: number) => {
      ctx.clearRect(0, 0, W, H)
      drawBackdrop()
      drawPathUpTo(dist)
      drawWaypoints(dist)
      drawShip(dist, pulse)
    }

    if (reduceMotion()) {
      render(total, 0)
      return
    }

    const drawMs = 1800
    const start = performance.now()
    const loop = (now: number) => {
      const elapsed = now - start
      const p = Math.min(elapsed / drawMs, 1)
      const eased = 1 - Math.pow(1 - p, 3) // easeOutCubic
      const pulse = (Math.sin(now / 600) + 1) / 2
      render(total * eased, pulse)
      rafRef.current = requestAnimationFrame(loop)
    }
    rafRef.current = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(rafRef.current)
  }, [waypoints])

  return (
    <div className="routemap card">
      <div className="routemap-canvas">
        <canvas ref={canvasRef} />
      </div>
      <div className="routemap-foot">
        <b>{routeName}</b>
        <span className="num">{Math.round(distanceNm).toLocaleString('en-US')} nm</span>
        <span className="num">单程 ≈ {durationH.toFixed(0)} h</span>
        <span className="num">平均风速 {windMs.toFixed(1)} m/s</span>
      </div>
    </div>
  )
}
