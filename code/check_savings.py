# -*- coding: utf-8 -*-
"""验证修复后各帆型经济性对比 — 含船型兼容性因子"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml

with open("results/precomputed/physics_grid.json", "r") as f:
    d = json.load(f)

with open("config/sail_types.yaml", "r", encoding="utf-8") as f:
    sail_cfg = yaml.safe_load(f)

compat_matrix = sail_cfg.get("ship_sail_compatibility", {})

recs = d["records"]
ships = d["metadata"]["ships"]
sails = d["metadata"]["sail_types"]
install = d["metadata"]["sail_install"]

# 成本配置 (来自 sail_types.yaml 更新后)
UNIT_COST = {"flettner": 1_500_000, "rigid_wing": 4_000_000, "suction_wing": 800_000}
N_SAILS = install  # {"flettner": 4, "rigid_wing": 1, "suction_wing": 6}
TOTAL_COST = {s: UNIT_COST[s] * N_SAILS[s] for s in sails}

# 经济性参数
FUEL_PRICE = 0.6  # USD/kg
CO2_FACTOR = 3.114  # tCO2/tFuel (VLSFO)
CO2_PRICE = 74.0  # EUR/tCO2
SEA_RATIO = 0.742
HOURS_PER_YEAR = 8765

print("=" * 90)
print("成本对比")
print("=" * 90)
for s in sails:
    print(f"  {s:15s}: {N_SAILS[s]}台 × ${UNIT_COST[s]/1e6:.1f}M = ${TOTAL_COST[s]/1e6:.1f}M 总投资")

print("\n" + "=" * 90)
print("船型帆型兼容性矩阵")
print("=" * 90)
print(f"{'Ship':<12} {'flettner':>12} {'rigid_wing':>12} {'suction_wing':>12}")
for ship in ships:
    row = []
    for sail in sails:
        c = compat_matrix.get(ship, {}).get(sail, 1.0)
        if c == 0.0:
            row.append("N/A")
        elif c < 1.0:
            row.append(f"{c:.0%}↓")
        else:
            row.append("✓")
    print(f"{ship:<12} {row[0]:>12} {row[1]:>12} {row[2]:>12}")

print("\n" + "=" * 90)
print("经济性对比: 回收期 (年) | 14kn, middle_east_china, 各季节平均")
print("=" * 90)
print(f"{'Ship':<12} {'flettner':>15} {'rigid_wing':>15} {'suction_wing':>15}  | 最优帆型")
print("-" * 90)

win_count = {s: 0 for s in sails}

for ship in ships:
    paybacks = {}
    for sail in sails:
        # 兼容性检查
        compat = compat_matrix.get(ship, {}).get(sail, 1.0)
        if compat == 0.0:
            paybacks[sail] = float('inf')
            continue
        # 取所有航线、季节的平均
        matching = [r for r in recs
                    if r["ship"] == ship and r["sail"] == sail
                    and r["speed_kn"] == 14.0]
        if not matching:
            paybacks[sail] = float('inf')
            continue
        # 平均每航次节油 (kg) × 兼容性因子
        avg_saved_kg = sum(r["fuel_saved_kg"] for r in matching) / len(matching) * compat
        avg_duration_h = sum(r["duration_h"] for r in matching) / len(matching)
        # 年航次数
        annual_hours = SEA_RATIO * HOURS_PER_YEAR
        trips_per_year = annual_hours / avg_duration_h if avg_duration_h > 0 else 0
        # 年节油 (t)
        annual_fuel_saved_t = avg_saved_kg * trips_per_year / 1000
        # 年节省 (USD)
        fuel_savings = annual_fuel_saved_t * 1000 * FUEL_PRICE
        co2_savings = annual_fuel_saved_t * CO2_FACTOR * CO2_PRICE * 1.08  # EUR→USD
        total_annual_savings = fuel_savings + co2_savings
        # 回收期
        if total_annual_savings > 0:
            paybacks[sail] = TOTAL_COST[sail] / total_annual_savings
        else:
            paybacks[sail] = float('inf')
    
    best = min(paybacks, key=paybacks.get)
    win_count[best] += 1
    row = []
    for sail in sails:
        pb = paybacks[sail]
        marker = " *" if sail == best else ""
        row.append(f"{pb:.1f}y{marker}")
    print(f"{ship:<12} {row[0]:>15} {row[1]:>15} {row[2]:>15}  | {best}")

print("\n" + "=" * 90)
print("按帆型获胜次数 (14kn):")
for s in sails:
    print(f"  {s:15s}: {win_count[s]} / {len(ships)} 船型")

# 全航速全条件扫描
print("\n" + "=" * 90)
print("全条件扫描: 帆型获胜统计 (所有航速×船型, 含兼容性约束)")
print("=" * 90)

full_wins = {s: 0 for s in sails}
total_combos = 0

for ship in ships:
    for speed in d["metadata"]["speeds_kn"]:
        paybacks = {}
        for sail in sails:
            compat = compat_matrix.get(ship, {}).get(sail, 1.0)
            if compat == 0.0:
                paybacks[sail] = float('inf')
                continue
            matching = [r for r in recs
                        if r["ship"] == ship and r["sail"] == sail
                        and r["speed_kn"] == speed]
            if not matching:
                paybacks[sail] = float('inf')
                continue
            avg_saved_kg = sum(r["fuel_saved_kg"] for r in matching) / len(matching) * compat
            avg_duration_h = sum(r["duration_h"] for r in matching) / len(matching)
            annual_hours = SEA_RATIO * HOURS_PER_YEAR
            trips_per_year = annual_hours / avg_duration_h if avg_duration_h > 0 else 0
            annual_fuel_saved_t = avg_saved_kg * trips_per_year / 1000
            fuel_savings = annual_fuel_saved_t * 1000 * FUEL_PRICE
            co2_savings = annual_fuel_saved_t * CO2_FACTOR * CO2_PRICE * 1.08
            total_annual_savings = fuel_savings + co2_savings
            if total_annual_savings > 0:
                paybacks[sail] = TOTAL_COST[sail] / total_annual_savings
            else:
                paybacks[sail] = float('inf')
        best = min(paybacks, key=paybacks.get)
        full_wins[best] += 1
        total_combos += 1

print(f"总组合数: {total_combos}")
for s in sails:
    pct = full_wins[s] / total_combos * 100
    print(f"  {s:15s}: {full_wins[s]:>3}/{total_combos} ({pct:.0f}%)")

print("\n" + "=" * 90)
print("节油率对比 (全航速平均)")
print("=" * 90)
print(f"{'Ship':<12} {'flettner':>12} {'rigid_wing':>12} {'suction_wing':>12}")
for ship in ships:
    row = []
    for sail in sails:
        matching = [r for r in recs if r["ship"] == ship and r["sail"] == sail]
        avg = sum(r["saving_rate_pct"] for r in matching) / len(matching) if matching else 0
        row.append(f"{avg:.2f}%")
    print(f"{ship:<12} {row[0]:>12} {row[1]:>12} {row[2]:>12}")
