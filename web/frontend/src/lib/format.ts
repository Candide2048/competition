// 数值/货币/单位格式化 —— 展示层，绝不参与计算。
export const fmtInt = (v: number) => Math.round(v).toLocaleString('en-US')

export const fmtUsd = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `$${Math.round(v).toLocaleString('en-US')}`

export const fmtUsdSigned = (v: number) =>
  `${v < 0 ? '-' : ''}$${Math.round(Math.abs(v)).toLocaleString('en-US')}`

export const fmtUsdCompact = (v: number) => {
  const formatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: Math.abs(v) >= 1_000_000 ? 2 : 0,
  }).format(v)
  return formatted.replace('-', '−')
}

export const fmtPayback = (v: number | null | undefined, locale: 'zh' | 'en' = 'zh') =>
  v === null || v === undefined
    ? (locale === 'en' ? 'N/A' : '不可回收')
    : `${v.toFixed(1)} ${locale === 'en' ? 'yr' : '年'}`

export const reduceMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches
