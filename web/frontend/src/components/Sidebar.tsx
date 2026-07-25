import { useState } from 'react'
import type { Options, ScenarioRequest, ShipMeta } from '../api'
import { fmtInt } from '../lib/format'

type Override = { DWT: number; L: number; B: number; draft: number; C_B: number }

const metaToOverride = (m: ShipMeta): Override => ({
  DWT: m.DWT,
  L: m.L,
  B: m.B,
  draft: m.T,
  C_B: m.C_B,
})

function Slider({
  label,
  value,
  min,
  max,
  step,
  unit = '',
  decimals = 0,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  unit?: string
  decimals?: number
  onChange: (v: number) => void
}) {
  return (
    <label className="field">
      <span className="field-label">
        {label}
        <b className="num field-val">
          {value.toFixed(decimals)}
          {unit}
        </b>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
    </label>
  )
}

/** 复刻 dashboard OwnerInputs 两层输入：①船型/航速/帆型/航线季节/经济性 + ②实船几何覆盖。 */
export default function Sidebar({
  options,
  req,
  patch,
}: {
  options: Options
  req: ScenarioRequest
  patch: (p: Partial<ScenarioRequest>) => void
}) {
  const [advOpen, setAdvOpen] = useState(false)
  const useOverride = req.overrides !== null
  const shipMeta = options.ships.find((s) => s.value === req.ship)!.meta
  const currentSail = options.sails.find((s) => s.value === req.sail)!
  const r = options.ranges

  const onShip = (value: string) => {
    const m = options.ships.find((s) => s.value === value)!.meta
    patch({ ship: value, overrides: useOverride ? metaToOverride(m) : null })
  }

  const onSail = (value: string) => {
    const defCost =
      value === 'flettner'
        ? options.flettner_unit_costs[req.flettner_spec]
        : options.sails.find((s) => s.value === value)!.default_unit_cost
    patch({ sail: value, unit_cost: defCost })
  }

  const onSpec = (value: string) => {
    patch({ flettner_spec: value, unit_cost: options.flettner_unit_costs[value] })
  }

  const onToggleOverride = (on: boolean) => {
    patch({ overrides: on ? metaToOverride(shipMeta) : null })
  }

  const setOv = (key: keyof Override, val: number) => {
    const base = req.overrides ?? metaToOverride(shipMeta)
    patch({ overrides: { ...base, [key]: val } })
  }

  const ov = req.overrides as Override | null

  return (
    <aside className="sidebar">
      <div className="sidebar-inner">
        <div className="brand">
          <span className="brand-mark">⛵</span>
          <div>
            <div className="brand-title">WASP</div>
            <div className="brand-sub">风帆辅助推进 · 效益决策</div>
          </div>
        </div>

        {/* ① 船型 */}
        <div className="group">
          <label className="field">
            <span className="field-label">船型</span>
            <select value={req.ship} onChange={(e) => onShip(e.target.value)}>
              {options.ships.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {/* ② 实船参数（高级，可选）→ 触发 live 重算 */}
        <div className="group">
          <button className="adv-toggle" onClick={() => setAdvOpen((o) => !o)}>
            <span>{advOpen ? '▾' : '▸'} 实船参数（高级，可选）</span>
          </button>
          {advOpen && (
            <div className="adv-body">
              <label className="check">
                <input
                  type="checkbox"
                  checked={useOverride}
                  onChange={(e) => onToggleOverride(e.target.checked)}
                />
                启用实船几何覆盖 <em>（触发 live 物理重算）</em>
              </label>
              <div className={`ov-grid ${useOverride ? '' : 'disabled'}`}>
                <label className="field-sm">
                  DWT (t)
                  <input
                    type="number"
                    disabled={!useOverride}
                    value={ov ? ov.DWT : shipMeta.DWT}
                    step={1000}
                    onChange={(e) => setOv('DWT', parseFloat(e.target.value))}
                  />
                </label>
                <label className="field-sm">
                  L (m)
                  <input
                    type="number"
                    disabled={!useOverride}
                    value={ov ? ov.L : shipMeta.L}
                    step={1}
                    onChange={(e) => setOv('L', parseFloat(e.target.value))}
                  />
                </label>
                <label className="field-sm">
                  B (m)
                  <input
                    type="number"
                    disabled={!useOverride}
                    value={ov ? ov.B : shipMeta.B}
                    step={0.5}
                    onChange={(e) => setOv('B', parseFloat(e.target.value))}
                  />
                </label>
                <label className="field-sm">
                  吃水 (m)
                  <input
                    type="number"
                    disabled={!useOverride}
                    value={ov ? ov.draft : shipMeta.T}
                    step={0.2}
                    onChange={(e) => setOv('draft', parseFloat(e.target.value))}
                  />
                </label>
                <label className="field-sm">
                  C_B
                  <input
                    type="number"
                    disabled={!useOverride}
                    value={ov ? ov.C_B : shipMeta.C_B}
                    step={0.01}
                    onChange={(e) => setOv('C_B', parseFloat(e.target.value))}
                  />
                </label>
              </div>
              <Slider
                label="SFOC (g/kWh)"
                value={req.sfoc}
                min={r.sfoc.min}
                max={r.sfoc.max ?? 220}
                step={r.sfoc.step}
                onChange={(v) => patch({ sfoc: v })}
              />
              <p className="adv-note">SFOC ≠ 180 或非网格航速将触发 live 实时物理重算。</p>
            </div>
          )}
        </div>

        {/* 航速 */}
        <div className="group">
          <Slider
            label="航速 (kn)"
            value={req.speed}
            min={r.speed.min}
            max={r.speed.max ?? 18}
            step={r.speed.step}
            decimals={1}
            onChange={(v) => patch({ speed: v })}
          />
          <p className="hint num">标准网格 {options.speeds_kn.join(' / ')} kn 秒级取数，其余触发 live。</p>
        </div>

        {/* ③ 帆型 */}
        <div className="group">
          <span className="field-label">风帆技术类型</span>
          <div className="seg">
            {options.sails.map((s) => (
              <button
                key={s.value}
                className={`seg-btn ${req.sail === s.value ? 'on' : ''}`}
                onClick={() => onSail(s.value)}
              >
                {s.label}
              </button>
            ))}
          </div>
          {req.sail === 'flettner' && (
            <label className="field">
              <span className="field-label">Flettner 规格 (H×D)</span>
              <select value={req.flettner_spec} onChange={(e) => onSpec(e.target.value)}>
                {options.flettner_specs.map((sp) => (
                  <option key={sp} value={sp}>
                    {sp}
                  </option>
                ))}
              </select>
            </label>
          )}
          <p className="hint">安装台数 {currentSail.n_sails} 台（等面积归一化，公平对比）。</p>
        </div>

        {/* ④ 航线 / 季节 */}
        <div className="group two">
          <label className="field">
            <span className="field-label">航线</span>
            <select value={req.route} onChange={(e) => patch({ route: e.target.value })}>
              {options.routes.map((r2) => (
                <option key={r2.value} value={r2.value}>
                  {r2.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">季节</span>
            <select value={req.season} onChange={(e) => patch({ season: e.target.value })}>
              {options.seasons.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {/* ⑤ 经济性 */}
        <div className="group">
          <span className="group-title">经济性参数</span>
          <label className="field">
            <span className="field-label">燃料类型</span>
            <select value={req.fuel_type} onChange={(e) => patch({ fuel_type: e.target.value })}>
              {options.fuel_types.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>
          <Slider
            label="燃油价 (USD/kg)"
            value={req.fuel_price}
            min={r.fuel_price.min}
            max={r.fuel_price.max ?? 1}
            step={r.fuel_price.step}
            decimals={2}
            onChange={(v) => patch({ fuel_price: v })}
          />
          <Slider
            label="碳价 (EUR/tCO₂)"
            value={req.co2_price}
            min={r.co2_price.min}
            max={r.co2_price.max ?? 150}
            step={r.co2_price.step}
            onChange={(v) => patch({ co2_price: v })}
          />
          <label className="field">
            <span className="field-label">
              单台成本 (USD)
              <b className="num field-val">${fmtInt(req.unit_cost ?? 0)}</b>
            </span>
            <input
              type="number"
              value={req.unit_cost ?? 0}
              min={r.unit_cost.min}
              step={r.unit_cost.step}
              onChange={(e) => patch({ unit_cost: parseFloat(e.target.value) })}
            />
          </label>
          <Slider
            label="海上作业比例"
            value={req.sea_ratio}
            min={r.sea_ratio.min}
            max={r.sea_ratio.max ?? 0.95}
            step={r.sea_ratio.step}
            decimals={3}
            onChange={(v) => patch({ sea_ratio: v })}
          />
        </div>
      </div>
    </aside>
  )
}
