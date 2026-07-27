# -*- coding: utf-8 -*-
"""模型可信度 / 审计摘要 —— 面向评审的"非黑箱"证据汇总

无重算法：只汇总已有 metadata、guardrail、benchmark、文献来源与限制。
所有数字来自加载时的网格/产物元信息，不在线上动态跑 pytest。
"""

from __future__ import annotations

# 测试数快照（离线 `pytest --collect-only -q` 统计；随测试增长手工更新）
CI_TEST_COUNT = 254

# 模型链路：每级的角色、数据/文献来源与校核方式（静态描述，可审计表达）
MODEL_CHAIN = [
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
        "validation": "节油率与 Norsepower / Oceanbird / bound4blue 实船报道区间对照",
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
        "source": "燃油成本 + EU ETS 碳价 + 折现现金流（NPV/回收期）",
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

# 已知限制（诚实呈现给评审）
LIMITATIONS = [
    "ERA5 天气目前仅覆盖 2025 单年，未包含多年际风资源波动",
    "无船东专有 noon-report 油耗日志，节油率以公开实船报道区间为外部校核",
    "标准网格采用代表性船体几何（KVLCC2 等公开船模），非具体在营船舶",
    "帆型气动系数取自公开文献，未做 CFD/风洞逐帆验证",
    "经济性假设（油价/碳价/维护率/折现率）由用户滑杆输入，结果随假设变化",
]


def build_audit_summary(meta: dict, df, insights_meta: dict | None = None,
                        bench_ranges: dict | None = None,
                        screening_cap: float | None = None) -> dict:
    """网格/产物 metadata → 审计摘要（纯汇总，零重算）

    Args:
        meta:          load_grid() 的 metadata
        df:            物理网格 DataFrame（只取 len）
        insights_meta: load_insights() 的 metadata（缺省则不确定性字段降级）
        bench_ranges:  {sail: (lo, hi, refs)} 实船报道区间
        screening_cap: 30% 筛查上限（%）
    """
    insights_meta = insights_meta or {}
    bench_ranges = bench_ranges or {}

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
        "compatibility_derating": "船型×帆型兼容性因子 ∈ [0,1]，先于一切经济/CII 后处理",
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
        "single_source_kpi": "前端不做任何经济公式复制，全部经 evaluate_cell 单源计算",
    }

    return {
        "model_chain": MODEL_CHAIN,
        "coverage": coverage,
        "guardrails": guardrails,
        "limitations": LIMITATIONS,
        "reproducibility": reproducibility,
    }
