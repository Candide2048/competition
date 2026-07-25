// 累计现金流计算 —— 纯前端推导，不改后端。
// 用于 CashflowChart SVG 和 KPI "20年累计收益" 展示。

const DISCOUNT_RATE = 0.08
const MAINTENANCE_RATE = 0.02

export interface CashflowPoint {
  year: number
  cumulative: number
}

/**
 * 计算 0-20 年累计净现金流（含贴现 + 维护）。
 * cashflow[0] = -initialCost
 * cashflow[t] = cashflow[t-1] + annualSavings * (1-maintenance)^t / (1+discount)^t
 */
export function computeCashflow(
  initialCost: number,
  annualSavings: number,
  years = 20,
): CashflowPoint[] {
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
 * 如果 20 年内未回本返回 null。
 */
export function findBreakevenYear(points: CashflowPoint[]): number | null {
  for (let i = 1; i < points.length; i++) {
    if (points[i].cumulative >= 0 && points[i - 1].cumulative < 0) {
      // 线性插值
      const frac =
        -points[i - 1].cumulative /
        (points[i].cumulative - points[i - 1].cumulative)
      return points[i - 1].year + frac
    }
  }
  // 初始就为正（极端情况）
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
