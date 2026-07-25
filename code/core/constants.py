"""共享物理常量 — 所有模块的 single source of truth

避免 models ↔ analytics 之间循环导入。
"""

# ═══════════════════════════════════════════════════════════
# 排放因子 (tCO2/tFuel)
# IMO MEPC.245(66) / MEPC.364(79) C_F 碳转换系数
# ═══════════════════════════════════════════════════════════

EMISSION_FACTORS: dict[str, float] = {
    "HFO":      3.114,   # Heavy Fuel Oil
    "VLSFO":    3.114,   # Very-Low Sulphur Fuel Oil (近似 HFO)
    "LNG":      2.750,   # Liquefied Natural Gas
    "MDO":      3.206,   # Marine Diesel Oil
    "MGO":      3.206,   # Marine Gas Oil
    "METHANOL": 1.375,   # 甲醇
}

DEFAULT_EMISSION_FACTOR: float = EMISSION_FACTORS["HFO"]
