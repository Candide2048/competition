# -*- coding: utf-8 -*-
"""闸门1: ERA5 加载器单元测试

验证目标：
    - ERA5 数据可正常加载
    - 单点采样物理量级正确
    - 复现 verify_physics_fix.py 的 rho≈1.171, wpd≈326.1 W/m²（±5%）

运行方式：
    cd shipping_wasp/code
    python -m pytest tests/test_era5_loader.py -v
"""
import os
import sys
import numpy as np
import pytest

# 将 code/ 目录加入 sys.path，便于 import core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.era5_loader import ERA5Dataset, load_era5_from_config


# ---------- 测试夹具 ----------

@pytest.fixture(scope="module")
def era5():
    """加载 ERA5 数据集（模块级共享，避免重复打开）"""
    ds = load_era5_from_config()
    yield ds
    ds.close()


# ---------- 闸门1: ERA5 加载与物理量级验证 ----------

class TestERA5LoaderGate1:
    """闸门1：复现 verify_physics_fix.py 的 rho≈1.171, wpd≈326.1"""

    def test_data_loaded_successfully(self, era5):
        """测试数据成功加载"""
        assert era5.merged is not None
        # 四个变量都存在
        for var in ["u10", "v10", "msl", "sst"]:
            assert var in era5.merged.data_vars, f"变量 {var} 缺失"

    def test_dimensions_correct(self, era5):
        """测试维度正确：8760 小时 × 201 纬度 × 401 经度"""
        assert era5.merged.sizes["valid_time"] == 8760, "时间维度应为 8760 小时"
        assert era5.merged.sizes["latitude"] == 201, "纬度维度应为 201"
        assert era5.merged.sizes["longitude"] == 401, "经度维度应为 401"

    def test_coordinate_range(self, era5):
        """测试坐标范围：lat 40→-10, lon 30→130"""
        lat = era5.merged.latitude.values
        lon = era5.merged.longitude.values
        assert lat[0] == 40.0 and lat[-1] == -10.0, "纬度应从 40 递减到 -10"
        assert lon[0] == 30.0 and lon[-1] == 130.0, "经度应从 30 递增到 130"

    def test_sample_point_nearest(self, era5):
        """测试单点采样（15°N, 65°E，北印度洋）"""
        pt = era5.sample_point(lat=15.0, lon=65.0)
        assert pt is not None
        # 采样点应返回 8760 个时间步
        assert len(pt.valid_time) == 8760

    def test_physical_quantities_magnitude(self, era5):
        """闸门1核心：验证物理量级（rho≈1.171, wpd≈326.1）

        复现 verify_physics_fix.py 的计算：
            ws = sqrt(u10² + v10²)
            rho = msl / (287.05 × sst)   # T 用开尔文！
            wpd = 0.5 × rho × ws³
        """
        pt = era5.sample_point(lat=15.0, lon=65.0)

        # 风速
        u10 = pt.u10.values
        v10 = pt.v10.values
        ws = np.sqrt(u10**2 + v10**2)

        # 空气密度（T 必须用开尔文，不减 273.15）
        msl = pt.msl.values
        sst = pt.sst.values  # 开尔文
        R_specific = 287.05  # J/(kg·K)
        rho = msl / (R_specific * sst)

        # 风功率密度
        wpd = 0.5 * rho * ws**3

        # 闸门1验证：rho 均值应 ≈ 1.171 kg/m³（±5%）
        rho_mean = rho.mean()
        assert 1.11 < rho_mean < 1.23, \
            f"空气密度均值 {rho_mean:.3f} 超出 [1.11, 1.23] 区间，期望≈1.171"

        # 闸门1验证：wpd 均值应 ≈ 326.1 W/m²（±10%，wpd 波动较大放宽到 10%）
        wpd_mean = wpd.mean()
        assert 293 < wpd_mean < 359, \
            f"风功率密度均值 {wpd_mean:.1f} 超出 [293, 359] 区间，期望≈326.1"

        # 风速均值应 ≈ 6.92 m/s（verify_physics_fix.py 报告值）
        ws_mean = ws.mean()
        assert 6.5 < ws_mean < 7.4, \
            f"风速均值 {ws_mean:.2f} 超出 [6.5, 7.4] 区间，期望≈6.92"

    def test_msl_pressure_reasonable(self, era5):
        """测试海平面气压合理（~101325 Pa）"""
        pt = era5.sample_point(lat=15.0, lon=65.0)
        msl_mean = pt.msl.values.mean()
        assert 99000 < msl_mean < 103000, \
            f"海平面气压 {msl_mean:.0f} Pa 不合理，期望≈101325"

    def test_sst_kelvin(self, era5):
        """测试 SST 单位为开尔文（~301 K ≈ 28°C，热带海域）"""
        pt = era5.sample_point(lat=15.0, lon=65.0)
        sst_mean = pt.sst.values.mean()
        # 开尔文范围 295-305 K（22-32°C）
        assert 295 < sst_mean < 305, \
            f"SST {sst_mean:.1f} K 不合理，期望 295-305 K（热带海域）"


# ---------- 辅助功能测试 ----------

class TestERA5DatasetUtility:
    """ERA5Dataset 辅助功能"""

    def test_sample_route(self, era5):
        """测试航路点序列采样"""
        # 波斯湾→阿拉伯海 2 个航路点
        waypoints = [(29.0, 49.0), (24.0, 60.0)]
        # 对应时间（取 2025-01-15 的两个时刻）
        times = [
            np.datetime64("2025-01-15T00:00:00"),
            np.datetime64("2025-01-15T06:00:00"),
        ]
        ds = era5.sample_route(waypoints, times)
        assert ds.sizes["step"] == 2, "应返回 2 个采样点"
        for var in ["u10", "v10", "msl", "sst"]:
            assert var in ds.data_vars

    def test_time_slice(self, era5):
        """测试时间切片采样"""
        pt = era5.sample_point(
            lat=15.0, lon=65.0,
            time_slice=slice("2025-07-01", "2025-07-31")
        )
        # 7 月有 31 天 × 24 小时 = 744 小时
        assert len(pt.valid_time) == 744, "7 月应返回 744 小时数据"

    def test_context_manager(self):
        """测试上下文管理器（with 语句）"""
        from core.era5_loader import load_era5_from_config
        with load_era5_from_config() as era5:
            pt = era5.sample_point(lat=15.0, lon=65.0)
            assert pt is not None
        # 退出后应已关闭


if __name__ == "__main__":
    # 直接运行：python tests/test_era5_loader.py
    pytest.main([__file__, "-v", "--tb=short"])
