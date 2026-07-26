export interface CashflowPoint {
  year: number
  cumulative: number
}

/**
 * 从现金流数组中找到回本年份（线性插值到零线交叉点）。
 * 如果未找到返回 null。
 */
export function findBreakevenYear(points: CashflowPoint[]): number | null {
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
