# -*- coding: utf-8 -*-
"""Phase B 效益矩阵可视化

读取 phase_b_matrix_*.json，产出申报书/答辩用的出版级图表：
    1. 节油率热力图网格   (3 帆型 × 航线×季节)          saving_heatmap.png
    2. 帆型对比条形图     (均值 + 最小/最大须)            sail_comparison.png
    3. 季节节油率折线图   (季风季节性，按航线平均)         seasonal_pattern.png
    4. 经济性对比         (回收期 + NPV20)                 economics.png
    5. CII 评级改善       (基线 vs 有帆)                   cii_improvement.png

用法:
    python -m pipelines.visualize_matrix                 # 用最新矩阵 JSON
    python -m pipelines.visualize_matrix <matrix.json>   # 指定文件

输出目录: results/figures/
"""
import os
import sys
import glob
import json

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(CODE_DIR, "results")
FIG_DIR = os.path.join(RESULTS_DIR, "figures")

# ---------- 中文字体 ----------
_CN_CANDIDATES = ["Microsoft YaHei", "SimHei", "Microsoft JhengHei", "SimSun"]
_available = {f.name for f in font_manager.fontManager.ttflist}
for _f in _CN_CANDIDATES:
    if _f in _available:
        plt.rcParams["font.sans-serif"] = [_f]
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130
plt.rcParams["savefig.bbox"] = "tight"

# 帆型显示名与配色（色盲友好）
SAIL_LABELS = {
    "flettner": "Flettner 旋筒帆",
    "rigid_wing": "刚性翼帆",
    "suction_wing": "吸力帆",
}
SAIL_COLORS = {
    "flettner": "#1b9e77",
    "rigid_wing": "#d95f02",
    "suction_wing": "#7570b3",
}
ROUTE_LABELS = {
    "middle_east_china": "中东-中国",
    "arabian_sea": "阿拉伯海",
    "bay_of_bengal": "孟加拉湾",
    "south_china_sea": "南海",
    "indian_ocean_monsoon": "印度洋季风",
}
SEASON_LABELS = {"winter": "冬", "spring": "春", "summer": "夏", "autumn": "秋"}


def find_latest_matrix() -> str:
    files = glob.glob(os.path.join(RESULTS_DIR, "phase_b_matrix_*.json"))
    if not files:
        raise FileNotFoundError("未找到 phase_b_matrix_*.json，请先运行 phase_b_matrix")
    return max(files, key=os.path.getmtime)


def load_matrix(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _sail_types(result: dict) -> list:
    return list(result["metadata"]["sail_install"].keys())


def _routes_seasons(result: dict):
    matrix = result["matrix"]
    routes = list(matrix.keys())
    seasons = list(next(iter(matrix.values()))["seasons"].keys())
    return routes, seasons


def _grid(result: dict, sail: str, field: str) -> np.ndarray:
    """提取 route × season 的某字段矩阵"""
    matrix = result["matrix"]
    routes, seasons = _routes_seasons(result)
    arr = np.full((len(routes), len(seasons)), np.nan)
    for i, r in enumerate(routes):
        for j, s in enumerate(seasons):
            cell = matrix[r]["seasons"][s]["sails"][sail]
            val = cell.get(field)
            if val is not None:
                arr[i, j] = val
    return arr


# ═══════════════════════════════════════════════════════════
# 图 1：节油率热力图网格
# ═══════════════════════════════════════════════════════════

def fig_saving_heatmap(result: dict) -> str:
    sails = _sail_types(result)
    routes, seasons = _routes_seasons(result)
    rlabels = [ROUTE_LABELS.get(r, r) for r in routes]
    slabels = [SEASON_LABELS.get(s, s) for s in seasons]

    # 统一色标范围
    all_vals = np.concatenate([_grid(result, st, "saving_rate_pct").ravel()
                               for st in sails])
    vmax = np.nanmax(all_vals)
    vmin = min(0.0, np.nanmin(all_vals))

    fig, axes = plt.subplots(1, len(sails), figsize=(4.2 * len(sails), 4.4))
    if len(sails) == 1:
        axes = [axes]
    im = None
    for k, (ax, st) in enumerate(zip(axes, sails)):
        grid = _grid(result, st, "saving_rate_pct")
        im = ax.imshow(grid, cmap="RdYlGn", vmin=vmin, vmax=vmax, aspect="auto")
        ax.set_xticks(range(len(seasons)))
        ax.set_xticklabels(slabels)
        if k == 0:
            ax.set_yticks(range(len(routes)))
            ax.set_yticklabels(rlabels)
        else:
            ax.set_yticks([])
        ax.set_title(SAIL_LABELS.get(st, st), fontsize=11, fontweight="bold")
        for i in range(len(routes)):
            for j in range(len(seasons)):
                v = grid[i, j]
                if not np.isnan(v):
                    ax.text(j, i, f"{v:.1f}", ha="center", va="center",
                            fontsize=8, color="black")
    fig.suptitle("WASP 节油率效益矩阵 — 航线 × 季节 × 帆型 (%)",
                 fontsize=13, fontweight="bold")
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="节油率 (%)")
    out = os.path.join(FIG_DIR, "saving_heatmap.png")
    fig.savefig(out)
    plt.close(fig)
    return out


# ═══════════════════════════════════════════════════════════
# 图 2：帆型对比条形图（均值 + 最小/最大须）
# ═══════════════════════════════════════════════════════════

def fig_sail_comparison(result: dict) -> str:
    sails = _sail_types(result)
    means, mins, maxs = [], [], []
    for st in sails:
        vals = _grid(result, st, "saving_rate_pct").ravel()
        vals = vals[~np.isnan(vals)]
        means.append(vals.mean())
        mins.append(vals.min())
        maxs.append(vals.max())

    x = np.arange(len(sails))
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    colors = [SAIL_COLORS.get(st, "#888") for st in sails]
    lower = np.array(means) - np.array(mins)
    upper = np.array(maxs) - np.array(means)
    ax.bar(x, means, color=colors, alpha=0.85,
           yerr=[lower, upper], capsize=6, ecolor="#333", width=0.55)
    for xi, m in zip(x, means):
        ax.text(xi, m + 0.3, f"{m:.1f}%", ha="center", fontweight="bold")
    # 文献参考带 5-15%
    ax.axhspan(5, 15, color="#4d79ff", alpha=0.08)
    ax.axhline(5, color="#4d79ff", ls="--", lw=0.8)
    ax.axhline(15, color="#4d79ff", ls="--", lw=0.8)
    ax.text(len(sails) - 0.5, 15.2, "文献参考区间 5–15%",
            color="#4d79ff", fontsize=8, ha="right")
    ax.set_xticks(x)
    ax.set_xticklabels([SAIL_LABELS.get(st, st) for st in sails])
    ax.set_ylabel("节油率 (%)")
    ax.set_title("三帆型跨情景节油率对比（均值±极值，等面积归一化）",
                 fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    out = os.path.join(FIG_DIR, "sail_comparison.png")
    fig.savefig(out)
    plt.close(fig)
    return out


# ═══════════════════════════════════════════════════════════
# 图 3：季节节油率折线图（按航线平均）
# ═══════════════════════════════════════════════════════════

def fig_seasonal_pattern(result: dict) -> str:
    sails = _sail_types(result)
    routes, seasons = _routes_seasons(result)
    slabels = [SEASON_LABELS.get(s, s) for s in seasons]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = np.arange(len(seasons))
    for st in sails:
        grid = _grid(result, st, "saving_rate_pct")  # route × season
        season_mean = np.nanmean(grid, axis=0)
        ax.plot(x, season_mean, "-o", color=SAIL_COLORS.get(st, "#888"),
                label=SAIL_LABELS.get(st, st), lw=2, ms=7)
    ax.set_xticks(x)
    ax.set_xticklabels(slabels)
    ax.set_xlabel("季节")
    ax.set_ylabel("平均节油率 (%)")
    ax.set_title("节油率季节性（跨 %d 条航线平均）— 季风驱动" % len(routes),
                 fontsize=12, fontweight="bold")
    ax.legend()
    ax.grid(alpha=0.3)
    out = os.path.join(FIG_DIR, "seasonal_pattern.png")
    fig.savefig(out)
    plt.close(fig)
    return out


# ═══════════════════════════════════════════════════════════
# 图 4：经济性对比（回收期 + NPV20）
# ═══════════════════════════════════════════════════════════

def fig_economics(result: dict) -> str:
    sails = _sail_types(result)
    # 取各帆型跨情景中位回收期与 NPV20（忽略 None）
    pb_med, npv_med = [], []
    for st in sails:
        pb = _grid(result, st, "payback_years").ravel()
        pb = pb[~np.isnan(pb)]
        npv20 = _grid(result, st, "npv_20y_usd").ravel()
        npv20 = npv20[~np.isnan(npv20)]
        pb_med.append(np.median(pb) if pb.size else np.nan)
        npv_med.append(np.median(npv20) / 1e6 if npv20.size else np.nan)

    x = np.arange(len(sails))
    colors = [SAIL_COLORS.get(st, "#888") for st in sails]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    ax1.bar(x, pb_med, color=colors, alpha=0.85, width=0.55)
    for xi, v in zip(x, pb_med):
        if not np.isnan(v):
            ax1.text(xi, v + 0.3, f"{v:.1f}", ha="center", fontweight="bold")
    ax1.axhline(20, color="red", ls="--", lw=0.8)
    ax1.text(len(sails) - 0.5, 20.3, "20 年设计寿命", color="red",
             fontsize=8, ha="right")
    ax1.set_xticks(x)
    ax1.set_xticklabels([SAIL_LABELS.get(st, st) for st in sails], fontsize=9)
    ax1.set_ylabel("回收期 (年)")
    ax1.set_title("投资回收期（跨情景中位数）", fontsize=11, fontweight="bold")
    ax1.grid(axis="y", alpha=0.3)

    barcolors = ["#2ca02c" if v >= 0 else "#d62728" for v in npv_med]
    ax2.bar(x, npv_med, color=barcolors, alpha=0.85, width=0.55)
    for xi, v in zip(x, npv_med):
        if not np.isnan(v):
            off = 0.05 if v >= 0 else -0.15
            ax2.text(xi, v + off, f"{v:.2f}", ha="center", fontweight="bold")
    ax2.axhline(0, color="#333", lw=0.8)
    ax2.set_xticks(x)
    ax2.set_xticklabels([SAIL_LABELS.get(st, st) for st in sails], fontsize=9)
    ax2.set_ylabel("NPV@20年 (百万美元)")
    ax2.set_title("20 年净现值（跨情景中位数）", fontsize=11, fontweight="bold")
    ax2.grid(axis="y", alpha=0.3)

    fig.suptitle("WASP 经济性对比", fontsize=13, fontweight="bold")
    out = os.path.join(FIG_DIR, "economics.png")
    fig.savefig(out)
    plt.close(fig)
    return out


# ═══════════════════════════════════════════════════════════
# 图 5：CII 改善（基线 vs 有帆，取最优情景）
# ═══════════════════════════════════════════════════════════

def fig_cii_improvement(result: dict) -> str:
    sails = _sail_types(result)
    imp_mean = []
    for st in sails:
        vals = _grid(result, st, "cii_improvement_pct").ravel()
        vals = vals[~np.isnan(vals)]
        imp_mean.append(vals.mean() if vals.size else np.nan)

    x = np.arange(len(sails))
    colors = [SAIL_COLORS.get(st, "#888") for st in sails]
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.bar(x, imp_mean, color=colors, alpha=0.85, width=0.55)
    for xi, v in zip(x, imp_mean):
        if not np.isnan(v):
            ax.text(xi, v + 0.1, f"{v:.1f}%", ha="center", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([SAIL_LABELS.get(st, st) for st in sails])
    ax.set_ylabel("CII 改善 (%)")
    ax.set_title("平均 CII 强度改善（MEPC.353(78) G2 参考线）",
                 fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    out = os.path.join(FIG_DIR, "cii_improvement.png")
    fig.savefig(out)
    plt.close(fig)
    return out


def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    path = sys.argv[1] if len(sys.argv) > 1 else find_latest_matrix()
    print(f"[可视化] 读取矩阵: {os.path.basename(path)}")
    result = load_matrix(path)

    outs = [
        fig_saving_heatmap(result),
        fig_sail_comparison(result),
        fig_seasonal_pattern(result),
        fig_economics(result),
        fig_cii_improvement(result),
    ]
    print("[可视化] 已生成:")
    for o in outs:
        print(f"    {o}")


if __name__ == "__main__":
    main()
