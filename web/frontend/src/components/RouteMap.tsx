import { useEffect, useRef } from 'react'
import { reduceMotion } from '../lib/format'
import { useTheme } from '../hooks/useTheme'
import { useI18n } from '../i18n'

type LatLon = [number, number]

// CartoDB Dark/Light 瓦片 URL
const TILE_DARK = 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png'
const TILE_LIGHT = 'https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png'
const TILE_SIZE = 256

// 经纬度 → 瓦片坐标
function lonToTileX(lon: number, z: number) {
  return ((lon + 180) / 360) * Math.pow(2, z)
}
function latToTileY(lat: number, z: number) {
  const rad = (lat * Math.PI) / 180
  return ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * Math.pow(2, z)
}
// 根据 bbox 确定合适的 zoom 级别
function fitZoom(minLat: number, maxLat: number, minLon: number, maxLon: number, w: number, h: number): number {
  for (let z = 10; z >= 1; z--) {
    const x0 = lonToTileX(minLon, z)
    const x1 = lonToTileX(maxLon, z)
    const y0 = latToTileY(maxLat, z)
    const y1 = latToTileY(minLat, z)
    const tilesX = (x1 - x0) * TILE_SIZE
    const tilesY = (y1 - y0) * TILE_SIZE
    if (tilesX < w * 1.3 && tilesY < h * 1.3) return z
  }
  return 1
}

/**
 * 航线动态绘制（Canvas）—— 叠加 CartoDB Dark Matter 地图瓦片。
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
  const { theme } = useTheme()
  const { t } = useI18n()
  const L = (s: string) => t.labels[s] || s

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

    const TILE_URL = theme === 'light' ? TILE_LIGHT : TILE_DARK

    const lats = waypoints.map((w) => w[0])
    const lons = waypoints.map((w) => w[1])
    const minLat = Math.min(...lats) - 2
    const maxLat = Math.max(...lats) + 2
    const minLon = Math.min(...lons) - 3
    const maxLon = Math.max(...lons) + 3

    // 计算合适的 zoom
    const zoom = fitZoom(minLat, maxLat, minLon, maxLon, W, H)

    // 中心点的瓦片坐标
    const centerLon = (minLon + maxLon) / 2
    const centerLat = (minLat + maxLat) / 2
    const centerTX = lonToTileX(centerLon, zoom)
    const centerTY = latToTileY(centerLat, zoom)

    // 像素坐标中心
    const centerPX = centerTX * TILE_SIZE
    const centerPY = centerTY * TILE_SIZE

    // 经纬度→画布坐标
    const project = (lat: number, lon: number): [number, number] => {
      const px = lonToTileX(lon, zoom) * TILE_SIZE - centerPX + W / 2
      const py = latToTileY(lat, zoom) * TILE_SIZE - centerPY + H / 2
      return [px, py]
    }
    const pts = waypoints.map((w) => project(w[0], w[1]))

    // 加载瓦片
    const tileXMin = Math.floor(centerPX / TILE_SIZE - W / (2 * TILE_SIZE)) - 1
    const tileXMax = Math.ceil(centerPX / TILE_SIZE + W / (2 * TILE_SIZE)) + 1
    const tileYMin = Math.floor(centerPY / TILE_SIZE - H / (2 * TILE_SIZE)) - 1
    const tileYMax = Math.ceil(centerPY / TILE_SIZE + H / (2 * TILE_SIZE)) + 1

    let tilesLoaded = 0
    const totalTiles = (tileXMax - tileXMin + 1) * (tileYMax - tileYMin + 1)
    const tileImages: { img: HTMLImageElement; dx: number; dy: number }[] = []

    const drawAll = () => {
      ctx.clearRect(0, 0, W, H)
      // 底色跟随主题
      ctx.fillStyle = theme === 'light' ? '#f5f7fa' : '#0a0e1a'
      ctx.fillRect(0, 0, W, H)
      // 绘制瓦片
      for (const t of tileImages) {
        ctx.drawImage(t.img, t.dx, t.dy, TILE_SIZE, TILE_SIZE)
      }
      // 覆盖一层轻微透明度，确保航线突出
      ctx.fillStyle = theme === 'light' ? 'rgba(245,247,250,0.2)' : 'rgba(10,14,26,0.3)'
      ctx.fillRect(0, 0, W, H)
    }

    for (let tx = tileXMin; tx <= tileXMax; tx++) {
      for (let ty = tileYMin; ty <= tileYMax; ty++) {
        const img = new Image()
        img.crossOrigin = 'anonymous'
        const url = TILE_URL.replace('{z}', String(zoom)).replace('{x}', String(tx)).replace('{y}', String(ty))
        const dx = tx * TILE_SIZE - centerPX + W / 2
        const dy = ty * TILE_SIZE - centerPY + H / 2
        img.onload = () => {
          tileImages.push({ img, dx, dy })
          tilesLoaded++
          if (tilesLoaded >= totalTiles) {
            startDraw()
          }
        }
        img.onerror = () => {
          tilesLoaded++
          if (tilesLoaded >= totalTiles) startDraw()
        }
        img.src = url
      }
    }

    // 如果瓦片加载超时，3秒后强制开始画
    const fallbackTimer = setTimeout(() => startDraw(), 3000)
    let started = false
    const startDraw = () => {
      if (started) return
      started = true
      clearTimeout(fallbackTimer)
      drawAll()
      beginAnimation()
    }

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

    const drawPathUpTo = (dist: number) => {
      ctx.strokeStyle = '#667eea'
      ctx.lineWidth = 3
      ctx.lineJoin = 'round'
      ctx.lineCap = 'round'
      ctx.shadowColor = 'rgba(102,126,234,0.6)'
      ctx.shadowBlur = 14
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
        ctx.arc(p[0], p[1], isEnd ? 6 : 3.5, 0, Math.PI * 2)
        ctx.fill()
        if (isEnd) {
          ctx.beginPath()
          ctx.strokeStyle = 'rgba(136,204,255,0.4)'
          ctx.lineWidth = 1.5
          ctx.arc(p[0], p[1], 10, 0, Math.PI * 2)
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
      drawAll()
      drawPathUpTo(dist)
      drawWaypoints(dist)
      drawShip(dist, pulse)
    }

    const beginAnimation = () => {
      if (reduceMotion()) {
        render(total, 0)
        return
      }
      const drawMs = 1800
      const start = performance.now()
      const loop = (now: number) => {
        const elapsed = now - start
        const p = Math.min(elapsed / drawMs, 1)
        const eased = 1 - Math.pow(1 - p, 3)
        const pulse = (Math.sin(now / 600) + 1) / 2
        render(total * eased, pulse)
        rafRef.current = requestAnimationFrame(loop)
      }
      rafRef.current = requestAnimationFrame(loop)
    }

    return () => {
      clearTimeout(fallbackTimer)
      cancelAnimationFrame(rafRef.current)
    }
  }, [waypoints, theme])

  return (
    <div className="routemap card">
      <div className="routemap-canvas">
        <canvas ref={canvasRef} />
      </div>
      <div className="routemap-foot">
        <b>{L(routeName)}</b>
        <span className="num">{Math.round(distanceNm).toLocaleString('en-US')} nm</span>
        <span className="num">{t.labels['单程'] || '单程'} ≈ {durationH.toFixed(0)} h</span>
        <span className="num">{t.labels['平均风速'] || '平均风速'} {windMs.toFixed(1)} m/s</span>
      </div>
    </div>
  )
}
