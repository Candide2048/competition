// WASP 前端 API 封装 —— 数值真源在 Python (FastAPI /api)，此处仅做 fetch + 类型。

export interface ShipMeta {
  DWT: number
  ship_type_imo: string
  GT: number | null
  L: number
  B: number
  T: number
  C_B: number
  V_design_kn: number
}

export interface ShipOption {
  value: string
  label: string
  meta: ShipMeta
}

export interface SailOption {
  value: string
  label: string
  n_sails: number
  bench: { lo: number; hi: number; refs: string }
  default_unit_cost: number
}

export interface RouteOption {
  value: string
  label: string
  waypoints: [number, number][] // [lat, lon]
}

export interface SeasonOption {
  value: string
  label: string
}

export interface Range {
  min: number
  max?: number
  step: number
  default?: number
}

export interface Options {
  ships: ShipOption[]
  sails: SailOption[]
  routes: RouteOption[]
  seasons: SeasonOption[]
  speeds_kn: number[]
  flettner_specs: string[]
  flettner_unit_costs: Record<string, number>
  fuel_types: string[]
  ranges: Record<string, Range>
  defaults: {
    ship: string
    sail: string
    route: string
    season: string
    fuel_type: string
    cii_year: number
  }
  capabilities: {
    live_physics: boolean
    grid_flettner_spec: string
  }
  compatibility: Record<string, Record<string, number>>
}

export interface Cell {
  mean_wind_ms: number
  mean_thrust_kN: number
  mean_power_kW: number
  fuel_saved_t: number
  saving_rate_pct: number
  co2_reduced_t: number
  cii_baseline: number
  cii_with_sail: number
  cii_rating_baseline: string
  cii_rating_with_sail: string
  cii_improvement_pct: number
  initial_cost_usd: number
  annual_savings_usd: number
  payback_years: number | null
  npv_10y_usd: number
  npv_20y_usd: number
  compatibility: number
  compatible: boolean
  physics_saving_rate_pct: number
  saving_rate_pct_before_guardrail: number
  screening_cap_pct: number
  guardrail_applied: boolean
  saving_rate_pct_adjusted: number
  payback_years_adjusted: number | null
}

export interface Physics {
  distance_nm: number
  duration_h: number
  mean_wind_ms: number
  fuel_baseline_kg: number
  fuel_with_sail_kg: number
  [k: string]: unknown
}

export interface ScenarioResult {
  cell: Cell
  physics: Physics
  is_live: boolean
  speed_used: number
  speed_exact: boolean
  trips_per_year: number
  n_sails: number
  route_name: string
  route_waypoints: [number, number][]
  unit_cost_used: number
  bench: { lo: number; hi: number; refs: string }
  report_md: string
  cashflow: CashflowPoint[]
  quality: {
    within_benchmark: boolean
    compatibility: number
    raw_saving_rate_pct: number
    saving_rate_pct_before_guardrail: number
    screening_cap_pct: number
    guardrail_applied: boolean
    scenario_basis: string
    cii_year: number
  }
}

export interface CashflowPoint {
  year: number
  cumulative: number
}

export interface ScenarioRequest {
  ship: string
  speed: number
  route: string
  season: string
  sail: string
  flettner_spec: string
  fuel_type: string
  fuel_price: number
  co2_price: number
  unit_cost: number | null
  sea_ratio: number
  sfoc: number
  overrides: Record<string, number> | null
  locale: string
  cii_year: number
}

export interface MatrixResult {
  ship: string
  route: string
  route_name: string
  season: string
  speeds: number[]
  sails: string[]
  sail_labels: string[]
  saving_rate_pct: number[][]
  annual_savings_usd: number[][]
  payback_years: (number | null)[][]
}

async function jget<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${url} → ${r.status}`)
  return r.json() as Promise<T>
}

export function getOptions(): Promise<Options> {
  return jget<Options>('/api/options')
}

export async function postScenario(
  req: ScenarioRequest,
  signal?: AbortSignal,
): Promise<ScenarioResult> {
  const r = await fetch('/api/scenario', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
    signal,
  })
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}))
    throw new Error((detail as { detail?: string }).detail ?? `HTTP ${r.status}`)
  }
  return r.json() as Promise<ScenarioResult>
}

export function getMatrix(params: {
  ship: string
  route: string
  season: string
  fuel_price: number
  co2_price: number
  sea_ratio: number
  fuel_type: string
  cii_year: number
}): Promise<MatrixResult> {
  const q = new URLSearchParams({
    ship: params.ship,
    route: params.route,
    season: params.season,
    fuel_price: String(params.fuel_price),
    co2_price: String(params.co2_price),
    sea_ratio: String(params.sea_ratio),
    fuel_type: params.fuel_type,
    cii_year: String(params.cii_year),
  })
  return jget<MatrixResult>(`/api/matrix?${q.toString()}`)
}
