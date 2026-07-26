# -*- coding: utf-8 -*-
"""ERA5 数据加载器

复用 verify_physics_fix.py 的全英文路径 + xarray merge 模式，
封装为可查询接口。

用法:
    from core.era5_loader import load_era5_from_config
    era5 = load_era5_from_config()
    pt = era5.sample_point(lat=15.0, lon=65.0)
    era5.close()
"""
import os
import yaml
import numpy as np
import xarray as xr


# 默认配置路径（相对于 code/ 目录）
DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "paths.yaml"
)

# 默认数据路径（当配置文件不可用时使用）
DEFAULT_NC_WIND = r"D:\Pythonfiles\pythonProject\shipping_wasp\data\data_stream-oper_stepType-instant.nc"
DEFAULT_NC_METEO = r"D:\Pythonfiles\pythonProject\shipping_wasp\data\data_stream-oper_stepType-instant (2).nc"


def _validate_no_chinese(path: str) -> None:
    """校验路径不含中文字符（避免 Windows C 库 fopen bug）"""
    try:
        path.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError(
            f"路径含非 ASCII 字符（可能触发 netCDF4/xarray bug）: {path}\n"
            "请将数据文件移至全英文路径。"
        )


def _load_paths_config(config_path: str) -> dict:
    """从 paths.yaml 读取数据路径"""
    if not os.path.exists(config_path):
        # 配置文件不存在，用默认路径
        return {"era5": {"nc_wind": DEFAULT_NC_WIND, "nc_meteo": DEFAULT_NC_METEO}}

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if cfg is None:
        # 空配置文件（仅注释），用默认路径
        return {"era5": {"nc_wind": DEFAULT_NC_WIND, "nc_meteo": DEFAULT_NC_METEO}}

    paths = {
        "nc_wind": cfg.get("era5", {}).get("nc_wind", DEFAULT_NC_WIND),
        "nc_meteo": cfg.get("era5", {}).get("nc_meteo", DEFAULT_NC_METEO),
        "validate_no_chinese": cfg.get("validate_no_chinese", True),
    }
    return {"era5": paths}


class ERA5Dataset:
    """ERA5 数据集封装，支持按时间/经纬度查询与航线采样

    数据维度：
        - valid_time: 8760 小时（2025-01-01 ~ 2025-12-31）
        - latitude: 201 点（40 → -10，递减，0.25° 网格）
        - longitude: 401 点（30 → 130，递增，0.25° 网格）
    变量：
        - u10, v10: 10m 风场 (m/s)
        - msl: 海平面气压 (Pa)
        - sst: 海表温度 (K，开尔文！)
    """

    def __init__(self, nc_wind_path: str, nc_meteo_path: str,
                 validate_path: bool = True) -> None:
        """打开两个 NC 文件并 merge；不立即载入数据（lazy load）

        Args:
            nc_wind_path: u10/v10 文件路径
            nc_meteo_path: msl/sst 文件路径
            validate_path: 是否校验路径不含中文
        """
        if validate_path:
            _validate_no_chinese(nc_wind_path)
            _validate_no_chinese(nc_meteo_path)

        if not os.path.exists(nc_wind_path):
            raise FileNotFoundError(f"风场文件不存在: {nc_wind_path}")
        if not os.path.exists(nc_meteo_path):
            raise FileNotFoundError(f"气象文件不存在: {nc_meteo_path}")

        # 打开两个文件（lazy load，不占内存）
        self.ds_wind = xr.open_dataset(nc_wind_path)
        self.ds_meteo = xr.open_dataset(nc_meteo_path)

        # 合并四个变量（与 verify_physics_fix.py 一致）
        self.merged = xr.merge([
            self.ds_wind[["u10", "v10"]],
            self.ds_meteo[["msl", "sst"]]
        ], compat="no_conflicts")

        self._closed = False

    def sample_point(self, lat: float, lon: float,
                     time_slice: slice | None = None) -> xr.Dataset:
        """单点采样（method='nearest'），返回该点全时段或指定时段的数据

        Args:
            lat: 纬度（-10 到 40）
            lon: 经度（30 到 130）
            time_slice: 可选，时间切片，如 slice('2025-07-01', '2025-07-31')

        Returns:
            Dataset 含 u10, v10, msl, sst，维度为 (valid_time,)
        """
        if time_slice is not None:
            ds = self.merged.sel(valid_time=time_slice)
        else:
            ds = self.merged
        return ds.sel(latitude=lat, longitude=lon, method="nearest")

    def sample_route(self, waypoints: list[tuple[float, float]],
                     times: list) -> xr.Dataset:
        """沿航路点序列采样，返回逐时刻 (u10, v10, msl, sst) 数组

        Args:
            waypoints: 航路点列表 [(lat0, lon0), (lat1, lon1), ...]
            times: 对应时间列表（np.datetime64 或字符串）

        Returns:
            Dataset 含 u10, v10, msl, sst，维度为 (step,)，长度 = len(waypoints)
        """
        if len(waypoints) != len(times):
            raise ValueError(
                f"waypoints 长度 ({len(waypoints)}) 必须等于 times 长度 ({len(times)})"
            )

        # 逐点采样并合并
        samples = []
        for (lat, lon), t in zip(waypoints, times):
            pt = self.merged.sel(
                valid_time=t, latitude=lat, longitude=lon, method="nearest"
            )
            samples.append(pt)

        # 沿新维度 step 合并
        combined = xr.concat(samples, dim="step")
        return combined

    def get_variable_at(self, var: str, lat: float, lon: float,
                        time=None) -> np.ndarray:
        """获取单变量在指定点的时序数据

        Args:
            var: 变量名 ('u10', 'v10', 'msl', 'sst')
            lat, lon: 经纬度
            time: 可选时间或时间切片

        Returns:
            numpy 数组
        """
        pt = self.sample_point(lat, lon,
                               time_slice=slice(time) if time else None)
        return pt[var].values

    def close(self) -> None:
        """关闭打开的文件句柄"""
        if not self._closed:
            self.ds_wind.close()
            self.ds_meteo.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def load_era5_from_config(config_path: str | None = None) -> ERA5Dataset:
    """从 paths.yaml 读取路径并构造 ERA5Dataset

    Args:
        config_path: paths.yaml 路径，None 则用默认路径

    Returns:
        ERA5Dataset 实例
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    paths_cfg = _load_paths_config(config_path)
    era5_cfg = paths_cfg["era5"]

    return ERA5Dataset(
        nc_wind_path=era5_cfg["nc_wind"],
        nc_meteo_path=era5_cfg["nc_meteo"],
        validate_path=era5_cfg.get("validate_no_chinese", True),
    )
