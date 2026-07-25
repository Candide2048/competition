import { useEffect, useState, type ReactNode } from 'react'
import { getOptions, type Options, type ScenarioRequest } from './api'
import { useScenario } from './hooks/useScenario'
import { useReveal } from './hooks/useReveal'
import Background from './components/Background'
import Sidebar from './components/Sidebar'
import Hero from './components/Hero'
import KpiGrid from './components/KpiGrid'
import CashflowChart from './components/CashflowChart'
import CiiBadge from './components/CiiBadge'
import SailCompare from './components/SailCompare'
import BenchmarkBar from './components/BenchmarkBar'
import RouteMap from './components/RouteMap'
import MatrixHeatmap from './components/MatrixHeatmap'
import ReportPanel from './components/ReportPanel'

/** 分区包裹：进入视口滚动淡入。 */
function Reveal({ children, className = '' }: { children: ReactNode; className?: string }) {
  const { ref, shown } = useReveal<HTMLElement>()
  return (
    <section ref={ref} className={`section reveal ${shown ? 'in' : ''} ${className}`}>
      {children}
    </section>
  )
}

export default function App() {
  const [options, setOptions] = useState<Options | null>(null)
  const [req, setReq] = useState<ScenarioRequest | null>(null)
  const [bootError, setBootError] = useState<string | null>(null)

  useEffect(() => {
    getOptions()
      .then((o) => {
        setOptions(o)
        const ship = o.ships.find((s) => s.value === o.defaults.ship) ?? o.ships[0]
        const sail = o.sails.find((s) => s.value === o.defaults.sail) ?? o.sails[0]
        const spec = o.flettner_specs[1] ?? o.flettner_specs[0]
        const unitCost =
          sail.value === 'flettner' ? o.flettner_unit_costs[spec] : sail.default_unit_cost
        setReq({
          ship: ship.value,
          speed: o.ranges.speed.default ?? 14,
          route: o.defaults.route,
          season: o.defaults.season,
          sail: sail.value,
          flettner_spec: spec,
          fuel_type: o.defaults.fuel_type,
          fuel_price: o.ranges.fuel_price.default ?? 0.6,
          co2_price: o.ranges.co2_price.default ?? 74,
          unit_cost: unitCost,
          sea_ratio: o.ranges.sea_ratio.default ?? 0.742,
          sfoc: o.ranges.sfoc.default ?? 180,
          overrides: null,
        })
      })
      .catch((e: unknown) => setBootError((e as Error).message || '选项加载失败'))
  }, [])

  const patch = (p: Partial<ScenarioRequest>) =>
    setReq((r) => (r ? { ...r, ...p } : r))

  const { data, loading, error } = useScenario(req)

  if (bootError) {
    return (
      <div className="boot boot-err">
        <h1>无法连接后端 API</h1>
        <p>{bootError}</p>
        <p className="hint">请先启动 <code>uvicorn app.api:app --port 8600</code>。</p>
      </div>
    )
  }
  if (!options || !req) {
    return <div className="boot">加载参数选项…</div>
  }

  const ship = options.ships.find((s) => s.value === req.ship)!
  const sail = options.sails.find((s) => s.value === req.sail)!

  return (
    <div className="app">
      <Background />
      <Sidebar options={options} req={req} patch={patch} />

      <main className="main">
        {loading && (
          <div className="live-bar">
            <span className="spinner" /> 实时物理重算中（首次约数秒，缓存后瞬时）…
          </div>
        )}

        {error && !data && (
          <div className="section boot-err-inline">场景计算失败：{error}</div>
        )}

        {data && (
          <>
            <Hero res={data} ship={ship} sail={sail} />

            {/* 核心答案区：回收期 + 年净节省 + 节油率 */}
            <Reveal>
              <p className="eyebrow">核心效益指标</p>
              {!data.speed_exact && (
                <div className="note">
                  航速 {req.speed.toFixed(1)} kn 不在标准集，已取最近邻{' '}
                  <b className="num">{data.speed_used.toFixed(0)} kn</b> 网格值。
                </div>
              )}
              <KpiGrid res={data} />
            </Reveal>

            <hr className="divider" />

            {/* 累计现金流曲线 */}
            <Reveal>
              <p className="eyebrow">投资回报曲线</p>
              <h2 className="section-title">累计净现金流（含贴现）</h2>
              <CashflowChart
                initialCost={data.cell.initial_cost_usd}
                annualSavings={data.cell.annual_savings_usd}
              />
            </Reveal>

            <hr className="divider" />

            {/* CII 评级跃迁 */}
            <Reveal>
              <p className="eyebrow">IMO 碳强度合规</p>
              <h2 className="section-title">CII 评级跃迁</h2>
              <div className="cii-row">
                <CiiBadge
                  baseline={data.cell.cii_rating_baseline}
                  withSail={data.cell.cii_rating_with_sail}
                  improvementPct={data.cell.cii_improvement_pct}
                  co2ReducedPerTrip={data.cell.co2_reduced_t}
                  co2Price={req.co2_price}
                  tripsPerYear={data.trips_per_year}
                />
              </div>
            </Reveal>

            <hr className="divider" />

            {/* 三帆型 PK */}
            <Reveal>
              <p className="eyebrow">帆型对比</p>
              <h2 className="section-title">三帆型横向 PK（同条件对比）</h2>
              <SailCompare
                ship={req.ship}
                route={req.route}
                season={req.season}
                fuelPrice={req.fuel_price}
                co2Price={req.co2_price}
                seaRatio={req.sea_ratio}
                currentSpeed={req.speed}
              />
            </Reveal>

            <hr className="divider" />

            {/* 实船报道对照 */}
            <Reveal>
              <p className="eyebrow">实船报道对照</p>
              <h2 className="section-title">节油率 vs 公开实船报道区间</h2>
              <BenchmarkBar
                value={data.cell.saving_rate_pct}
                lo={data.bench.lo}
                hi={data.bench.hi}
                refs={data.bench.refs}
              />
            </Reveal>

            <hr className="divider" />

            {/* 效益矩阵热力图 */}
            <Reveal>
              <p className="eyebrow">效益矩阵</p>
              <h2 className="section-title">帆型 × 航速 效益全景</h2>
              <MatrixHeatmap
                ship={req.ship}
                route={req.route}
                season={req.season}
                fuelPrice={req.fuel_price}
                co2Price={req.co2_price}
                seaRatio={req.sea_ratio}
              />
            </Reveal>

            <hr className="divider" />

            {/* 航线地图 */}
            <Reveal>
              <p className="eyebrow">航线</p>
              <h2 className="section-title">{data.route_name}</h2>
              <RouteMap
                key={req.route}
                waypoints={data.route_waypoints}
                routeName={data.route_name}
                distanceNm={data.physics.distance_nm}
                durationH={data.physics.duration_h}
                windMs={data.physics.mean_wind_ms}
              />
            </Reveal>

            <hr className="divider" />

            {/* 技术报告 */}
            <Reveal>
              <p className="eyebrow">分析报告</p>
              <h2 className="section-title">自动生成技术报告</h2>
              <ReportPanel md={data.report_md} />
            </Reveal>
          </>
        )}
      </main>
    </div>
  )
}
