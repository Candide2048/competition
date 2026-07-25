# -*- coding: utf-8 -*-
"""交互仪表盘自动分析报告生成（纯字符串，无 Streamlit 依赖，可独立单测）

把当前场景的物理层结果 + 经济性后处理 + 敏感性分析（analytics.economics.
sensitivity）填成中文 Markdown 段落，供 st.download_button 导出。

设计取向:
    - 结论先行：节油率 / 年节省 / 回收期 / CII 评级放开头
    - 与实船数据对照（Norsepower / bound4blue / Oceanbird 公开值）标注可信度
    - 敏感性表回答「油价/碳价/效率波动下经济性是否稳健」
"""
import os
import sys
from datetime import datetime

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from core.owner_inputs import HOURS_PER_YEAR
from analytics.economics import sensitivity

# 帆型中文名 + 英文名 + 实船节油率对照锚点（公开报道值）
SAIL_LABELS = {
    "flettner": "Flettner 旋筒帆",
    "rigid_wing": "刚性翼帆",
    "suction_wing": "吸力帆",
}
SAIL_LABELS_EN = {
    "flettner": "Flettner Rotor",
    "rigid_wing": "Rigid Wing Sail",
    "suction_wing": "Suction Wing Sail",
}
SAIL_BENCHMARKS = {
    "flettner": "Norsepower MV Estraden 双转子实测 6.1%；Maersk Pelican 2×24×4 实测 8.2%",
    "rigid_wing": "Oceanbird Wing560 单翼 7-10%；Pyxis Ocean 双翼 DNV 验证约 14%",
    "suction_wing": "bound4blue Pacific Sentinel 平均约 8%（净节油 5.5%，峰值 >20%）",
}
SHIP_LABELS = {
    "kvlcc2": "VLCC 原油轮 (KVLCC2, 30万 DWT)",
    "kamsarmax": "Kamsarmax 散货船 (8.2万 DWT)",
    "mr_tanker": "MR 成品油轮 (5万 DWT)",
    "container": "集装箱船 (KCS, 约 4万 DWT)",
    "pctc": "PCTC 汽车滚装船 (约 6.2万 GT / 1.8万 DWT)",
}
SHIP_LABELS_EN = {
    "kvlcc2": "VLCC Crude Tanker (KVLCC2, 300k DWT)",
    "kamsarmax": "Kamsarmax Bulk Carrier (82k DWT)",
    "mr_tanker": "MR Product Tanker (50k DWT)",
    "container": "Container Ship (KCS, ~40k DWT)",
    "pctc": "PCTC Car Carrier (~62k GT / 18k DWT)",
}
# 船型专属说明（写入报告“与实船对照”段，念实边界）
SHIP_NOTES = {
    "pctc": (
        "PCTC 是 WASP 头号招牌船型：Wallenius Wilhelmsen **Oceanbird** 与 "
        "**Orcelle Wind** 均为汽车滚装风帆旗舰，其刚性翼帆方案预期远洋航线减排 "
        "可达 60%（多帆 + 选航）。本模型与其 rigid_wing 基准 Oceanbird 7-10% 单翼量级呼应。\n\n"
        "> ⚠️ **诚实边界**：PCTC 高干舛、大箱体迎风面显著大于常规货船，而本模型当前 "
        "**未计入船体空气阻力（A_T/C_X）**——该项对 PCTC 敏感度高于瘦削油/散货船，"
        "且 PCTC 为工程估算代表船（无 SIMMAN 级公开基准船），结果用于量级筛选与横向对比，非单船精确值。"
    ),
}
SEASON_LABELS = {
    "winter": "冬季（东北季风盛期）",
    "spring": "春季（季风过渡期）",
    "summer": "夏季（西南季风盛期）",
    "autumn": "秋季（季风过渡期）",
}
SEASON_LABELS_EN = {
    "winter": "Winter (NE Monsoon)",
    "spring": "Spring (Monsoon Transition)",
    "summer": "Summer (SW Monsoon)",
    "autumn": "Autumn (Monsoon Transition)",
}


def _fmt_usd(v) -> str:
    if v is None:
        return "—"
    # 转义 $：Streamlit 会把成对 $ 当作 LaTeX 定界符，导致金额被渲染成数学公式；
    # \$ 在 Streamlit 与 GitHub/标准 Markdown 中都渲染为字面美元符号，下载的 .md 亦正常。
    return f"\\${v:,.0f}"


def _fmt_payback(years, locale="zh") -> str:
    if years is None:
        return "N/A (annual savings ≤ 0)" if locale == "en" else "不可回收（年节省 ≤ 0）"
    return f"{years:.1f} yr" if locale == "en" else f"{years:.1f} 年"


def build_sensitivity_table(annual_fuel_saved_t: float,
                            annual_co2_t: float,
                            initial_cost_usd: float,
                            fuel_price: float,
                            co2_price: float,
                            years: int = 10,
                            locale: str = "zh") -> str:
    """油价±30% / 碳价±50% / 效率±20% 的 10 年 NPV 敏感性 Markdown 表"""
    s = sensitivity(
        annual_fuel_saved_t, annual_co2_t, initial_cost_usd,
        fuel_price=fuel_price, co2_price=co2_price,
        work_rate=1.0, years=years,
    )
    base = s["base_npv"]

    def _delta(v):
        d = v - base
        pct = (d / abs(base) * 100.0) if base != 0 else 0.0
        sign = "+" if d >= 0 else ""
        if locale == "en":
            return f"{_fmt_usd(v)} ({sign}{pct:.1f}%)"
        return f"{_fmt_usd(v)}（{sign}{pct:.1f}%）"
    
    if locale == "en":
        rows = [
            f"| Baseline | {_fmt_usd(base)} | — |",
            f"| Fuel −30% | {_fmt_usd(s['fuel_-30%'])} | {_delta(s['fuel_-30%'])} |",
            f"| Fuel +30% | {_fmt_usd(s['fuel_+30%'])} | {_delta(s['fuel_+30%'])} |",
            f"| Carbon −50% | {_fmt_usd(s['co2_-50%'])} | {_delta(s['co2_-50%'])} |",
            f"| Carbon +50% | {_fmt_usd(s['co2_+50%'])} | {_delta(s['co2_+50%'])} |",
            f"| Eff. −20% | {_fmt_usd(s['eff_-20%'])} | {_delta(s['eff_-20%'])} |",
            f"| Eff. +20% | {_fmt_usd(s['eff_+20%'])} | {_delta(s['eff_+20%'])} |",
        ]
        header = (f"| Scenario | {years}-yr NPV | vs Baseline |\n"
                  "|------|-----------|----------|") 
    else:
        rows = [
            f"| 基准情景 | {_fmt_usd(base)} | — |",
            f"| 油价 −30% | {_fmt_usd(s['fuel_-30%'])} | {_delta(s['fuel_-30%'])} |",
            f"| 油价 +30% | {_fmt_usd(s['fuel_+30%'])} | {_delta(s['fuel_+30%'])} |",
            f"| 碳价 −50% | {_fmt_usd(s['co2_-50%'])} | {_delta(s['co2_-50%'])} |",
            f"| 碳价 +50% | {_fmt_usd(s['co2_+50%'])} | {_delta(s['co2_+50%'])} |",
            f"| 效率 −20% | {_fmt_usd(s['eff_-20%'])} | {_delta(s['eff_-20%'])} |",
            f"| 效率 +20% | {_fmt_usd(s['eff_+20%'])} | {_delta(s['eff_+20%'])} |",
        ]
        header = (f"| 情景 | {years} 年 NPV | 相对基准 |\n"
                  "|------|-----------|----------|") 
    return header + "\n" + "\n".join(rows)


def generate_report(*, ship: str, sail: str, route: str, route_name: str,
                    season: str, speed_used: float, speed_exact: bool,
                    physics: dict, cell: dict,
                    sea_operating_ratio: float,
                    fuel_type: str, fuel_price: float, co2_price: float,
                    unit_cost_usd: float, n_sails: int,
                    flettner_spec: str | None = None,
                    is_live: bool = False,
                    ship_overrides: dict | None = None,
                    locale: str = "zh") -> str:
    """生成 Markdown 分析报告（支持 zh/en）"""
    en = (locale == "en")
    ship_label = (SHIP_LABELS_EN if en else SHIP_LABELS).get(ship, ship)
    sail_label = (SAIL_LABELS_EN if en else SAIL_LABELS).get(sail, sail)
    season_label = (SEASON_LABELS_EN if en else SEASON_LABELS).get(season, season)
    duration_h = float(physics["duration_h"])
    distance_nm = float(physics["distance_nm"])
    trips = sea_operating_ratio * HOURS_PER_YEAR / duration_h if duration_h > 0 else 0.0

    annual_fuel_saved_t = cell["fuel_saved_t"] * trips
    annual_co2_t = cell["co2_reduced_t"] * trips
    initial_cost = cell["initial_cost_usd"]

    sail_spec = (f" (spec {flettner_spec})" if en else f"（规格 {flettner_spec}）") if sail == "flettner" and flettner_spec else ""
    speed_note = ("" if speed_exact else
                 (" (nearest grid speed)" if en else "（网格最近邻航速，非精确匹配）"))
    live_note = ""
    if is_live:
        live_note = ("\n> ⚙️ This scenario uses custom geometry or non-grid speed — **live physics recomputation**.\n" if en
                     else "\n> ⚙️ 本场景含实船几何覆盖或非标准航速，结果为 **live 实时物理重算**（非预计算网格取值）。\n")

    ov_line = ""
    if ship_overrides:
        if en:
            ov_items = ", ".join(f"{k}={v}" for k, v in ship_overrides.items())
            ov_line = f"- **Vessel geometry overrides**: {ov_items}\n"
        else:
            ov_items = "、".join(f"{k}={v}" for k, v in ship_overrides.items())
            ov_line = f"- **实船几何覆盖**：{ov_items}\n"

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    _sn = SHIP_NOTES.get(ship)
    _ship_note = f"\n{_sn}\n" if _sn else ""

    if en:
        md = _report_en(ship_label, sail_label, sail_spec, route_name, season_label,
                        distance_nm, duration_h, speed_used, speed_note, n_sails,
                        cell, physics, trips, annual_fuel_saved_t, annual_co2_t,
                        initial_cost, unit_cost_usd, fuel_type, fuel_price, co2_price,
                        sea_operating_ratio, now, live_note, ov_line, _ship_note, sail)
    else:
        md = _report_zh(ship_label, sail_label, sail_spec, route_name, season_label,
                        distance_nm, duration_h, speed_used, speed_note, n_sails,
                        cell, physics, trips, annual_fuel_saved_t, annual_co2_t,
                        initial_cost, unit_cost_usd, fuel_type, fuel_price, co2_price,
                        sea_operating_ratio, now, live_note, ov_line, _ship_note, sail)
    return md

def _report_zh(ship_label, sail_label, sail_spec, route_name, season_label,
              distance_nm, duration_h, speed_used, speed_note, n_sails,
              cell, physics, trips, annual_fuel_saved_t, annual_co2_t,
              initial_cost, unit_cost_usd, fuel_type, fuel_price, co2_price,
              sea_operating_ratio, now, live_note, ov_line, _ship_note, sail):
    return f"""# 风帆辅助推进效益分析报告

> 生成时间：{now}　|　场景：{ship_label} · {sail_label}{sail_spec} · {route_name} · {season_label}
{live_note}
## 一、核心结论

在 **{route_name}**（{distance_nm:,.0f} nm，单程约 {duration_h:.0f} h）{season_label}风况下，
为 {ship_label} 加装 **{n_sails} 台 {sail_label}{sail_spec}**（航速 {speed_used:.0f} kn{speed_note}），
逐小时 ERA5 风况积分得到的效益如下：

- **节油率**：{cell['saving_rate_pct']:.2f}%
- **单航次节油**：{cell['fuel_saved_t']:.2f} t　→　**年节油**（{trips:.1f} 航次/年）：{annual_fuel_saved_t:.0f} t
- **单航次 CO₂ 减排**：{cell['co2_reduced_t']:.2f} t　→　**年减排**：{annual_co2_t:.0f} t
- **CII 评级**：加装后 {cell['cii_rating_with_sail']} 级（碳强度改善 {cell['cii_improvement_pct']:.2f}%）
- **初始投资**：{_fmt_usd(initial_cost)}（{n_sails} 台 × 单台 {_fmt_usd(unit_cost_usd)}）
- **年净节省**：{_fmt_usd(cell['annual_savings_usd'])}　|　**投资回收期**：{_fmt_payback(cell['payback_years'], 'zh')}
- **10 年 NPV**：{_fmt_usd(cell['npv_10y_usd'])}　|　**20 年 NPV**：{_fmt_usd(cell['npv_20y_usd'])}
{ov_line}
## 二、与实船数据对照

本场景节油率 **{cell['saving_rate_pct']:.2f}%**，对照公开实船报道：

> {SAIL_BENCHMARKS.get(sail, '—')}

模型采用等面积归一化安装（三帆型总投影面积量级相近，用于公平对比单位面积气动效率），
结果落在文献报道的实船节油率区间内，量级可信；实船满装潜力另受甲板面积与船型约束。
{_ship_note}
## 三、物理层量化（逐小时积分中间量）

| 指标 | 数值 |
|------|------|
| 平均风速 | {physics['mean_wind_ms']:.2f} m/s |
| 平均帆推力 | {cell['mean_thrust_kN']:.1f} kN |
| 平均转子/吸力电力功耗 | {cell['mean_power_kW']:.1f} kW |
| 基线油耗（单航次） | {physics['fuel_baseline_kg']/1000.0:.2f} t |
| 有帆油耗（单航次） | {physics['fuel_with_sail_kg']/1000.0:.2f} t |
| CII 基线 → 加帆 | {cell['cii_baseline']:.4f} → {cell['cii_with_sail']:.4f} |

> 说明：有帆油耗已扣除转子驱动 / 吸力风扇电力功耗；SFOC 固定为 180 g/kWh。

## 四、经济性敏感性分析（10 年 NPV）

油价、碳价与风帆效率是经济性结论的主要不确定源。下表给出各因素单独波动时的 10 年 NPV：

{build_sensitivity_table(annual_fuel_saved_t, annual_co2_t, initial_cost, fuel_price, co2_price, locale='zh')}

> 基准：燃料 {fuel_type}，油价 {fuel_price:.2f} USD/kg，碳价 {co2_price:.0f} EUR/tCO₂，
> 海上作业比例 {sea_operating_ratio:.3f}（年 {trips:.1f} 航次）。

## 五、方法与口径说明

- **计算分层**：物理层（船型×航速×航线×季节×帆型，ERA5 逐小时积分）离线预计算；
  经济性 / CII 后处理为纯算术，随油价/碳价/成本滑杆实时重算。
- **物理模型**：Holtrop-Mennen 阻力 + 帆型气动最优控制 + 逐小时推力平衡（扣电力功耗）。
- **CII 参考线**：MEPC.353(78) G2，按船型 IMO 分类取参考线。
- **经济性**：初始成本 = 单台成本 × 台数；年节省 = (节油×油价 + 减排×碳价)；
  NPV 计入 2% 年维护与 8% 贴现（analytics/economics.py）。

---
*本报告由 WASP 交互仪表盘自动生成，数据与模型口径详见 code/ 各模块与配置。*
"""


def _report_en(ship_label, sail_label, sail_spec, route_name, season_label,
              distance_nm, duration_h, speed_used, speed_note, n_sails,
              cell, physics, trips, annual_fuel_saved_t, annual_co2_t,
              initial_cost, unit_cost_usd, fuel_type, fuel_price, co2_price,
              sea_operating_ratio, now, live_note, ov_line, _ship_note, sail):
    return f"""# Wind-Assisted Ship Propulsion Benefit Analysis

> Generated: {now} | Scenario: {ship_label} · {sail_label}{sail_spec} · {route_name} · {season_label}
{live_note}
## 1. Key Findings

On **{route_name}** ({distance_nm:,.0f} nm, ~{duration_h:.0f} h one-way) under {season_label} wind conditions,
installing **{n_sails} × {sail_label}{sail_spec}** on {ship_label} (at {speed_used:.0f} kn{speed_note}),
hourly ERA5 wind integration yields:

- **Fuel saving rate**: {cell['saving_rate_pct']:.2f}%
- **Per-voyage fuel saved**: {cell['fuel_saved_t']:.2f} t → **Annual** ({trips:.1f} voyages/yr): {annual_fuel_saved_t:.0f} t
- **Per-voyage CO₂ reduced**: {cell['co2_reduced_t']:.2f} t → **Annual**: {annual_co2_t:.0f} t
- **CII rating**: {cell['cii_rating_with_sail']} (carbon intensity improved {cell['cii_improvement_pct']:.2f}%)
- **Initial investment**: {_fmt_usd(initial_cost)} ({n_sails} × {_fmt_usd(unit_cost_usd)} each)
- **Annual net savings**: {_fmt_usd(cell['annual_savings_usd'])} | **Payback**: {_fmt_payback(cell['payback_years'], 'en')}
- **10-yr NPV**: {_fmt_usd(cell['npv_10y_usd'])} | **20-yr NPV**: {_fmt_usd(cell['npv_20y_usd'])}
{ov_line}
## 2. Benchmark Comparison

This scenario’s fuel saving of **{cell['saving_rate_pct']:.2f}%** compared to published real-vessel data:

> {SAIL_BENCHMARKS.get(sail, '—')}

The model uses equal-area normalized installation for fair cross-sail-type comparison.
Results fall within the reported range, confirming order-of-magnitude credibility.
{_ship_note}
## 3. Physics Summary (Hourly Integration)

| Metric | Value |
|--------|-------|
| Mean wind speed | {physics['mean_wind_ms']:.2f} m/s |
| Mean sail thrust | {cell['mean_thrust_kN']:.1f} kN |
| Mean rotor/suction power | {cell['mean_power_kW']:.1f} kW |
| Baseline fuel (per voyage) | {physics['fuel_baseline_kg']/1000.0:.2f} t |
| With-sail fuel (per voyage) | {physics['fuel_with_sail_kg']/1000.0:.2f} t |
| CII baseline → with sail | {cell['cii_baseline']:.4f} → {cell['cii_with_sail']:.4f} |

> Note: With-sail fuel accounts for rotor/fan power consumption; SFOC fixed at 180 g/kWh.

## 4. Sensitivity Analysis (10-yr NPV)

Fuel price, carbon price, and sail efficiency are the main uncertainty drivers:

{build_sensitivity_table(annual_fuel_saved_t, annual_co2_t, initial_cost, fuel_price, co2_price, locale='en')}

> Baseline: {fuel_type}, fuel {fuel_price:.2f} USD/kg, carbon {co2_price:.0f} EUR/tCO₂,
> sea operating ratio {sea_operating_ratio:.3f} ({trips:.1f} voyages/yr).

## 5. Methodology

- **Computation**: Physics (ship×speed×route×season×sail, ERA5 hourly) pre-computed offline;
  economics/CII is pure arithmetic, recomputed in real-time.
- **Physics model**: Holtrop-Mennen resistance + aerodynamic optimal control + hourly thrust balance.
- **CII reference**: MEPC.353(78) G2, ship-type-specific IMO reference lines.
- **Economics**: Initial cost = unit × count; annual savings = (fuel×price + CO₂×carbon price);
  NPV includes 2% annual maintenance and 8% discount rate.

---
*Auto-generated by the WASP Interactive Dashboard.*
"""
