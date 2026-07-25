# -*- coding: utf-8 -*-
"""经济性分析模块

实现 ⑤ Guzelbulut 2024 §4 的经济性评估方法:
- 初始投资成本 (Eq.11)
- 年度节省 (燃油 + 碳价)
- NPV (5/10/15/20 年投资期)
- 回收期
- 敏感性分析（油价/碳价/风帆效率）

公式:
    c_initial = a·(A_top + A_lateral) + b·V_rotor   (⑤ Eq.11)

    annual_savings = (fuel_saved_t × fuel_price + co2_reduced_t × co2_price) × work_rate

    NPV(n) = Σ_{t=1}^{n} (annual_savings × (1-maintenance)^t) / (1+r)^t - c_initial

    payback = c_initial / annual_savings  (简化，不考虑贴现)

参考:
    ⑤ Guzelbulut 2024 §4 Table 5
    config/economics.yaml
"""
import os
from dataclasses import dataclass, field

import numpy as np
import yaml


# 默认经济参数（⑤ Guzelbulut 2024 + 船舶风帆技术数据搜集表.xlsx 2025 市场数据）
DEFAULT_FUEL_PRICE = 0.6      # USD/kg (VLSFO 2025: 485-650 $/t, 取上沿偏保守)
DEFAULT_CO2_PRICE = 74.0      # EUR/tCO2 (EU ETS 2025 年均; 年末 87.37, 2026Q2 64-68)
DEFAULT_WORK_RATE = 1.0           # 风帆工作率（与 economics.yaml 一致；逐小时物理仿真已隐含折减）
DEFAULT_MAINTENANCE_RATE = 0.02  # 年维护成本 = 2% 初始成本 (PH-04)
DEFAULT_DISCOUNT_RATE = 0.08  # 贴现率 (PH-05)
DEFAULT_INVESTMENT_YEARS = [5, 10, 15, 20]

# ⑤ Guzelbulut 2024 Eq.11 初始成本系数
DEFAULT_A_COST = 2500.0       # USD/m² (面积系数)
DEFAULT_B_COST = 800.0        # USD/(m³/s) (体积流速系数)


# 默认经济配置文件路径
DEFAULT_ECON_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "economics.yaml"
)


def initial_cost(A_top: float, A_lateral: float, V_rotor: float,
                 a: float = DEFAULT_A_COST, b: float = DEFAULT_B_COST) -> float:
    """初始投资成本 (⑤ Eq.11)

    c_initial = a·(A_top + A_lateral) + b·V_rotor

    Args:
        A_top:      转子横截面积 π(D/2)² (m²)
        A_lateral:  侧投影面积 H×D (m²)
        V_rotor:    转子几何体积 π(D/2)²·H (m³)
        a:          面积成本系数 (USD/m²)
        b:          体积成本系数 (USD/m³)

    Returns:
        c_initial_usd: 初始投资 (USD)
    """
    return a * (A_top + A_lateral) + b * V_rotor


def annual_savings(fuel_saved_t_per_year: float,
                   co2_reduced_t_per_year: float,
                   fuel_price: float = DEFAULT_FUEL_PRICE,
                   co2_price: float = DEFAULT_CO2_PRICE,
                   work_rate: float = DEFAULT_WORK_RATE) -> dict:
    """年度节省金额

    savings = (fuel_saved × fuel_price + co2_reduced × co2_price) × work_rate

    Args:
        fuel_saved_t_per_year:   年节油量 (t)
        co2_reduced_t_per_year:  年 CO2 减排 (t)
        fuel_price:              油价 (USD/kg) → 注意 t→kg 转换
        co2_price:               碳价 (EUR/tCO2)
        work_rate:               风帆工作率

    Returns:
        dict: fuel_savings_usd, co2_savings_eur, total_savings_usd (近似)
              work_rate, fuel_saved_t, co2_reduced_t
    """
    fuel_savings_usd = fuel_saved_t_per_year * 1000.0 * fuel_price  # t→kg
    co2_savings_eur = co2_reduced_t_per_year * co2_price
    # 近似 1 EUR ≈ 1.08 USD（占位，实际应动态汇率）
    co2_savings_usd_approx = co2_savings_eur * 1.08
    total_usd = (fuel_savings_usd + co2_savings_usd_approx) * work_rate
    return {
        "fuel_savings_usd": fuel_savings_usd * work_rate,
        "co2_savings_eur": co2_savings_eur * work_rate,
        "co2_savings_usd_approx": co2_savings_usd_approx * work_rate,
        "total_savings_usd": total_usd,
        "work_rate": work_rate,
        "fuel_saved_t": fuel_saved_t_per_year,
        "co2_reduced_t": co2_reduced_t_per_year,
    }


def npv(annual_savings_usd: float, initial_cost_usd: float,
        years: list[int] = DEFAULT_INVESTMENT_YEARS,
        discount_rate: float = DEFAULT_DISCOUNT_RATE,
        maintenance_rate: float = DEFAULT_MAINTENANCE_RATE) -> dict:
    """计算多个投资期的 NPV

    NPV(n) = Σ_{t=1}^{n} (annual_savings × (1-maintenance)^t) / (1+r)^t - initial_cost

    Args:
        annual_savings_usd: 年度节省 (USD)
        initial_cost_usd:   初始投资 (USD)
        years:              投资期列表
        discount_rate:      贴现率
        maintenance_rate:   年维护成本率

    Returns:
        dict: {5: npv_5y, 10: npv_10y, 15: npv_15y, 20: npv_20y}
    """
    result = {}
    for n in years:
        npv_value = 0.0
        for t in range(1, n + 1):
            net_cash = annual_savings_usd * (1.0 - maintenance_rate) ** t
            npv_value += net_cash / (1.0 + discount_rate) ** t
        npv_value -= initial_cost_usd
        result[n] = float(npv_value)
    return result


def payback_period(initial_cost_usd: float, annual_savings_usd: float) -> float:
    """回收期（简化，不考虑贴现）

    payback = initial_cost / annual_savings

    Args:
        initial_cost_usd:    初始投资 (USD)
        annual_savings_usd:  年度节省 (USD)

    Returns:
        payback_years: 回收期 (年)
    """
    if annual_savings_usd <= 0:
        return float("inf")
    return initial_cost_usd / annual_savings_usd


def sensitivity(fuel_saved_t_per_year: float,
                co2_reduced_t_per_year: float,
                initial_cost_usd: float,
                fuel_price: float = DEFAULT_FUEL_PRICE,
                co2_price: float = DEFAULT_CO2_PRICE,
                work_rate: float = DEFAULT_WORK_RATE,
                discount_rate: float = DEFAULT_DISCOUNT_RATE,
                maintenance_rate: float = DEFAULT_MAINTENANCE_RATE,
                years: int = 10) -> dict:
    """敏感性分析

    变动维度:
    - 油价 ±30%
    - 碳价 ±50%
    - 风帆效率（即节油率）±20%

    Args:
        同 annual_savings + npv

    Returns:
        dict: 每个变动维度的 NPV 变化
    """
    base_savings = annual_savings(
        fuel_saved_t_per_year, co2_reduced_t_per_year,
        fuel_price, co2_price, work_rate
    )["total_savings_usd"]
    base_npv = npv(base_savings, initial_cost_usd, [years],
                   discount_rate, maintenance_rate)[years]

    result = {"base_npv": base_npv, "base_savings_usd": base_savings}

    # 油价 ±30%
    for delta, label in [(-0.3, "fuel_-30%"), (0.3, "fuel_+30%")]:
        s = annual_savings(
            fuel_saved_t_per_year, co2_reduced_t_per_year,
            fuel_price * (1 + delta), co2_price, work_rate
        )["total_savings_usd"]
        result[label] = npv(s, initial_cost_usd, [years],
                            discount_rate, maintenance_rate)[years]

    # 碳价 ±50%
    for delta, label in [(-0.5, "co2_-50%"), (0.5, "co2_+50%")]:
        s = annual_savings(
            fuel_saved_t_per_year, co2_reduced_t_per_year,
            fuel_price, co2_price * (1 + delta), work_rate
        )["total_savings_usd"]
        result[label] = npv(s, initial_cost_usd, [years],
                            discount_rate, maintenance_rate)[years]

    # 风帆效率 ±20%（即节油量与碳减排量等比例变动）
    for delta, label in [(-0.2, "eff_-20%"), (0.2, "eff_+20%")]:
        s = annual_savings(
            fuel_saved_t_per_year * (1 + delta),
            co2_reduced_t_per_year * (1 + delta),
            fuel_price, co2_price, work_rate
        )["total_savings_usd"]
        result[label] = npv(s, initial_cost_usd, [years],
                            discount_rate, maintenance_rate)[years]

    return result


def scenario_analysis(annual_fuel_saved_t: float,
                      annual_co2_reduced_t: float,
                      unit_cost_usd: float,
                      n_sails: int,
                      fuel_price: float = DEFAULT_FUEL_PRICE,
                      co2_price: float = DEFAULT_CO2_PRICE,
                      work_rate: float = 1.0,
                      discount_rate: float = DEFAULT_DISCOUNT_RATE,
                      maintenance_rate: float = DEFAULT_MAINTENANCE_RATE,
                      years: int = 20) -> dict:
    """船东输入参数情景分析

    与 sensitivity() 互补：sensitivity 只动油价/碳价/效率；本函数额外把
    **单台成本**（船东最不确定、且直接翻转经济性结论的量）纳入情景扫描，
    并同时返回回收期与 NPV，用于「把不确定因素作为船东输入做整体评估」。

    扫描维度（各自 one-at-a-time，其余取基准）:
        - 单台成本 ±30%（成本区间不确定性）
        - 油价 ±30%
        - 碳价 ±50%
        - 风帆效率（节油量）±20%

    Args:
        annual_fuel_saved_t:  年节油量 (t)
        annual_co2_reduced_t: 年 CO2 减排 (t)
        unit_cost_usd:        单台成本 (USD)
        n_sails:              安装台数
        其余同 annual_savings / npv

    Returns:
        dict: {"base": {...}, "scenarios": {label: {payback_years, npv_usd, ...}}}
    """
    base_cost = unit_cost_usd * n_sails

    def _eval(fuel_t, co2_t, fprice, cprice, cost):
        sav = annual_savings(fuel_t, co2_t, fprice, cprice, work_rate)["total_savings_usd"]
        pb = payback_period(cost, sav)
        nv = npv(sav, cost, [years], discount_rate, maintenance_rate)[years]
        return {
            "annual_savings_usd": round(sav, 0),
            "initial_cost_usd": round(cost, 0),
            "payback_years": round(pb, 1) if np.isfinite(pb) else None,
            f"npv_{years}y_usd": round(nv, 0),
        }

    base = _eval(annual_fuel_saved_t, annual_co2_reduced_t,
                 fuel_price, co2_price, base_cost)

    scenarios = {}
    # 单台成本 ±30%
    for delta, label in [(-0.3, "cost_-30%"), (0.3, "cost_+30%")]:
        scenarios[label] = _eval(
            annual_fuel_saved_t, annual_co2_reduced_t,
            fuel_price, co2_price, base_cost * (1 + delta))
    # 油价 ±30%
    for delta, label in [(-0.3, "fuel_-30%"), (0.3, "fuel_+30%")]:
        scenarios[label] = _eval(
            annual_fuel_saved_t, annual_co2_reduced_t,
            fuel_price * (1 + delta), co2_price, base_cost)
    # 碳价 ±50%
    for delta, label in [(-0.5, "co2_-50%"), (0.5, "co2_+50%")]:
        scenarios[label] = _eval(
            annual_fuel_saved_t, annual_co2_reduced_t,
            fuel_price, co2_price * (1 + delta), base_cost)
    # 风帆效率 ±20%
    for delta, label in [(-0.2, "eff_-20%"), (0.2, "eff_+20%")]:
        scenarios[label] = _eval(
            annual_fuel_saved_t * (1 + delta), annual_co2_reduced_t * (1 + delta),
            fuel_price, co2_price, base_cost)

    return {"base": base, "scenarios": scenarios, "years": years,
            "n_sails": n_sails, "unit_cost_usd": unit_cost_usd}


def load_economics_from_config(config_path: str | None = None) -> dict:
    """从 economics.yaml 加载经济参数

    Returns:
        dict: 含 fuel_price, co2_price, work_rate, discount_rate,
              maintenance_rate, a_cost, b_cost, investment_years
    """
    if config_path is None:
        config_path = DEFAULT_ECON_CONFIG
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
