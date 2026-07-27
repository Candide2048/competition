# -*- coding: utf-8 -*-
"""模型可信度 / 审计摘要 —— 面向评审的"非黑箱"证据汇总

无重算法：只汇总已有 metadata、guardrail、benchmark、文献来源与限制。
所有数字来自加载时的网格/产物元信息，不在线上动态跑 pytest。
文本按 locale ("zh"|"en") 单语返回，语义真源在后端（前端零复制）。
"""

from __future__ import annotations

# 测试数快照（离线 `pytest --collect-only -q` 统计；随测试增长手工更新）
CI_TEST_COUNT = 277

# 模型链路：每级的角色、数据/文献来源与校核方式（静态描述，可审计表达）
MODEL_CHAIN_ZH = [
    {
        "name": "ERA5 风场采样",
        "source": "Copernicus ERA5 逐小时 u10/v10 再分析",
        "role": "航线沿程真风场（速度/方向），季节代表航次逐小时采样",
        "validation": "ECMWF 官方再分析产品，全球风速偏差文献 <0.5 m/s",
    },
    {
        "name": "Holtrop-Mennen 阻力模型",
        "source": "Holtrop & Mennen (1982) 经验回归",
        "role": "裸船体静水阻力 → 主机功率与基线油耗",
        "validation": "对照 SIMMAN/KVLCC2 公开基准，阻力偏差目标 <5%",
    },
    {
        "name": "风帆气动力模型",
        "source": "Flettner / 刚性翼帆 / 吸力帆 公开升阻系数曲线",
        "role": "视风 → 帆推力与侧向力（含失速与低风截止）",
        "validation": "节油率与 Norsepower / Oceanbird / bound4blue 公开案例区间对照",
    },
    {
        "name": "推力平衡与节油",
        "source": "帆推力抵扣螺旋桨推力 → SFOC 折算油耗",
        "role": "逐小时功率平衡积分出单航次节油量",
        "validation": "30% 筛查上限 guardrail + 兼容性 derating 双重钳制",
    },
    {
        "name": "CII 评级",
        "source": "IMO MEPC.353(78) G2 参考线（2023-2026 折减系数）",
        "role": "AER 与 A-E 评级、改善幅度",
        "validation": "roro/PCTC 按 GT 容量基数，其余 DWT，与法规文本一致",
    },
    {
        "name": "经济性评估",
        "source": "燃油成本 + 影子碳价 + 折现现金流（NPV/回收期）",
        "role": "年净节省、20 年 NPV、回收期",
        "validation": "与主 KPI 同一 evaluate_cell 单源公式，前后端零复制",
    },
    {
        "name": "不确定性量化",
        "source": "24h 环块自助法（circular block bootstrap）× 500 重采样",
        "role": "节油率/NPV 的 P10/P50/P90 置信区间与风险概率",
        "validation": "固定随机种子可复现；分位数经单调经济变换保持有效",
    },
]

MODEL_CHAIN_EN = [
    {
        "name": "ERA5 wind sampling",
        "source": "Copernicus ERA5 hourly u10/v10 reanalysis",
        "role": "True wind (speed/direction) along the route, sampled hourly on seasonal representative voyages",
        "validation": "Official ECMWF reanalysis; published global wind-speed bias <0.5 m/s",
    },
    {
        "name": "Holtrop-Mennen resistance model",
        "source": "Holtrop & Mennen (1982) empirical regression",
        "role": "Bare-hull calm-water resistance → main-engine power and baseline fuel",
        "validation": "Checked against SIMMAN/KVLCC2 public benchmarks; resistance deviation target <5%",
    },
    {
        "name": "Sail aerodynamic models",
        "source": "Published lift/drag curves for Flettner, rigid wing and suction wing sails",
        "role": "Apparent wind → sail thrust and side force (incl. stall and low-wind cut-off)",
        "validation": "Saving rates cross-checked against Norsepower / Oceanbird / bound4blue published case ranges",
    },
    {
        "name": "Thrust balance & fuel saving",
        "source": "Sail thrust offsets propeller thrust → fuel via SFOC",
        "role": "Hourly power balance integrated into per-voyage fuel saving",
        "validation": "Double-clamped by the 30% screening cap guardrail and compatibility derating",
    },
    {
        "name": "CII rating",
        "source": "IMO MEPC.353(78) G2 reference lines (2023-2026 reduction factors)",
        "role": "AER, A-E rating and improvement margin",
        "validation": "GT capacity basis for ro-ro/PCTC, DWT otherwise, consistent with the regulation text",
    },
    {
        "name": "Economic evaluation",
        "source": "Fuel cost + shadow carbon price + discounted cash flow (NPV/payback)",
        "role": "Annual net savings, 20-year NPV, payback period",
        "validation": "Same single-source evaluate_cell formula as the main KPIs; zero front-end duplication",
    },
    {
        "name": "Uncertainty quantification",
        "source": "24h circular block bootstrap × 500 resamples",
        "role": "P10/P50/P90 intervals and risk probabilities for saving rate / NPV",
        "validation": "Reproducible with a fixed random seed; quantiles remain valid under monotone economic transforms",
    },
]

# 已知限制（诚实呈现给评审）
LIMITATIONS_ZH = [
    "ERA5 天气目前仅覆盖 2025 单年，未包含多年际风资源波动",
    "无船东专有 noon-report 油耗日志，节油率以公开实船报道区间为外部校核",
    "标准网格采用代表性船体几何（KVLCC2 等公开船模），非具体在营船舶",
    "帆型气动系数取自公开文献，未做 CFD/风洞逐帆验证",
    "经济性假设（油价/影子碳价/维护率/折现率）由用户滑杆输入，结果随假设变化",
    "每船装机数固定（4 转子 / 1 刚翼 / 6 吸力翼），未做数量/布置优化，未计入多帆遮蔽、横倾与稳性约束",
    "兼容性因子为启发式筛选系数，非船级审批或实船校准的性能折减值",
    "未覆盖的 WASP 技术：拖曳风筝（Airseas Seawing）、充气软翼（Michelin WISAMO）、DynaRig 等，因公开商业实绩不足暂不建模",
    "5 条航线均位于中东—亚洲季风走廊，结论外推至其他海区需重新评估",
]

LIMITATIONS_EN = [
    "ERA5 weather currently covers the single year 2025; inter-annual wind variability is not included",
    "No proprietary noon-report fuel logs; saving rates are externally checked against published in-service ranges",
    "The standard grid uses representative hull geometries (public models such as KVLCC2), not specific in-service ships",
    "Sail aerodynamic coefficients come from public literature; no per-sail CFD/wind-tunnel validation",
    "Economic assumptions (fuel price / shadow carbon price / maintenance / discount rate) are user slider inputs; results vary with them",
    "Sail counts are fixed per ship (4 rotors / 1 rigid wing / 6 suction wings); no count/layout optimisation, and multi-sail interaction, heel and stability constraints are not modelled",
    "Compatibility factors are heuristic screening coefficients, not class-approved or sea-trial-calibrated performance deratings",
    "WASP technologies not covered: towing kites (Airseas Seawing), inflatable soft wings (Michelin WISAMO), DynaRig, etc., excluded for insufficient public commercial track record",
    "All 5 routes lie in the Middle East-Asia monsoon corridor; extrapolation to other sea areas requires re-evaluation",
]

# 按 locale 切换的短文案（guardrail / 复现性描述）
AUDIT_TEXT = {
    "zh": {
        "compatibility_derating": (
            "船型×帆型兼容性因子 ∈ [0,1]，启发式筛选系数"
            "（非船级审批/实船校准值），先于一切经济/CII 后处理"),
        "single_source_kpi": (
            "前端不做任何经济公式复制，全部经 evaluate_cell 单源计算"),
    },
    "en": {
        "compatibility_derating": (
            "Ship×sail compatibility factor ∈ [0,1], a heuristic screening "
            "coefficient (not a class-approved or sea-trial-calibrated value), "
            "applied before all economic/CII post-processing"),
        "single_source_kpi": (
            "The front end duplicates no economic formulas; everything goes "
            "through the single-source evaluate_cell computation"),
    },
}

# 向后兼容别名（test_audit 以同一性断言引用）
MODEL_CHAIN = MODEL_CHAIN_ZH
LIMITATIONS = LIMITATIONS_ZH


def build_audit_summary(meta: dict, df, insights_meta: dict | None = None,
                        bench_ranges: dict | None = None,
                        screening_cap: float | None = None,
                        locale: str = "zh") -> dict:
    """网格/产物 metadata → 审计摘要（纯汇总，零重算）

    Args:
        meta:          load_grid() 的 metadata
        df:            物理网格 DataFrame（只取 len）
        insights_meta: load_insights() 的 metadata（缺省则不确定性字段降级）
        bench_ranges:  {sail: (lo, hi, refs)} 公开案例参考范围
        screening_cap: 30% 筛查上限（%）
        locale:        "zh" | "en"，静态文本语言
    """
    if locale not in ("zh", "en"):
        raise ValueError(f"locale 必须为 zh|en，收到 {locale!r}")
    insights_meta = insights_meta or {}
    bench_ranges = bench_ranges or {}
    text = AUDIT_TEXT[locale]

    coverage = {
        "records": int(len(df)),
        "ships": list(meta.get("ships", [])),
        "routes": list(meta.get("routes", {}).keys()),
        "seasons": list(meta.get("seasons", {}).keys()),
        "sails": list(meta.get("sail_types", [])),
        "speeds_kn": [float(s) for s in meta.get("speeds_kn", [])],
        "weather_years": list(insights_meta.get(
            "weather_years", [meta.get("era5_year", 2025)])),
        "generated_at": meta.get("generated_at", ""),
        "insight_records": int(insights_meta.get("n_records", 0)),
    }

    guardrails = {
        "screening_cap_pct": (float(screening_cap)
                              if screening_cap is not None else None),
        "compatibility_derating": text["compatibility_derating"],
        "benchmark_ranges": {
            sail: {"lo": lo, "hi": hi, "refs": refs}
            for sail, (lo, hi, refs) in bench_ranges.items()
        },
    }

    bootstrap = insights_meta.get("bootstrap", {})
    reproducibility = {
        "physics_grid": "code/results/precomputed/physics_grid.json",
        "insights_grid": "code/results/precomputed/scenario_insights.json",
        "bootstrap_method": bootstrap.get("method", ""),
        "bootstrap_samples": bootstrap.get("n_samples"),
        "bootstrap_seed": bootstrap.get("seed"),
        "dockerized": True,
        "ci_tests": CI_TEST_COUNT,
        "single_source_kpi": text["single_source_kpi"],
    }

    return {
        "model_chain": MODEL_CHAIN_ZH if locale == "zh" else MODEL_CHAIN_EN,
        "coverage": coverage,
        "guardrails": guardrails,
        "limitations": LIMITATIONS_ZH if locale == "zh" else LIMITATIONS_EN,
        "reproducibility": reproducibility,
    }
