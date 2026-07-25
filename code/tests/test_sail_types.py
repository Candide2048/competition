# -*- coding: utf-8 -*-
"""刚性翼帆与吸力帆气动模型测试

验证 RigidWingSail (Song 2025 极曲线) 与 SuctionSail (参数化极曲线) 的
物理合理性、边界条件、最优控制单调性，以及与文献参考指标的一致性。
"""
import os
import sys

import numpy as np
import pytest

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from models.aerodynamics.rigid_wing import RigidWingSail, CD_FLOOR
from models.aerodynamics.suction_sail import SuctionSail
from models.atmosphere import rho_air


RHO = 1.20  # 标准空气密度 (kg/m³)


# ═══════════════════════════════════════════════════════════
# 刚性翼帆
# ═══════════════════════════════════════════════════════════

class TestRigidWingSail:
    """刚性翼帆 (Song 2025 风洞极曲线)"""

    @pytest.fixture
    def sail(self):
        return RigidWingSail.from_config()

    def test_load_from_config(self, sail):
        """应从 sail_types.yaml 成功加载投影面积与极曲线"""
        assert sail.projected_area == 750.0
        cl, cd = sail.cl_cd(40.0)
        assert cl > 0 and cd > 0

    def test_cd_floor_applied(self, sail):
        """CD@90° 原始 0.00 应被下限修正为 ≥ CD_FLOOR"""
        _, cd = sail.cl_cd(90.0)
        assert cd >= CD_FLOOR

    def test_cl_monotonic_rise(self, sail):
        """升力系数应随攻角单调上升（Song 数据特征）"""
        cl0, _ = sail.cl_cd(0.0)
        cl40, _ = sail.cl_cd(40.0)
        cl80, _ = sail.cl_cd(80.0)
        assert cl0 < cl40 < cl80

    def test_cl_max_matches_reference(self, sail):
        """单翼 CL_max 应接近 Song 2025 的 1.38"""
        cl, _ = sail.cl_cd(90.0)
        assert 1.3 < cl < 1.45

    def test_cross_wind_thrust_positive(self, sail):
        """横风 (β=90°) 下最优攻角应产生正推力"""
        opt = sail.optimal_control(V_apparent=15.0, rho_air=RHO, beta=np.pi / 2)
        assert opt["thrust"] > 0
        assert 0 <= opt["aoa_opt_deg"] <= 90

    def test_no_drive_power(self, sail):
        """翼帆无机械驱动功耗"""
        f = sail.forces(15.0, RHO, np.pi / 2, aoa_deg=40.0)
        assert f["power_rotor"] == 0.0

    def test_thrust_scales_with_v_squared(self, sail):
        """推力应随风速平方增长"""
        f1 = sail.forces(10.0, RHO, np.pi / 2, aoa_deg=40.0)
        f2 = sail.forces(20.0, RHO, np.pi / 2, aoa_deg=40.0)
        assert abs(f2["thrust"] / f1["thrust"] - 4.0) < 0.01

    def test_cl_gain_increases_lift(self):
        """升力增益（襟翼/双元素）应提升升力"""
        base = RigidWingSail.from_config(cl_gain=1.0)
        flap = RigidWingSail.from_config(cl_gain=1.27)
        cl_base, _ = base.cl_cd(40.0)
        cl_flap, _ = flap.cl_cd(40.0)
        assert cl_flap > cl_base * 1.2


# ═══════════════════════════════════════════════════════════
# 吸力帆
# ═══════════════════════════════════════════════════════════

class TestSuctionSail:
    """吸力帆 (参数化极曲线)"""

    @pytest.fixture
    def sail(self):
        return SuctionSail.from_config()

    def test_load_from_config(self, sail):
        """应从 sail_types.yaml 成功加载"""
        assert sail.projected_area == 66.0
        assert sail.CL_max == 7.0

    def test_cl_peaks_at_stall(self, sail):
        """CL 应在失速攻角处达到 CL_max"""
        cl_stall, _ = sail.cl_cd(sail.stall_aoa)
        assert abs(cl_stall - sail.CL_max) < 1e-6

    def test_cl_declines_after_stall(self, sail):
        """失速后 CL 应下降"""
        cl_stall, _ = sail.cl_cd(sail.stall_aoa)
        cl_post, _ = sail.cl_cd(sail.stall_aoa + 10)
        assert cl_post < cl_stall

    def test_ld_max_near_reference(self, sail):
        """最大升阻比应接近标定目标 12（±1.5）"""
        aoas = np.arange(1.0, 25.0, 0.5)
        ld = [sail.cl_cd(a)[0] / sail.cl_cd(a)[1] for a in aoas]
        assert 10.5 < max(ld) < 13.5

    def test_high_lift_vs_rigid_wing(self, sail):
        """吸力帆峰值 CL 应远高于刚性翼帆（高升力特征）"""
        assert sail.CL_max > 5.0

    def test_suction_power_positive(self, sail):
        """工作时应有吸力风扇功耗"""
        f = sail.forces(15.0, RHO, np.pi / 2, aoa_deg=20.0)
        assert f["power_rotor"] > 0

    def test_off_state_zero(self, sail):
        """关闭状态升阻力与功耗均为 0"""
        f = sail.forces(15.0, RHO, np.pi / 2, aoa_deg=20.0, operating=False)
        assert f["thrust"] == 0.0 and f["power_rotor"] == 0.0

    def test_low_wind_turns_off(self, sail):
        """极低风速下最优控制应关闭吸力系统（净功率为 0）"""
        opt = sail.optimal_control(V_apparent=0.5, rho_air=RHO, beta=np.pi / 2)
        assert opt["net_power"] == 0.0
        assert opt["power_rotor"] == 0.0

    def test_strong_wind_net_positive(self, sail):
        """强风横风下最优控制净功率应为正"""
        opt = sail.optimal_control(V_apparent=18.0, rho_air=RHO, beta=np.pi / 2)
        assert opt["net_power"] > 0
        assert opt["thrust"] > 0


# ═══════════════════════════════════════════════════════════
# 三帆型横向对比（同风况）
# ═══════════════════════════════════════════════════════════

class TestSailComparison:
    """三帆型在相同风况下的横向一致性检查"""

    def test_all_produce_thrust_in_beam_wind(self):
        """横风强风下三帆型均应产生正推力"""
        from models.aerodynamics.flettner import FlettnerSail, FlettnerConfig
        flettner = FlettnerSail(FlettnerConfig(H=24, D=4, AR=6, D_e_D=3))
        rigid = RigidWingSail.from_config()
        suction = SuctionSail.from_config()

        beta = np.deg2rad(100)  # 略偏后的横风
        V = 15.0
        for sail in (flettner, rigid, suction):
            opt = sail.optimal_control(V_apparent=V, rho_air=RHO, beta=beta)
            assert opt["thrust"] > 0, f"{type(sail).__name__} 推力应为正"
