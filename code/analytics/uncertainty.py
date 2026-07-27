# -*- coding: utf-8 -*-
"""不确定性量化 — 单航次 hourly 序列的 circular block bootstrap

设计（与计算分层一致）:
    物理层（离线）  simulate_voyage(collect_hourly=True) 产出 hourly 数组，
                    本模块做 24h circular block bootstrap，只汇总物理量分位数
                    （fuel_baseline_kg / fuel_saved_kg / saving_rate_pct）。
    后处理层（在线）经济性（annual_savings / NPV / payback）由 API 按当前
                    油价、碳价、成本从 fuel_saved_kg 分位数实时后处理，
                    分位数网格足够密（5%..95%）可插值 P(NPV>0)。

方法学:
    - 块大小 24h：保留日内风场自相关（昼夜循环）。
    - circular：块起点均匀随机，越界回绕，避免端点欠采样。
    - 固定 seed：结果可复现（写入产物 metadata）。

局限（诚实声明）:
    bootstrap 只量化单年（ERA5 2025）航线风场的日间组合不确定性，
    不覆盖年际气候变率；产物 metadata 与前端均须注明 weather_years。
"""
import numpy as np

DEFAULT_BLOCK_H = 24
DEFAULT_N_SAMPLES = 500
DEFAULT_SEED = 20260727

# 分位数网格（5%..95% 步长 5%），P10/P50/P90 为其子集；
# 网格足够密，供 API 端对单调变换（NPV 等）插值越零概率。
QUANTILE_GRID = [round(q, 2) for q in np.arange(0.05, 0.951, 0.05)]


def block_bootstrap_indices(n_hours: int, block_h: int,
                            n_samples: int, seed: int) -> list[np.ndarray]:
    """生成 circular block bootstrap 的重采样索引

    每个样本由 ceil(n_hours/block_h) 个随机起点的连续 block_h 小时块
    拼接后截断到 n_hours（回绕取模）。

    Returns:
        list[np.ndarray]: n_samples 个长度为 n_hours 的索引数组
    """
    if n_hours <= 0:
        raise ValueError(f"n_hours 必须为正: {n_hours}")
    if block_h <= 0:
        raise ValueError(f"block_h 必须为正: {block_h}")
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n_hours / block_h))
    offsets = np.arange(block_h)
    samples = []
    for _ in range(n_samples):
        starts = rng.integers(0, n_hours, size=n_blocks)
        idx = (starts[:, None] + offsets[None, :]).ravel() % n_hours
        samples.append(idx[:n_hours])
    return samples


def summarize_bootstrap_hourly(hourly: dict,
                               block_h: int = DEFAULT_BLOCK_H,
                               n_samples: int = DEFAULT_N_SAMPLES,
                               seed: int = DEFAULT_SEED) -> dict:
    """对单航次 hourly 数组做 block bootstrap，输出物理量分位数摘要

    Args:
        hourly: simulate_voyage(collect_hourly=True) 返回的 hourly dict，
                至少含 fuel_baseline_kg_h / fuel_saved_kg_h
    Returns:
        dict: method/n_samples/block_h/seed/n_hours
              + quantile_grid（q 与三个物理量的分位数组，等长）
              + quantiles.p10/p50/p90（三物理量便捷摘要）
              + risk.prob_positive_fuel_saving
    """
    base = np.asarray(hourly["fuel_baseline_kg_h"], dtype=float)
    saved = np.asarray(hourly["fuel_saved_kg_h"], dtype=float)
    if base.shape != saved.shape:
        raise ValueError("fuel_baseline_kg_h 与 fuel_saved_kg_h 长度不一致")
    n = int(base.size)

    idx_list = block_bootstrap_indices(n, block_h, n_samples, seed)
    fuel_baseline = np.array([float(base[idx].sum()) for idx in idx_list])
    fuel_saved = np.array([float(saved[idx].sum()) for idx in idx_list])
    saving_rate = np.divide(fuel_saved, fuel_baseline,
                            out=np.zeros_like(fuel_saved),
                            where=fuel_baseline > 0) * 100.0

    q = np.asarray(QUANTILE_GRID, dtype=float)
    fb_q = np.quantile(fuel_baseline, q)
    fs_q = np.quantile(fuel_saved, q)
    sr_q = np.quantile(saving_rate, q)

    def _at(p: float) -> dict:
        i = int(np.argmin(np.abs(q - p)))
        return {
            "fuel_baseline_kg": round(float(fb_q[i]), 3),
            "fuel_saved_kg": round(float(fs_q[i]), 3),
            "saving_rate_pct": round(float(sr_q[i]), 4),
        }

    return {
        "method": f"{block_h}h circular block bootstrap over hourly route samples",
        "n_samples": int(n_samples),
        "block_h": int(block_h),
        "seed": int(seed),
        "n_hours": n,
        "quantile_grid": {
            "q": [float(v) for v in q],
            "fuel_baseline_kg": [round(float(v), 3) for v in fb_q],
            "fuel_saved_kg": [round(float(v), 3) for v in fs_q],
            "saving_rate_pct": [round(float(v), 4) for v in sr_q],
        },
        "quantiles": {"p10": _at(0.10), "p50": _at(0.50), "p90": _at(0.90)},
        "risk": {
            "prob_positive_fuel_saving": round(float((fuel_saved > 0).mean()), 4),
        },
    }


def prob_exceed_threshold(q: list[float], values: list[float],
                          threshold: float) -> float:
    """由分位数网格插值 P(X > threshold)（X 随分位数单调不减）

    用于 API 端对单调变换后的量（如 NPV 随 fuel_saved 单调）估算越零概率。
    """
    v = np.asarray(values, dtype=float)
    qs = np.asarray(q, dtype=float)
    if threshold < v[0]:
        return 1.0
    if threshold >= v[-1]:
        return round(float(1.0 - qs[-1]), 4)
    # v 单调不减，找 threshold 所在区间线性插值累计概率
    p = float(np.interp(threshold, v, qs))
    return round(1.0 - p, 4)
