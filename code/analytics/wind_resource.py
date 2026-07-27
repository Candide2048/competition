# -*- coding: utf-8 -*-
"""风资源适配摘要 — 单航次 hourly 序列 → 风速/相对风角分布与有效推力占比

物理口径（与 simulate_voyage 完全同源，不重算）:
    hourly 数组由 simulate_voyage(collect_hourly=True) 逐小时收集：
    true_wind_ms / apparent_wind_ms / relative_wind_angle_deg / thrust_kN /
    effective（视风 >= MIN_EFFECTIVE_WIND_SPEED）。本模块只做统计分箱。

分箱约定:
    风速 0-3-6-9-12-15-20-30 m/s（末箱吸收 >30 的极端值）
    相对风角 0-30-...-180°（0=顶风，180=顺风；beta 已折叠到 [0, π]）
"""
import numpy as np

WIND_SPEED_BINS_MS = [0.0, 3.0, 6.0, 9.0, 12.0, 15.0, 20.0, 30.0]
RELATIVE_ANGLE_BINS_DEG = [0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0]

# 低风阈值（m/s）：真风低于此值基本无可用风资源
LOW_WIND_THRESHOLD_MS = 3.0
# 适配度判级阈值（基于有效推力小时占比，%）
FIT_GOOD_THRESHOLD_PCT = 60.0
FIT_MEDIUM_THRESHOLD_PCT = 35.0


def _histogram_pct(values: np.ndarray, bins: list[float]) -> list[float]:
    """值 → 分箱占比（%），越界值截断进两端箱"""
    v = np.clip(np.asarray(values, dtype=float), bins[0], bins[-1] - 1e-9)
    counts, _ = np.histogram(v, bins=bins)
    total = counts.sum()
    if total == 0:
        return [0.0] * (len(bins) - 1)
    return [round(float(c) / total * 100.0, 2) for c in counts]


def circular_angle_histogram(deg: np.ndarray,
                             bins: list[float] = None) -> dict:
    """相对风角（0-180°，已折叠）分箱占比"""
    if bins is None:
        bins = RELATIVE_ANGLE_BINS_DEG
    return {
        "bins_deg": [float(b) for b in bins],
        "pct": _histogram_pct(deg, list(bins)),
    }


def summarize_wind_resource(hourly: dict) -> dict:
    """hourly 数组 → 风资源摘要（占比、直方图、适配判级）

    Args:
        hourly: simulate_voyage(collect_hourly=True) 的 hourly dict
    Returns:
        dict: 均值/占比标量 + wind_speed_hist + relative_angle_hist
              + interpretation（fit_level / main_reason_key）
    """
    true_wind = np.asarray(hourly["true_wind_ms"], dtype=float)
    app_wind = np.asarray(hourly["apparent_wind_ms"], dtype=float)
    angle = np.asarray(hourly["relative_wind_angle_deg"], dtype=float)
    thrust = np.asarray(hourly["thrust_kN"], dtype=float)
    effective = np.asarray(hourly["effective"], dtype=bool)
    n = true_wind.size
    if n == 0:
        raise ValueError("hourly 数组为空")

    pct = lambda mask: round(float(mask.sum()) / n * 100.0, 2)  # noqa: E731

    effective_pct = pct(effective)
    positive_thrust_pct = pct(thrust > 0.0)
    low_wind_pct = pct(true_wind < LOW_WIND_THRESHOLD_MS)
    headwind_pct = pct(angle < 60.0)
    beam_pct = pct((angle >= 60.0) & (angle < 120.0))
    tailwind_pct = pct(angle >= 120.0)

    # 适配判级：有效推力小时占比为主，主因取占比最高的角区间/低风
    if positive_thrust_pct >= FIT_GOOD_THRESHOLD_PCT:
        fit = "good"
    elif positive_thrust_pct >= FIT_MEDIUM_THRESHOLD_PCT:
        fit = "medium"
    else:
        fit = "poor"
    if low_wind_pct >= 40.0:
        reason = "low_wind_dominant"
    elif beam_pct >= max(headwind_pct, tailwind_pct):
        reason = "beam_reach_dominant"
    elif headwind_pct >= tailwind_pct:
        reason = "headwind_dominant"
    else:
        reason = "tailwind_dominant"

    return {
        "mean_true_wind_ms": round(float(true_wind.mean()), 2),
        "mean_apparent_wind_ms": round(float(app_wind.mean()), 2),
        "effective_hours_pct": effective_pct,
        "positive_thrust_hours_pct": positive_thrust_pct,
        "low_wind_hours_pct": low_wind_pct,
        "headwind_hours_pct": headwind_pct,
        "beam_reach_hours_pct": beam_pct,
        "tailwind_hours_pct": tailwind_pct,
        "wind_speed_hist": {
            "bins": [float(b) for b in WIND_SPEED_BINS_MS],
            "pct": _histogram_pct(true_wind, WIND_SPEED_BINS_MS),
        },
        "relative_angle_hist": circular_angle_histogram(angle),
        "interpretation": {
            "fit_level": fit,
            "main_reason_key": reason,
        },
    }
