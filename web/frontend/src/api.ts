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
    weather_years: number[]
    departure_samples_per_season: number
    uncertainty_interval_available: boolean
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

export interface RecommendationCandidate {
  sail: string
  label: string
  n_sails: number
  saving_rate_pct: number
  annual_savings_usd: number
  initial_cost_usd: number
  payback_years: number | null
  npv_10y_usd: number
  npv_20y_usd: number
  cii_rating_baseline: string
  cii_rating_with_sail: string
  cii_improvement_pct: number
  compatibility: number
  within_benchmark: boolean
  guardrail_applied: boolean
  is_live: boolean
  unit_cost_used: number
}

export interface RecommendationResult {
  decision: 'install' | 'do_not_install'
  recommended_sail: string | null
  best_candidate: string
  criteria: {
    primary: 'npv_20y_usd'
    secondary: 'payback_years'
    investment_horizon_years: number
    cost_basis: 'default_by_sail'
  }
  candidates: RecommendationCandidate[]
  report_md: string
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

export async function postRecommendation(
  req: ScenarioRequest,
  signal?: AbortSignal,
): Promise<RecommendationResult> {
  const r = await fetch('/api/recommendation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
    signal,
  })
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}))
    throw new Error((detail as { detail?: string }).detail ?? `HTTP ${r.status}`)
  }
  return r.json() as Promise<RecommendationResult>
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

export interface QuantileBand {
  p10: number
  p50: number
  p90: number
}

export interface UncertaintyResult {
  available: boolean
  reason?: string
  speed_used?: number
  basis?: { weather_years: number[]; note: string }
  method?: string
  n_samples?: number
  block_h?: number
  seed?: number
  n_hours?: number
  saving_rate_pct?: QuantileBand
  fuel_saved_t?: QuantileBand
  co2_reduced_t?: QuantileBand
  annual_savings_usd?: QuantileBand
  npv_20y_usd?: QuantileBand
  payback_years?: {
    p10_case: number | null
    p50_case: number | null
    p90_case: number | null
  }
  risk?: {
    prob_positive_fuel_saving: number
    prob_positive_npv_20y: number
    prob_within_benchmark?: number
  }
}

export async function postUncertainty(
  req: ScenarioRequest,
  signal?: AbortSignal,
): Promise<UncertaintyResult> {
  const r = await fetch('/api/uncertainty', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
    signal,
  })
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}))
    throw new Error((detail as { detail?: string }).detail ?? `HTTP ${r.status}`)
  }
  return r.json() as Promise<UncertaintyResult>
}

export interface ParetoCandidate {
  id: string
  sail: string
  label: string
  speed_kn: number
  saving_rate_pct: number
  npv_20y_usd: number
  npv_20y_p10_usd?: number
  annual_co2_reduced_t: number
  cii_improvement_pct: number
  payback_years: number | null
  initial_cost_usd: number
  annual_savings_usd: number
  pareto_rank: number
  is_front: boolean
  dominates: string[]
  dominated_by: string[]
}

export interface ParetoResult {
  scope: {
    ship: string
    route: string
    route_name: string
    season: string
    speeds: number[]
  }
  objectives: { field: string; direction: 'max' | 'min' }[]
  robust_npv_available: boolean
  fronts: string[][]
  candidates: ParetoCandidate[]
}

export async function postPareto(
  req: ScenarioRequest,
  signal?: AbortSignal,
): Promise<ParetoResult> {
  const r = await fetch('/api/pareto', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
    signal,
  })
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}))
    throw new Error((detail as { detail?: string }).detail ?? `HTTP ${r.status}`)
  }
  return r.json() as Promise<ParetoResult>
}

export interface AuditModelStage {
  name: string
  source: string
  role: string
  validation: string
}

export interface AuditResult {
  model_chain: AuditModelStage[]
  coverage: {
    records: number
    ships: string[]
    routes: string[]
    seasons: string[]
    sails: string[]
    speeds_kn: number[]
    weather_years: number[]
    generated_at: string
    insight_records: number
  }
  guardrails: {
    screening_cap_pct: number | null
    compatibility_derating: string
    benchmark_ranges: Record<string, { lo: number; hi: number; refs: string }>
  }
  limitations: string[]
  reproducibility: {
    physics_grid: string
    insights_grid: string
    bootstrap_method: string
    bootstrap_samples: number | null
    bootstrap_seed: number | null
    dockerized: boolean
    ci_tests: number
    single_source_kpi: string
  }
}

export function getAudit(): Promise<AuditResult> {
  return jget<AuditResult>('/api/audit')
}

export interface WindResourceSummary {
  mean_true_wind_ms: number
  mean_apparent_wind_ms: number
  net_saving_contribution_hours_pct: number
  low_wind_hours_pct: number
  headwind_hours_pct: number
  beam_reach_hours_pct: number
  tailwind_hours_pct: number
  wind_speed_hist: { bins: number[]; pct: number[] }
  relative_angle_hist: { bins_deg: number[]; pct: number[] }
}

export interface WindResourceResult {
  available: boolean
  reason?: string
  ship?: string
  route?: string
  route_name?: string
  season?: string
  sail?: string
  sail_label?: string
  speed_used?: number
  summary?: WindResourceSummary
  interpretation?: {
    fit_level: 'good' | 'medium' | 'poor'
    main_reason_key: string
  }
  basis?: { weather_years: number[] }
}

export async function postWindResource(
  req: ScenarioRequest,
  signal?: AbortSignal,
): Promise<WindResourceResult> {
  const r = await fetch('/api/wind-resource', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
    signal,
  })
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}))
    throw new Error((detail as { detail?: string }).detail ?? `HTTP ${r.status}`)
  }
  return r.json() as Promise<WindResourceResult>
}
