# -*- coding: utf-8 -*-
"""ERA5 航线走廊预抽取加载器（部署瘦身方案）

背景:
    全域 ERA5 .nc 约 4.5 GB，无法随部署镜像分发。本模块加载由
    pipelines/extract_corridor.py 预抽取的走廊 NPZ（约 27 MiB，随 git 分发），
    对配置航线（routes.yaml）× 4 季节 × 719 小时窗口内的任意采样请求，
    返回与全域 ERA5Dataset.sample_route 逐比特一致的数值。

语义保证:
    - nearest 平票语义与 xarray sel(method="nearest") 实测一致：
      经/纬度平票取数值较大坐标，时间平票取较晚时刻，越界 clamp 到端点。
    - 覆盖缺失一律 fail-closed：抛 CorridorCoverageError，绝不静默回退。

用法:
    from core.corridor_era5 import CorridorERA5
    era5 = CorridorERA5()          # 默认 results/precomputed/era5_corridor_v1.npz
    ds = era5.sample_route(waypoints, times)   # 与 ERA5Dataset.sample_route 同契约
"""
import hashlib
import json
import os

import numpy as np
import xarray as xr

SCHEMA_VERSION = 1
EPOCH = np.datetime64("2025-01-01T00:00:00")
WEATHER_VARS = ("u10", "v10", "msl", "sst")

DEFAULT_NPZ_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "results", "precomputed", "era5_corridor_v1.npz",
)


class CorridorCoverageError(RuntimeError):
    """采样点（空间或时间）不在预抽取走廊覆盖范围内。"""


def nearest_index(axis: np.ndarray, value: float, tol: float = 1e-9) -> int:
    """复刻 xarray sel(method="nearest") 的索引选择（含平票语义）

    实测语义（xarray 2024.x，合成 DataArray 验证）:
        - 平票（value 恰在两格点中点）取数值较大的坐标
        - 越界 clamp 到端点

    Args:
        axis: 一维坐标轴（递增或递减均可）
        value: 查询值
        tol: 平票判定容差（0.25° 网格下距离均为二进制精确值，容差仅防御）

    Returns:
        int: 选中的轴索引
    """
    d = np.abs(axis - value)
    cand = np.flatnonzero(d <= d.min() + tol)
    return int(cand[np.argmax(axis[cand])])


class CorridorERA5:
    """走廊 NPZ 加载器，与 ERA5Dataset.sample_route 接口兼容

    NPZ schema v1（allow_pickle=False）:
        manifest_json    uint8[...]      JSON 清单（schema/指纹/payload 哈希）
        grid_latitude    float64[201]    完整纬度轴（40 → -10 递减）
        grid_longitude   float64[401]    完整经度轴（30 → 130 递增）
        cell_lat_idx     uint8[N]        走廊 cell 纬度索引（按 (lat,lon) 排序）
        cell_lon_idx     uint16[N]       走廊 cell 经度索引
        season_names     str[4]          季节名（winter/spring/summer/autumn）
        season_start_hour int32[4]       各季窗口起点（相对 2025-01-01T00 的小时）
        hour_offset      uint16[W]       窗口内小时偏移（0..W-1）
        weather          float32[4,W,N,4] 末维为 (u10, v10, msl, sst)，NaN 原样保留
    """

    backend = "corridor"

    def __init__(self, npz_path: str | None = None) -> None:
        path = npz_path or DEFAULT_NPZ_PATH
        if not os.path.exists(path):
            raise FileNotFoundError(f"走廊 NPZ 不存在: {path}")

        with np.load(path, allow_pickle=False) as z:
            manifest = json.loads(bytes(z["manifest_json"].tobytes()).decode("utf-8"))
            if int(manifest.get("schema_version", -1)) != SCHEMA_VERSION:
                raise ValueError(
                    f"走廊 NPZ schema 版本不匹配: 期望 {SCHEMA_VERSION}, "
                    f"实际 {manifest.get('schema_version')}"
                )
            self.grid_latitude = np.asarray(z["grid_latitude"], dtype=np.float64)
            self.grid_longitude = np.asarray(z["grid_longitude"], dtype=np.float64)
            self.cell_lat_idx = np.asarray(z["cell_lat_idx"], dtype=np.int64)
            self.cell_lon_idx = np.asarray(z["cell_lon_idx"], dtype=np.int64)
            self.season_names = [str(s) for s in z["season_names"]]
            self.season_start_hour = np.asarray(z["season_start_hour"], dtype=np.int64)
            self.hour_offset = np.asarray(z["hour_offset"], dtype=np.int64)
            self.weather = np.asarray(z["weather"], dtype=np.float32)

        # fail-closed：payload 哈希不符即拒绝加载（防 git 损坏 / 手工篡改）
        digest = hashlib.sha256(self.weather.tobytes()).hexdigest()
        if digest != manifest.get("payload_sha256"):
            raise ValueError(
                "走廊 NPZ payload SHA256 校验失败，文件可能损坏，请重新生成: "
                f"期望 {manifest.get('payload_sha256')}, 实际 {digest}"
            )

        self.manifest = manifest
        self.window_hours = int(self.hour_offset[-1])  # 最大偏移（W-1）
        self._slots = {
            (int(la), int(lo)): pos
            for pos, (la, lo) in enumerate(zip(self.cell_lat_idx, self.cell_lon_idx))
        }
        self._closed = False

    # ── 时间定位 ──────────────────────────────────────────────

    def _locate_time(self, t) -> tuple[int, int]:
        """时间 → (季节索引, 窗口内偏移)；不在任何窗口内则 fail-closed"""
        t64 = np.datetime64(t)
        hours = float((t64 - EPOCH) / np.timedelta64(1, "h"))
        # round-half-to-later：平票取较晚整点（与 xarray nearest 实测一致）
        h = int(np.floor(hours + 0.5))
        for si, start in enumerate(self.season_start_hour):
            off = h - int(start)
            if 0 <= off <= self.window_hours:
                return si, off
        raise CorridorCoverageError(
            f"采样时间 {t64} 不在任何预抽取季节窗口内 "
            f"(季节起点小时: {self.season_start_hour.tolist()}, "
            f"窗口长度: {self.window_hours + 1}h)"
        )

    # ── 与 ERA5Dataset 兼容的采样接口 ─────────────────────────

    def sample_route(self, waypoints: list[tuple[float, float]],
                     times: list) -> xr.Dataset:
        """沿航路点序列采样，契约与 ERA5Dataset.sample_route 一致

        Returns:
            Dataset 含 u10, v10, msl, sst，维度为 (step,)，长度 = len(waypoints)
        """
        if len(waypoints) != len(times):
            raise ValueError(
                f"waypoints 长度 ({len(waypoints)}) 必须等于 times 长度 ({len(times)})"
            )

        n = len(waypoints)
        out = {var: np.empty(n, dtype=np.float64) for var in WEATHER_VARS}
        for k, ((lat, lon), t) in enumerate(zip(waypoints, times)):
            li = nearest_index(self.grid_latitude, float(lat))
            oi = nearest_index(self.grid_longitude, float(lon))
            pos = self._slots.get((li, oi))
            if pos is None:
                raise CorridorCoverageError(
                    f"采样点 ({lat:.4f}, {lon:.4f}) → 网格 "
                    f"({self.grid_latitude[li]:.3f}, {self.grid_longitude[oi]:.3f}) "
                    "不在预抽取走廊内"
                )
            si, off = self._locate_time(t)
            vals = self.weather[si, off, pos, :]
            for vi, var in enumerate(WEATHER_VARS):
                out[var][k] = float(vals[vi])

        return xr.Dataset({var: ("step", out[var]) for var in WEATHER_VARS})

    def close(self) -> None:
        """与 ERA5Dataset 接口对齐（NPZ 已全量载入内存，无句柄可关）"""
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
