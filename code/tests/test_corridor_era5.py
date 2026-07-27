# -*- coding: utf-8 -*-
"""闸门: ERA5 航线走廊 NPZ 加载器（CorridorERA5）回归测试

验证目标：
    - nearest_index 复刻 xarray sel(method="nearest") 平票/越界语义
    - NPZ schema v1 结构与 payload SHA256 完整性
    - sample_route 契约（Dataset 变量/长度/内部一致性）
    - 覆盖缺失 fail-closed（空间/时间越界抛 CorridorCoverageError）
    - 后端工厂（ERA5_BACKEND 覆写、corridor/none 分支）
    - 金标准：与全域 ERA5Dataset 逐比特一致（本地有 .nc 时）

运行方式：
    cd shipping_wasp/code
    python -m pytest tests/test_corridor_era5.py -v
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.corridor_era5 import (
    DEFAULT_NPZ_PATH,
    EPOCH,
    SCHEMA_VERSION,
    WEATHER_VARS,
    CorridorCoverageError,
    CorridorERA5,
    nearest_index,
)
from core import era5_loader


# ---------- 测试夹具 ----------

@pytest.fixture(scope="module")
def era5():
    """模块级共享走廊实例（NPZ 全量载入约 27 MiB，仅加载一次）"""
    return CorridorERA5()


def _covered_point(ds: CorridorERA5, pos: int = 0):
    """返回走廊内第 pos 个 cell 的 (lat, lon) 网格坐标"""
    lat = float(ds.grid_latitude[ds.cell_lat_idx[pos]])
    lon = float(ds.grid_longitude[ds.cell_lon_idx[pos]])
    return lat, lon


def _covered_time(ds: CorridorERA5, season: int = 0, hour: int = 0):
    """返回第 season 季窗口内偏移 hour 小时的时间戳"""
    return EPOCH + np.timedelta64(int(ds.season_start_hour[season]) + hour, "h")


# ---------- nearest_index 平票/越界语义 ----------

def test_nearest_index_tie_ascending():
    """递增轴平票（恰在中点）取数值较大的坐标"""
    axis = np.array([0.0, 0.25, 0.5])
    assert nearest_index(axis, 0.125) == 1   # 平票 → 0.25
    assert nearest_index(axis, 0.375) == 2   # 平票 → 0.5
    assert nearest_index(axis, 0.1) == 0     # 非平票 → 最近


def test_nearest_index_tie_descending():
    """递减轴（ERA5 纬度轴）平票同样取数值较大的坐标"""
    axis = np.array([0.5, 0.25, 0.0])
    assert nearest_index(axis, 0.125) == 1   # 平票 → 0.25
    assert nearest_index(axis, 0.375) == 0   # 平票 → 0.5


def test_nearest_index_clamp():
    """越界 clamp 到端点"""
    axis = np.array([0.0, 0.25, 0.5])
    assert nearest_index(axis, -99.0) == 0
    assert nearest_index(axis, 99.0) == 2


# ---------- NPZ schema 与完整性 ----------

def test_npz_exists_and_schema(era5):
    """NPZ 随 git 分发、schema v1、轴/载荷形状自洽（构造即校验 SHA256）"""
    assert os.path.exists(DEFAULT_NPZ_PATH)
    assert int(era5.manifest["schema_version"]) == SCHEMA_VERSION
    # 轴：纬度递减、经度递增
    assert era5.grid_latitude[0] > era5.grid_latitude[-1]
    assert era5.grid_longitude[0] < era5.grid_longitude[-1]
    # 载荷: (4季, W小时, N cell, 4变量)
    n_cells = len(era5.cell_lat_idx)
    assert era5.weather.shape == (
        4, era5.window_hours + 1, n_cells, len(WEATHER_VARS))
    assert era5.weather.dtype == np.float32
    assert set(era5.season_names) == {"winter", "spring", "summer", "autumn"}
    assert len(era5.cell_lon_idx) == n_cells


# ---------- sample_route 契约 ----------

def test_sample_route_contract(era5):
    """返回 Dataset 含 4 个变量，step 维长度 = 航路点数"""
    wps = [_covered_point(era5, 0), _covered_point(era5, 1)]
    times = [_covered_time(era5, 0, 0), _covered_time(era5, 0, 1)]
    ds = era5.sample_route(wps, times)
    for var in WEATHER_VARS:
        assert var in ds
        assert ds[var].dims == ("step",)
        assert ds[var].shape == (2,)


def test_sample_route_internal_consistency(era5):
    """采样值与 weather 数组直接索引逐比特一致"""
    pos = len(era5.cell_lat_idx) // 2
    lat, lon = _covered_point(era5, pos)
    si, hour = 2, 7
    ds = era5.sample_route([(lat, lon)], [_covered_time(era5, si, hour)])
    for vi, var in enumerate(WEATHER_VARS):
        expect = float(era5.weather[si, hour, pos, vi])
        got = float(ds[var].values[0])
        if np.isnan(expect):
            assert np.isnan(got)
        else:
            assert got == expect


def test_sample_route_length_mismatch(era5):
    """waypoints 与 times 长度不一致 → ValueError"""
    with pytest.raises(ValueError):
        era5.sample_route([_covered_point(era5)], [])


# ---------- 覆盖缺失 fail-closed ----------

def test_coverage_spatial_fail_closed(era5):
    """走廊外网格点 → CorridorCoverageError（绝不静默回退）"""
    # 从网格角落起找一个不在走廊内的 cell
    outside = None
    for li in range(len(era5.grid_latitude)):
        if (li, 0) not in era5._slots:
            outside = (float(era5.grid_latitude[li]),
                       float(era5.grid_longitude[0]))
            break
    assert outside is not None, "走廊不应覆盖整条经度边界"
    with pytest.raises(CorridorCoverageError):
        era5.sample_route([outside], [_covered_time(era5)])


def test_coverage_temporal_fail_closed(era5):
    """季节窗口外时间 → CorridorCoverageError"""
    t = EPOCH - np.timedelta64(1000, "h")
    with pytest.raises(CorridorCoverageError):
        era5.sample_route([_covered_point(era5)], [t])


def test_time_tie_half_hour_takes_later(era5):
    """时间平票（恰在半点）取较晚整点，与 xarray nearest 实测一致"""
    start = int(era5.season_start_hour[0])
    t = EPOCH + np.timedelta64(start * 60 + 30, "m")  # 起点 + 30 分钟
    si, off = era5._locate_time(t)
    assert (si, off) == (0, 1)


# ---------- 后端工厂 ----------

def test_backend_env_override(monkeypatch):
    """ERA5_BACKEND 环境变量显式覆写优先于 auto 探测"""
    monkeypatch.setenv("ERA5_BACKEND", "corridor")
    assert era5_loader.resolve_era5_backend() == "corridor"
    monkeypatch.setenv("ERA5_BACKEND", "none")
    assert era5_loader.resolve_era5_backend() == "none"


def test_backend_env_invalid(monkeypatch):
    """非法 ERA5_BACKEND 值 → ValueError"""
    monkeypatch.setenv("ERA5_BACKEND", "bogus")
    with pytest.raises(ValueError):
        era5_loader.resolve_era5_backend()


def test_factory_corridor():
    """工厂 backend="corridor" → CorridorERA5 实例"""
    ds = era5_loader.load_era5_from_config(backend="corridor")
    assert isinstance(ds, CorridorERA5)
    assert ds.backend == "corridor"
    ds.close()


def test_factory_none_raises():
    """工厂 backend="none" → RuntimeError（无数据源不可构造）"""
    with pytest.raises(RuntimeError):
        era5_loader.load_era5_from_config(backend="none")


# ---------- 金标准：与全域 ERA5Dataset 逐比特一致 ----------

_NC_OK = False
try:
    _cfg = era5_loader._load_paths_config(era5_loader.DEFAULT_CONFIG_PATH)["era5"]
    _NC_OK = (os.path.exists(_cfg["nc_wind"])
              and os.path.exists(_cfg["nc_meteo"]))
except Exception:
    pass


@pytest.mark.skipif(not _NC_OK, reason="全域 ERA5 .nc 不可用（CI/部署环境）")
def test_golden_vs_full_era5(era5):
    """走廊采样与全域 ERA5Dataset.sample_route 在 f32 精度下逐比特一致"""
    full = era5_loader.load_era5_from_config(backend="full")
    try:
        n = len(era5.cell_lat_idx)
        for si in range(4):
            t = _covered_time(era5, si, 7)
            wps = [_covered_point(era5, p) for p in (0, n // 2, n - 1)]
            times = [t] * len(wps)
            a = era5.sample_route(wps, times)
            b = full.sample_route(wps, times)
            for var in WEATHER_VARS:
                np.testing.assert_array_equal(
                    np.asarray(a[var].values, dtype=np.float32),
                    np.asarray(b[var].values, dtype=np.float32),
                    err_msg=f"season={si} var={var}")
    finally:
        full.close()
