# -*- coding: utf-8 -*-
"""闸门3: Holtrop-Mennen 阻力模型单元测试

验证目标:
    - KVLCC2 在 14 kn (V=7.2 m/s) 反算 P_E 数量级合理
    - 反推 70 小时总油耗与 ④ 计明军场景2 实船油耗 89.2 t 误差 < 30%
    - 各阻力分量符号正确（R_F>0, R_R>0, R_APP>0）
    - R_total 随船速 V 单调递增
    - 形状因子 (1+k1) 落在 VLCC 典型区间 [1.05, 1.30]
    - ITTC 1957 摩擦系数 C_F 落在 [1.0e-3, 2.5e-3]

运行方式:
    cd shipping_wasp/code
    python -m pytest tests/test_holtrop_mennen.py -v
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.resistance import (
    HoltropMennenInput,
    compute_resistance,
    compute_wet_surface,
    load_kvlcc2_from_config,
)
from models.resistance.ittc1957 import friction_coefficient, reynolds_number
from models.resistance.holtrop_mennen import compute_form_factor, compute_length_of_run


# ---------- 测试夹具 ----------

@pytest.fixture
def kvlcc2():
    """从 YAML 配置加载 KVLCC2 船型"""
    return load_kvlcc2_from_config()


@pytest.fixture
def kvlcc2_at_14kn(kvlcc2):
    """KVLCC2 在 14 kn (V=7.2 m/s) 下的阻力计算结果"""
    return compute_resistance(kvlcc2, V=7.2)


# ---------- ITTC 1957 摩擦阻力 ----------

class TestITTC1957:
    """ITTC 1957 摩擦阻力系数验证"""

    def test_reynolds_number(self, kvlcc2):
        """Re = V·L/ν，VLCC 14kn 应在 1e9 量级"""
        Re = reynolds_number(V=7.2, L=kvlcc2.L, nu=kvlcc2.nu_sw)
        assert 1e8 < Re < 1e10, f"Re={Re:.3e} 应在 1e8-1e10 范围"
        # KVLCC2 @ 14 kn: Re ≈ 1.94e9
        assert 1.5e9 < Re < 2.5e9, f"Re={Re:.3e} 应接近 1.94e9"

    def test_friction_coefficient_magnitude(self):
        """C_F 应在 [1.0e-3, 2.5e-3] 典型范围"""
        for Re in [1e8, 1e9, 1e10]:
            C_F = friction_coefficient(Re)
            assert 1.0e-3 <= C_F <= 2.5e-3, f"Re={Re}: C_F={C_F:.3e} 超出 [1e-3, 2.5e-3]"

    def test_friction_decreases_with_Re(self):
        """C_F 应随 Re 增大而减小（层流→湍流过渡）"""
        cf_low = friction_coefficient(1e8)
        cf_high = friction_coefficient(1e10)
        assert cf_low > cf_high, "C_F 应随 Re 增大而减小"

    def test_invalid_Re_raises(self):
        """Re <= 0 应抛出异常"""
        with pytest.raises(ValueError):
            friction_coefficient(0.0)
        with pytest.raises(ValueError):
            friction_coefficient(-1.0)


# ---------- 几何派生量 ----------

class TestGeometry:
    """湿表面积、后体长度、形状因子验证"""

    def test_wet_surface_magnitude(self, kvlcc2):
        """湿表面积 S 应在 20000-30000 m² 范围（VLCC 典型）"""
        S = compute_wet_surface(kvlcc2)
        assert 20000 < S < 30000, f"S={S:.1f} 超出 VLCC 典型范围"

    def test_length_of_run_positive(self, kvlcc2):
        """后体长度 L_R 应为正值"""
        L_R = compute_length_of_run(kvlcc2)
        assert L_R > 0, f"L_R={L_R} 应为正"
        # KVLCC2 (lcb=+3.48% Lpp): L_R ≈ 84.5 m (≈0.26·L, VLCC 典型)
        assert 70 < L_R < 100, f"L_R={L_R:.2f} 应在 70-100 m 范围"

    def test_form_factor_range(self, kvlcc2):
        """形状因子 (1+k1) 应在 VLCC 典型范围 [1.05, 1.30]"""
        one_plus_k1 = compute_form_factor(kvlcc2)
        assert 1.05 <= one_plus_k1 <= 1.30, \
            f"(1+k1)={one_plus_k1:.4f} 超出 [1.05, 1.30]"


# ---------- 阻力分量符号 ----------

class TestResistanceComponents:
    """各阻力分量符号与量级验证"""

    def test_R_F_positive(self, kvlcc2_at_14kn):
        """摩擦阻力 R_F 应为正"""
        assert kvlcc2_at_14kn["R_F"] > 0, "R_F 必须为正"

    def test_R_R_positive(self, kvlcc2_at_14kn):
        """剩余阻力 R_R 应为正（兴波阻力恒正）"""
        assert kvlcc2_at_14kn["R_R"] > 0, "R_R 必须为正"

    def test_R_APP_positive(self, kvlcc2_at_14kn):
        """附体阻力 R_APP 应为正"""
        assert kvlcc2_at_14kn["R_APP"] > 0, "R_APP 必须为正"

    def test_R_total_positive(self, kvlcc2_at_14kn):
        """总阻力 R_total 必须为正"""
        assert kvlcc2_at_14kn["R_total"] > 0, "R_total 必须为正"

    def test_R_viscous_dominant(self, kvlcc2_at_14kn):
        """粘性阻力（R_F·(1+k1)）应为总阻力主要分量（>50%）"""
        ratio = kvlcc2_at_14kn["R_viscous"] / kvlcc2_at_14kn["R_total"]
        assert ratio > 0.5, \
            f"粘性阻力占比 {ratio*100:.1f}% 应 > 50%（VLCC 低速段特征）"

    def test_R_total_in_vlcc_range(self, kvlcc2_at_14kn):
        """VLCC 14 kn 总阻力应在 800-1500 kN 范围"""
        R_total_kN = kvlcc2_at_14kn["R_total"] / 1000
        assert 800 < R_total_kN < 1500, \
            f"R_total={R_total_kN:.1f} kN 超出 VLCC 14kn 典型范围 [800, 1500] kN"


# ---------- 阻力随船速变化 ----------

class TestResistanceScaling:
    """阻力随船速的变化规律"""

    def test_R_total_increases_with_V(self, kvlcc2):
        """R_total 应随船速 V 单调递增"""
        Vs = [4.0, 6.0, 8.0, 10.0, 12.0]
        Rs = [compute_resistance(kvlcc2, V=V)["R_total"] for V in Vs]
        for i in range(len(Rs) - 1):
            assert Rs[i + 1] > Rs[i], \
                f"R_total 应随 V 递增：V={Vs[i]}→{Vs[i+1]}, R={Rs[i]:.0f}→{Rs[i+1]:.0f}"

    def test_R_total_scales_approximately_V2(self, kvlcc2):
        """R_total 应近似按 V² 增长（摩擦阻力主导）"""
        R_6 = compute_resistance(kvlcc2, V=6.0)["R_total"]
        R_12 = compute_resistance(kvlcc2, V=12.0)["R_total"]
        # 速度翻倍，阻力应增加约 3-5 倍（V² × 形状因子修正）
        ratio = R_12 / R_6
        assert 3.0 < ratio < 6.0, \
            f"R(12)/R(6)={ratio:.2f} 应在 [3, 6]（近似 V² 增长）"


# ---------- 闸门3: 反算油耗验证（核心） ----------

class TestGate3FuelConsumption:
    """闸门3: KVLCC2 @ 14 kn 反算油耗与 ④ 计明军场景2 实船 89.2 t 对照

    ④ 计明军 2023 场景2: 波斯湾 (29°N,49°E) → (24°N,60°E)
                        航程 70 h，航速 14 kn，实船油耗 89.2 t

    反算链:
        P_E = R_total × V
        P_MF = P_E / (η_S × η_D)        # η_S=0.98 轴传递, η_D=0.97 推进效率
        油耗率 = P_MF × SFOC / 3600      # SFOC=0.160 kg/kWh (HFO 典型)
        总油耗 = 油耗率 × 70 × 3600 (kg)
    """

    # ④ 计明军场景2 锚点
    TARGET_FUEL_T = 89.2          # 实船总油耗 (t)
    DURATION_H = 70.0             # 航程时长 (h)
    ETA_SHAFT = 0.98              # 轴传递效率
    ETA_PROPULSIVE = 0.97         # 推进效率
    SFOC = 0.160                  # kg/kWh (HFO 典型)
    TOLERANCE_PCT = 30.0          # 容差 ±30%

    def test_P_E_magnitude(self, kvlcc2_at_14kn):
        """P_E 应在 VLCC 14 kn 合理范围 5-15 MW"""
        P_E_MW = kvlcc2_at_14kn["P_E"] / 1e6
        assert 5.0 < P_E_MW < 15.0, \
            f"P_E={P_E_MW:.2f} MW 超出 VLCC 14kn 合理范围 [5, 15] MW"

    def test_gate3_fuel_within_tolerance(self, kvlcc2_at_14kn):
        """闸门3 核心断言: 反算油耗与 89.2 t 误差 < 30%

        反算链:
            P_E (W) → P_MF (W) = P_E / (η_S·η_D)
            油耗率 (kg/s) = P_MF (W) × SFOC (kg/kWh) / 3600 (s/h) / 1000 (W/kW)
            总油耗 (t) = 油耗率 × 70 h × 3600 (s/h) / 1000 (kg/t)
        """
        P_E_W = kvlcc2_at_14kn["P_E"]                    # W
        P_MF_W = P_E_W / (self.ETA_SHAFT * self.ETA_PROPULSIVE)  # W
        # SFOC = 0.160 kg/kWh → P_MF_kW × SFOC = kg/h
        P_MF_kW = P_MF_W / 1000.0
        fuel_kg_per_h = P_MF_kW * self.SFOC              # kg/h
        fuel_kg = fuel_kg_per_h * self.DURATION_H        # kg
        fuel_t = fuel_kg / 1000.0                        # t

        error_pct = abs(fuel_t - self.TARGET_FUEL_T) / self.TARGET_FUEL_T * 100
        assert error_pct < self.TOLERANCE_PCT, (
            f"闸门3 失败: 反算油耗 {fuel_t:.2f} t 与实船 "
            f"{self.TARGET_FUEL_T} t 误差 {error_pct:.1f}% > {self.TOLERANCE_PCT}%"
        )

    def test_P_MF_magnitude(self, kvlcc2_at_14kn):
        """P_MF (主机持续功率) 应在 6-15 MW 范围"""
        P_E = kvlcc2_at_14kn["P_E"]
        P_MF = P_E / (self.ETA_SHAFT * self.ETA_PROPULSIVE)
        P_MF_MW = P_MF / 1e6
        assert 6.0 < P_MF_MW < 15.0, \
            f"P_MF={P_MF_MW:.2f} MW 超出 VLCC 14kn 合理范围 [6, 15] MW"

    def test_efficiency_chain_positive(self, kvlcc2_at_14kn):
        """效率链 η_S × η_D 应在 (0, 1)"""
        eta_total = self.ETA_SHAFT * self.ETA_PROPULSIVE
        assert 0 < eta_total < 1
        # P_MF 必须大于 P_E（功率传递有损耗）
        P_E = kvlcc2_at_14kn["P_E"]
        P_MF = P_E / eta_total
        assert P_MF > P_E, "P_MF 应大于 P_E（功率损耗）"


# ---------- 配置加载 ----------

class TestConfigLoading:
    """KVLCC2 配置加载验证"""

    def test_load_kvlcc2_principal_dimensions(self, kvlcc2):
        """主尺度应为 SIMMAN 2008 官方值"""
        assert kvlcc2.L == 320.0, "L_pp 应为 320 m"
        assert kvlcc2.B == 58.0, "B 应为 58 m"
        assert kvlcc2.T == 20.8, "T 应为 20.8 m"
        assert kvlcc2.V_disp == 312622.0, "V_disp 应为 312622 m³ (SIMMAN 2008)"
        assert abs(kvlcc2.C_B - 0.8098) < 1e-4, "C_B 应为 0.8098"

    def test_load_kvlcc2_derived_coefficients(self, kvlcc2):
        """派生系数应在合理范围"""
        assert 0.99 < kvlcc2.C_M < 1.0, "C_M 应在 0.99-1.0"
        assert 0.7 < kvlcc2.C_P < 0.9, "C_P 应在 0.7-0.9"
        assert 0.8 < kvlcc2.C_WP < 0.9, "C_WP 应在 0.8-0.9"

    def test_validate_raises_on_invalid(self):
        """超出范围的参数应抛出异常"""
        with pytest.raises(ValueError):
            HoltropMennenInput(
                L=320, B=58, T=20.8, V_disp=312600,
                C_B=0.5, C_M=0.5, C_P=1.0, C_WP=0.85,
                lcb=-2.5, A_BT=50, h_B=5, C_stern=-10, S_app=112.5
            ).validate()  # C_M=0.5 超出 [0.9, 1.0]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
