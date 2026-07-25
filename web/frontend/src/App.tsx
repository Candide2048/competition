import { useEffect, useState, type ReactNode } from 'react'
import { getOptions, type Options, type ScenarioRequest } from './api'
import { useScenario } from './hooks/useScenario'
import { useReveal } from './hooks/useReveal'
import { useI18n } from './i18n'
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
import ScrollProgress from './components/ScrollProgress'
import WelcomeToast from './components/WelcomeToast'

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
  const { t, locale } = useI18n()
  const L = (s: string) => t.labels[s] || s

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
          locale,
        })
      })
      .catch((e: unknown) => setBootError((e as Error).message || t.err_boot_fallback))
  }, [])

  const patch = (p: Partial<ScenarioRequest>) =>
    setReq((r) => (r ? { ...r, ...p } : r))

  // sync locale to API request when language changes
  useEffect(() => {
    setReq((r) => (r ? { ...r, locale } : r))
  }, [locale])

  const { data, loading, error } = useScenario(req)

  if (bootError) {
    return (
      <div className="boot boot-err">
        <h1>{t.err_api}</h1>
        <p>{bootError}</p>
        <p className="hint">{t.err_hint} <code>uvicorn app.api:app --port 8600</code>{t.err_hint_suffix}</p>
      </div>
    )
  }
  if (!options || !req) {
    return <div className="boot">{t.loading}</div>
  }

  const ship = options.ships.find((s) => s.value === req.ship)!
  const sail = options.sails.find((s) => s.value === req.sail)!

  return (
    <div className="app">
      <Background />
      <ScrollProgress />
      <WelcomeToast />
      <Sidebar options={options} req={req} patch={patch} />

      <main className="main">
        {loading && (
          <div className="live-bar">
            <span className="spinner" /> {t.loading_live}
          </div>
        )}

        {error && !data && (
          <div className="section boot-err-inline">{t.err_scenario}{error}</div>
        )}

        {data && (
          <>
            <Hero res={data} ship={ship} sail={sail} />

            {/* 核心答案区：回收期 + 年净节省 + 节油率 */}
            <Reveal>
              <div className="section-header">
                <span className="eyebrow">{t.sec_kpi}</span>
                <h2 className="section-title">{t.sec_kpi_title}</h2>
              </div>
              {!data.speed_exact && (
                <div className="note">
                  {t.speed_note(req.speed.toFixed(1), data.speed_used.toFixed(0))}
                </div>
              )}
              <KpiGrid res={data} />
            </Reveal>

            <hr className="divider" />

            {/* 累计现金流曲线 */}
            <Reveal>
              <div className="section-header">
                <span className="eyebrow">{t.sec_cashflow}</span>
                <h2 className="section-title">{t.sec_cashflow_title}</h2>
              </div>
              <CashflowChart
                initialCost={data.cell.initial_cost_usd}
                annualSavings={data.cell.annual_savings_usd}
              />
            </Reveal>

            <hr className="divider" />

            {/* CII 评级跃迁 */}
            <Reveal>
              <div className="section-header">
                <span className="eyebrow">{t.sec_cii}</span>
                <h2 className="section-title">{t.sec_cii_title}</h2>
              </div>
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
              <div className="section-header">
                <span className="eyebrow">{t.sec_sail}</span>
                <h2 className="section-title">{t.sec_sail_title}</h2>
              </div>
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
              <div className="section-header">
                <span className="eyebrow">{t.sec_bench}</span>
                <h2 className="section-title">{t.sec_bench_title}</h2>
              </div>
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
              <div className="section-header">
                <span className="eyebrow">{t.sec_matrix}</span>
                <h2 className="section-title">{t.sec_matrix_title}</h2>
              </div>
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
              <div className="section-header">
                <span className="eyebrow">{t.sec_route}</span>
                <h2 className="section-title">{L(data.route_name)}</h2>
              </div>
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
              <div className="section-header">
                <span className="eyebrow">{t.sec_report}</span>
                <h2 className="section-title">{t.sec_report_title}</h2>
              </div>
              <ReportPanel md={data.report_md} />
            </Reveal>
          </>
        )}
      </main>
    </div>
  )
}
