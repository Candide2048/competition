# -*- coding: utf-8 -*-
"""闸门2: Flettner 转子帆气动模型单元测试

验证目标：
    - SR=0 边界条件严格返回 (0, 0.5, 0)
    - CL 量级合理（SR=2, AR=6, D_e/D=2 时 C_L∈[4,12]）
    - CL 随 SR 单调上升至峰值后趋缓
    - 力计算公式正确
    - 最优 SR 搜索有效

运行方式：
    cd shipping_wasp/code
    python -m pytest tests/test_flettner.py -v
"""
import os
import sys
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.aerodynamics.flettner import FlettnerSail, FlettnerConfig


# ---------- 测试夹具 ----------

@pytest.fixture
def sail_default():
    """默认 Flettner 配置（MVP 中位值）"""
    return FlettnerSail(FlettnerConfig(H=20.0, D=4.0, AR=5.0, D_e_D=3.0))


@pytest.fixture
def sail_verification():
    """验证用配置（AR=6, D_e/D=2，用于对照 ③ 综述 CL 量级）"""
    return FlettnerSail(FlettnerConfig(H=24.0, D=4.0, AR=6.0, D_e_D=2.0))


# ---------- 闸门2: SR=0 边界条件 ----------

class TestFlettnerGate2Boundary:
    """闸门2：SR=0 边界条件验证"""

    def test_SR_zero_returns_boundary(self, sail_default):
        """SR=0 时必须严格返回 (0, 0.5, 0)"""
        cl, cd, cp = sail_default.cl_cd_cp(SR=0.0)
        assert cl == pytest.approx(0.0, abs=1e-6), f"SR=0 时 CL={cl} 应为 0"
        assert cd == pytest.approx(0.5, abs=1e-6), f"SR=0 时 CD={cd} 应为 0.5"
        assert cp == pytest.approx(0.0, abs=1e-6), f"SR=0 时 CP={cp} 应为 0"

    def test_SR_near_zero_uses_boundary(self, sail_default):
        """SR 极小（< 1e-10）时也用边界条件"""
        cl, cd, cp = sail_default.cl_cd_cp(SR=1e-12)
        assert cl == pytest.approx(0.0, abs=1e-6)
        assert cd == pytest.approx(0.5, abs=1e-6)


# ---------- 闸门2: CL 量级验证 ----------

class TestFlettnerGate2Magnitude:
    """闸门2：CL 量级验证（对照 ③ 综述 CL 峰值 9.5-17.97）"""

    def test_CL_typical_operation_in_range(self, sail_verification):
        """SR=2, AR=6, D_e/D=2 时 CL 应落在 [4, 12]"""
        cl, cd, cp = sail_verification.cl_cd_cp(SR=2.0)
        assert 4.0 <= cl <= 12.0, \
            f"CL={cl:.3f} 超出 [4, 12] 区间（SR=2, AR=6, D_e/D=2）"

    def test_CL_peak_below_18(self, sail_verification):
        """CL 峰值不应超过 ③ 综述上限 17.97（放宽到 18）"""
        # 扫描 SR ∈ [0, 5] 找峰值
        SRs = np.linspace(0.1, 5.0, 100)
        CLs = [sail_verification.cl_cd_cp(sr)[0] for sr in SRs]
        cl_peak = max(CLs)
        assert cl_peak <= 18.0, \
            f"CL 峰值 {cl_peak:.2f} 超过 18.0（③ 综述上限 17.97）"

    def test_CL_positive_for_positive_SR(self, sail_default):
        """正 SR（顺时针）应产生正 CL"""
        cl, _, _ = sail_default.cl_cd_cp(SR=2.0)
        assert cl > 0, f"正 SR 应产生正 CL，得到 {cl}"

    def test_CL_positive_in_cfd_valid_range(self, sail_default):
        """在 Kwon 2022 CFD 数据有效区间 SR∈[1, 5] 内 CL 应为正

        注意：Kwon 2022 原始 CFD 数据仅覆盖 SR∈[1,5]（⑤ §3 明示），
        负 SR 区域为公式外推，回归多项式含偶次项不保证马格努斯方向反转，
        故不在负 SR 区间断言物理符号。
        ⑤ 应用层将 SR 范围扩展至 ±5 以涵盖顺/逆时针旋转，
        但本研究只在 [1, 5] 验证物理可信性。
        """
        for sr in [1.0, 2.0, 3.0, 4.0, 5.0]:
            cl, _, _ = sail_default.cl_cd_cp(SR=sr)
            assert cl > 0, f"SR={sr}（CFD 有效区间）应产生正 CL，得到 {cl}"


# ---------- CL 单调性验证 ----------

class TestFlettnerMonotonicity:
    """CL 随 SR 变化趋势验证"""

    def test_CL_increasing_at_low_SR(self, sail_default):
        """低 SR 区间（0-2）CL 应单调上升"""
        SRs = np.linspace(0.5, 2.0, 10)
        CLs = [sail_default.cl_cd_cp(sr)[0] for sr in SRs]
        # 检查总体上升趋势（允许局部小波动）
        assert CLs[-1] > CLs[0], \
            f"CL 应在低 SR 区间上升：CL(0.5)={CLs[0]}, CL(2.0)={CLs[-1]}"

    def test_CD_positive(self, sail_default):
        """CD 应始终为正（阻力不能为负）"""
        for SR in [0.0, 0.5, 1.0, 2.0, 3.0, 5.0]:
            _, cd, _ = sail_default.cl_cd_cp(SR=SR)
            assert cd > 0, f"SR={SR} 时 CD={cd} 应为正"


# ---------- 力计算验证 ----------

class TestFlettnerForces:
    """力计算公式验证"""

    def test_forces_keys(self, sail_default):
        """forces 返回值应包含所有必需字段"""
        f = sail_default.forces(
            V_apparent=10.0, rho_air=1.171, beta=np.pi/4, SR=2.0
        )
        required_keys = {"lift", "drag", "thrust", "side_force",
                         "power_rotor", "CL", "CD", "CP"}
        assert set(f.keys()) >= required_keys, f"缺少字段: {required_keys - set(f.keys())}"

    def test_lift_formula(self, sail_default):
        """验证升力公式 L = ½ρV²S·CL"""
        V, rho, beta, SR = 10.0, 1.171, np.pi/4, 2.0
        f = sail_default.forces(V, rho, beta, SR=SR)
        cl, _, _ = sail_default.cl_cd_cp(SR)
        S = sail_default.config.S
        L_expected = 0.5 * rho * V**2 * S * cl
        assert f["lift"] == pytest.approx(L_expected, rel=1e-6)

    def test_thrust_formula(self, sail_default):
        """验证推力公式 T = L·sin(β) − D·cos(β)"""
        V, rho, beta, SR = 10.0, 1.171, np.pi/4, 2.0
        f = sail_default.forces(V, rho, beta, SR=SR)
        T_expected = f["lift"] * np.sin(beta) - f["drag"] * np.cos(beta)
        assert f["thrust"] == pytest.approx(T_expected, rel=1e-6)

    def test_power_rotor_formula(self, sail_default):
        """验证功率公式 P = ½ρV³S·CP"""
        V, rho, beta, SR = 10.0, 1.171, np.pi/4, 2.0
        f = sail_default.forces(V, rho, beta, SR=SR)
        _, _, cp = sail_default.cl_cd_cp(SR)
        S = sail_default.config.S
        P_expected = 0.5 * rho * V**3 * S * cp
        assert f["power_rotor"] == pytest.approx(P_expected, rel=1e-6)

    def test_thrust_positive_at_crosswind(self, sail_default):
        """横风（β=π/2）时推力应较大（升力全部转化为推力）"""
        V, rho, SR = 10.0, 1.171, 2.0
        f_cross = sail_default.forces(V, rho, beta=np.pi/2, SR=SR)
        f_head = sail_default.forces(V, rho, beta=0.0, SR=SR)
        assert f_cross["thrust"] > f_head["thrust"], \
            "横风推力应大于顶风推力"


# ---------- 最优控制验证 ----------

class TestFlettnerOptimalControl:
    """最优 SR 搜索验证"""

    def test_optimal_control_returns_valid_SR(self, sail_default):
        """最优 SR 应在 [0, 5] 范围内（Kwon CFD 有效区间 + SR=0 边界）"""
        opt = sail_default.optimal_control(
            V_apparent=10.0, rho_air=1.171, beta=np.pi/4
        )
        assert 0.0 <= opt["SR_opt"] <= 5.0
        assert "thrust" in opt
        assert "net_power" in opt

    def test_optimal_better_than_zero(self, sail_default):
        """最优 SR 的净功率应优于 SR=0"""
        opt = sail_default.optimal_control(
            V_apparent=10.0, rho_air=1.171, beta=np.pi/4
        )
        f_zero = sail_default.forces(10.0, 1.171, np.pi/4, SR=0.0)
        net_zero = f_zero["thrust"] * 10.0 - f_zero["power_rotor"]
        assert opt["net_power"] >= net_zero, \
            f"最优净功率 {opt['net_power']} 应 ≥ SR=0 净功率 {net_zero}"

    def test_projected_area(self, sail_default):
        """投影面积应等于 H × D"""
        expected = sail_default.config.H * sail_default.config.D
        assert sail_default.projected_area == pytest.approx(expected)


# ---------- 配置校验 ----------

class TestFlettnerConfig:
    """配置校验"""

    def test_auto_compute_S(self):
        """S=0 时应自动计算为 H × D"""
        cfg = FlettnerConfig(H=20.0, D=4.0, AR=5.0, D_e_D=3.0, S=0.0)
        assert cfg.S == 80.0  # 20 × 4

    def test_validate_out_of_range(self):
        """超出范围的配置应抛出异常"""
        with pytest.raises(ValueError):
            FlettnerConfig(H=5.0, D=4.0, AR=5.0, D_e_D=3.0).validate()  # H<10
        with pytest.raises(ValueError):
            FlettnerConfig(H=20.0, D=4.0, AR=3.0, D_e_D=3.0).validate()  # AR<4


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
