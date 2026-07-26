import { useState } from 'react'
import type { Options, ScenarioRequest, ShipMeta } from '../api'
import { fmtInt } from '../lib/format'
import { useI18n } from '../i18n'
import { useTheme } from '../hooks/useTheme'
import MarketPrices from './MarketPrices'

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
  const [mobileOpen, setMobileOpen] = useState(false)
  const { locale, toggle: toggleLang, t } = useI18n()
  const { theme, toggle: toggleTheme } = useTheme()
  const L = (s: string) => t.labels[s] || s
  const useOverride = req.overrides !== null
  const shipMeta = options.ships.find((s) => s.value === req.ship)!.meta
  const currentSail = options.sails.find((s) => s.value === req.sail)!
  const r = options.ranges

  const onShip = (value: string) => {
    const m = options.ships.find((s) => s.value === value)!.meta
    const currentCompatibility = options.compatibility[value]?.[req.sail] ?? 0
    const fallbackSail = options.sails.find(
      (s) => (options.compatibility[value]?.[s.value] ?? 0) > 0,
    )
    const nextSail = currentCompatibility > 0 ? req.sail : fallbackSail?.value ?? req.sail
    const nextCost = nextSail === 'flettner'
      ? options.flettner_unit_costs[req.flettner_spec]
      : options.sails.find((s) => s.value === nextSail)?.default_unit_cost ?? req.unit_cost
    patch({
      ship: value,
      sail: nextSail,
      unit_cost: nextCost,
      overrides: useOverride ? metaToOverride(m) : null,
    })
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
  const currentRoute = options.routes.find((route) => route.value === req.route)!

  const showResults = () => {
    setMobileOpen(false)
    requestAnimationFrame(() => {
      document.getElementById('results')?.scrollIntoView({ behavior: 'smooth' })
    })
  }

  return (
    <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
      <div className="sidebar-inner">
        <div className="sidebar-top">
        <div className="brand">
          <span className="brand-mark">⛵</span>
          <div>
            <div className="brand-title">WASP</div>
            <div className="brand-sub">{t.brand_sub}</div>
          </div>
        </div>

        {/* 语言 / 主题切换 */}
        <div className="toolbar-row">
          <div className="pill-toggle">
            <button className={locale === 'zh' ? 'on' : ''} onClick={() => locale !== 'zh' && toggleLang()}>中</button>
            <button className={locale === 'en' ? 'on' : ''} onClick={() => locale !== 'en' && toggleLang()}>EN</button>
          </div>
          <button className="theme-btn" onClick={toggleTheme} title={theme === 'dark' ? 'Light mode' : 'Dark mode'}>
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        </div>
        </div>

        <button
          className="mobile-params-toggle"
          type="button"
          aria-expanded={mobileOpen}
          aria-controls="scenario-controls"
          onClick={() => setMobileOpen((open) => !open)}
        >
          <span>{mobileOpen ? t.sb_hide_params : t.sb_show_params}</span>
          <span aria-hidden>{mobileOpen ? '↑' : '↓'}</span>
        </button>

        <div id="scenario-controls" className="sidebar-controls">

        {/* ① 船型 */}
        <div className="group">
          <label className="field">
            <span className="field-label">{t.sb_ship}</span>
            <select value={req.ship} onChange={(e) => onShip(e.target.value)}>
              {options.ships.map((s) => (
                <option key={s.value} value={s.value}>
                  {L(s.label)}
                </option>
              ))}
            </select>
          </label>
        </div>

        {/* ② 实船参数（高级，可选）→ 触发 live 重算 */}
        {options.capabilities.live_physics && (
          <div className="group">
            <button className="adv-toggle" onClick={() => setAdvOpen((o) => !o)}>
              <span>{advOpen ? '▾' : '▸'} {t.sb_adv}</span>
            </button>
            {advOpen && (
            <div className="adv-body">
              <label className="check">
                <input
                  type="checkbox"
                  checked={useOverride}
                  onChange={(e) => onToggleOverride(e.target.checked)}
                />
                {t.sb_override} <em>{t.sb_override_note}</em>
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
                  {t.sb_draft}
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
                label={t.sb_sfoc}
                value={req.sfoc}
                min={r.sfoc.min}
                max={r.sfoc.max ?? 220}
                step={r.sfoc.step}
                onChange={(v) => patch({ sfoc: v })}
              />
              <p className="adv-note">{t.sb_sfoc_note}</p>
            </div>
            )}
          </div>
        )}

        {/* 航速 */}
        <div className="group">
          <Slider
            label={t.sb_speed}
            value={req.speed}
            min={r.speed.min}
            max={r.speed.max ?? 18}
            step={r.speed.step}
            decimals={1}
            onChange={(v) => patch({ speed: v })}
          />
          <p className="hint num">{t.sb_speed_hint(options.speeds_kn.join(' / '))}</p>
        </div>

        {/* ③ 帆型 */}
        <div className="group">
          <span className="field-label">{t.sb_sail_type}</span>
          <div className="seg">
            {options.sails.map((s) => (
              <button
                key={s.value}
                className={`seg-btn ${req.sail === s.value ? 'on' : ''}`}
                disabled={(options.compatibility[req.ship]?.[s.value] ?? 0) <= 0}
                onClick={() => onSail(s.value)}
              >
                {L(s.label)}
              </button>
            ))}
          </div>
          {req.sail === 'flettner' && (
            <label className="field">
              <span className="field-label">{t.sb_flettner_spec}</span>
              <select value={req.flettner_spec} onChange={(e) => onSpec(e.target.value)}>
                {options.flettner_specs.map((sp) => (
                  <option key={sp} value={sp}>
                    {sp}
                  </option>
                ))}
              </select>
            </label>
          )}
          <p className="hint">{t.sb_sail_hint(currentSail.n_sails)}</p>
        </div>

        {/* ④ 航线 / 季节 */}
        <div className="group two">
          <label className="field">
            <span className="field-label">{t.sb_route}</span>
            <select value={req.route} onChange={(e) => patch({ route: e.target.value })}>
              {options.routes.map((r2) => (
                <option key={r2.value} value={r2.value}>
                  {L(r2.label)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">{t.sb_season}</span>
            <select value={req.season} onChange={(e) => patch({ season: e.target.value })}>
              {options.seasons.map((s) => (
                <option key={s.value} value={s.value}>
                  {L(s.label)}
                </option>
              ))}
            </select>
          </label>
        </div>

        {/* ⑤ 实时市场数据 + 经济性 */}
        <div className="group">
          <MarketPrices
            recommendedHub={currentRoute.recommended_bunker_hub}
            onApply={(fuel, co2) => patch({ fuel_price: fuel, co2_price: co2 })}
          />
        </div>

        {/* ⑥ 经济性 */}
        <div className="group">
          <span className="group-title">{t.sb_econ}</span>
          <label className="field">
            <span className="field-label">{t.sb_fuel_type}</span>
            <select value={req.fuel_type} onChange={(e) => patch({ fuel_type: e.target.value })}>
              {options.fuel_types.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>
          <Slider
            label={t.sb_fuel_price}
            value={req.fuel_price}
            min={r.fuel_price.min}
            max={r.fuel_price.max ?? 1}
            step={r.fuel_price.step}
            decimals={2}
            onChange={(v) => patch({ fuel_price: v })}
          />
          <Slider
            label={t.sb_co2_price}
            value={req.co2_price}
            min={r.co2_price.min}
            max={r.co2_price.max ?? 150}
            step={r.co2_price.step}
            onChange={(v) => patch({ co2_price: v })}
          />
          <label className="field">
            <span className="field-label">
              {t.sb_unit_cost}
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
            label={t.sb_sea_ratio}
            value={req.sea_ratio}
            min={r.sea_ratio.min}
            max={r.sea_ratio.max ?? 0.95}
            step={r.sea_ratio.step}
            decimals={3}
            onChange={(v) => patch({ sea_ratio: v })}
          />
        </div>
        <button className="mobile-view-results" type="button" onClick={showResults}>
          {t.sb_view_results}
        </button>
        </div>
      </div>
    </aside>
  )
}
