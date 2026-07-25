// 累计现金流计算 —— 纯前端推导，不改后端。
// 用于 CashflowChart SVG 和 KPI "20年累计收益" 展示。

const DISCOUNT_RATE = 0.08
const MAINTENANCE_RATE = 0.02

export interface CashflowPoint {
  year: number
  cumulative: number
}

/**
 * 计算 0-N 年累计净现金流（含贴现 + 维护）。
 * 默认自动延伸到回本后 +5 年（最少 20，最多 40），
 * 确保评委和船东能看到“开始赚钱”的拐点。
 */
export function computeCashflow(
  initialCost: number,
  annualSavings: number,
  fixedYears?: number,
): CashflowPoint[] {
  // 如果调用方指定了年数，就用固定年数
  if (fixedYears !== undefined) {
    return buildPoints(initialCost, annualSavings, fixedYears)
  }
  // 自动延伸：先算 40 年，找到回本点后取 breakeven+5，最少显示 20 年
  const full = buildPoints(initialCost, annualSavings, 40)
  const beYear = findBreakevenYearFromPoints(full)
  let showYears = 20
  if (beYear !== null) {
    showYears = Math.max(20, Math.ceil(beYear) + 5)
  } else {
    showYears = 40 // 仍未回本就展示全部 40 年
  }
  return full.slice(0, showYears + 1)
}

function buildPoints(initialCost: number, annualSavings: number, years: number): CashflowPoint[] {
  const points: CashflowPoint[] = [{ year: 0, cumulative: -initialCost }]
  let cum = -initialCost
  for (let t = 1; t <= years; t++) {
    const netFlow =
      (annualSavings * Math.pow(1 - MAINTENANCE_RATE, t)) /
      Math.pow(1 + DISCOUNT_RATE, t)
    cum += netFlow
    points.push({ year: t, cumulative: cum })
  }
  return points
}

/**
 * 从现金流数组中找到回本年份（线性插值到零线交叉点）。
 * 如果未找到返回 null。
 */
export function findBreakevenYear(points: CashflowPoint[]): number | null {
  return findBreakevenYearFromPoints(points)
}

function findBreakevenYearFromPoints(points: CashflowPoint[]): number | null {
  for (let i = 1; i < points.length; i++) {
    if (points[i].cumulative >= 0 && points[i - 1].cumulative < 0) {
      const frac =
        -points[i - 1].cumulative /
        (points[i].cumulative - points[i - 1].cumulative)
      return points[i - 1].year + frac
    }
  }
  if (points.length > 0 && points[0].cumulative >= 0) return 0
  return null
}

/**
 * 估算 CII 不合规年度罚款避免金额。
 * 如果 baseline 评级为 D 或 E，船东面临 EU ETS 额外碳成本风险。
 * 简化估算：penalty_avoided ≈ co2_reduced_t * co2_price * trips_per_year
 */
export function estimateCiiPenaltyAvoided(
  baselineRating: string,
  co2ReducedPerTrip: number,
  co2PriceEurPerT: number,
  tripsPerYear: number,
): number {
  if (baselineRating === 'D' || baselineRating === 'E') {
    return co2ReducedPerTrip * co2PriceEurPerT * 1.08 * tripsPerYear
  }
  // C→B 跃迁也有避免未来降级的预防性价值，按 30% 估算
  if (baselineRating === 'C') {
    return co2ReducedPerTrip * co2PriceEurPerT * 1.08 * tripsPerYear * 0.3
  }
  return 0
}
