# -*- coding: utf-8 -*-
"""ERA5 CDS API 批量下载脚本（3-5 年数据）

设计要点（响应用户判断）：
- API 模式比手动下载灵活：可指定变量+时空范围+年份，避免冗余
- 单次请求限制：CDS 服务器排队，单次请求合理大小（一年一请求）
- 用 cdsapi Python 包（已配置 ~/.cdsapirc）
- 不需要合并字段：直接请求所需变量到单个 NC 文件
- 用户偏好：3-5 年数据（不是 40 年），用预测模型或移动均值

用法:
    py -3.11 era5_cds_batch.py                    # 默认下载 2021-2025 全年
    py -3.11 era5_cds_batch.py --years 2023 2024 2025
    py -3.11 era5_cds_batch.py --years 2023-2025 --months 6 7 8  # 仅夏季
    py -3.11 era5_cds_batch.py --dry-run          # 只打印请求体不提交

输出: shipping_wasp/data/era5_<year>.nc（每年一个文件）
"""
import os
import sys
import json
import time
import argparse
from pathlib import Path

# ---------- 配置 ----------
DATA_DIR = r'D:\Pythonfiles\pythonProject\shipping_wasp\data'
DEFAULT_VARS = ['u10', 'v10', 'msl', 'sst']  # 4 必需变量（与现有手动下载一致）
# 默认时空范围（与现有 2025 全年数据一致：30°E–130°E, 10°S–40°N）
DEFAULT_LAT_RANGE = [40, -10]   # 北→南
DEFAULT_LON_RANGE = [30, 130]
DEFAULT_YEARS = [2021, 2022, 2023, 2024, 2025]  # 5 年
DEFAULT_MONTHS = list(range(1, 13))
DEFAULT_DAYS = [f'{i:02d}' for i in range(1, 32)]
DEFAULT_TIMES = [f'{i:02d}:00' for i in range(0, 24)]  # 逐小时


def build_request(year, months=DEFAULT_MONTHS, variables=DEFAULT_VARS,
                  lat_range=DEFAULT_LAT_RANGE, lon_range=DEFAULT_LON_RANGE):
    """构造 CDS API 请求体（一年一个请求）"""
    # ERA5 single-levels 区分 instant 和 accumulation，但我们 4 变量都是 instant
    # u10/v10/msl/sst 都是 instant 型，可放一个请求
    return {
        'product_type': 'reanalysis',
        'format': 'netcdf',
        'variable': variables,
        'year': str(year),
        'month': [f'{m:02d}' for m in months],
        'day': DEFAULT_DAYS,
        'time': DEFAULT_TIMES,
        'area': [
            lat_range[0],  # north
            lon_range[0],  # west
            lat_range[1],  # south
            lon_range[1],  # east
        ],
    }


def submit_and_wait(request, target_path, dataset='reanalysis-era5-single-levels', poll_interval=60):
    """提交请求并轮询直到完成，下载到 target_path"""
    try:
        import cdsapi
    except ImportError:
        print('  [ERROR] cdsapi 未安装，请运行: pip install cdsapi')
        return False

    print(f'  提交请求到 {dataset}')
    c = cdsapi.Client(quiet=True, progress=False)
    # cdsapi.Client().run 提交并等待，返回 True/False
    # 也可以用 c.status() + c.delete() 模式
    print(f'  目标文件: {target_path}')
    try:
        # cdsapi 的 wait_until_complete 会阻塞直到完成
        # 用 c.retrieve 是新版 API，自动等待
        r = c.retrieve(dataset, request, target_path)
        print(f'  [OK] 下载完成: {target_path}')
        return True
    except Exception as e:
        print(f'  [ERROR] {e}')
        return False


def estimate_size_mb(years, variables, lat_range, lon_range):
    """粗略估计下载大小（基于 2025 全年 4 变量 4.21 GB 的实测数据）"""
    # 2025 全年 u10/v10/msl/sst 4 变量，区域 30°E–130°E × 10°S–40°N = 100°×50°
    # = 0.25°网格 400×201 = 80400 点 × 8760 小时 × 4 变量 × 4 bytes (float32)
    # ≈ 11.3 GB（未压缩），实测 NC 文件 4.21 GB（有压缩）
    n_vars = len(variables)
    n_years = len(years)
    # 单年单变量压缩后约 1 GB
    return n_years * n_vars * 1.0  # 粗略


def parse_year_arg(s):
    """支持 --years 2021 2022 2023 或 --years 2023-2025"""
    years = []
    for tok in s:
        if '-' in tok:
            a, b = tok.split('-')
            years.extend(range(int(a), int(b) + 1))
        else:
            years.append(int(tok))
    return sorted(set(years))


def main():
    ap = argparse.ArgumentParser(description='ERA5 CDS API 批量下载')
    ap.add_argument('--years', nargs='+', default=None,
                    help='年份列表，如 "2021 2022 2023" 或 "2023-2025"')
    ap.add_argument('--months', nargs='+', type=int, default=None,
                    help='月份列表（1-12），不指定则全年')
    ap.add_argument('--vars', nargs='+', default=DEFAULT_VARS,
                    help=f'变量列表，默认 {DEFAULT_VARS}')
    ap.add_argument('--lat', nargs=2, type=float, default=DEFAULT_LAT_RANGE,
                    metavar=('NORTH', 'SOUTH'),
                    help='纬度范围，北→南，如 "40 -10"')
    ap.add_argument('--lon', nargs=2, type=float, default=DEFAULT_LON_RANGE,
                    metavar=('WEST', 'EAST'),
                    help='经度范围，西→东，如 "30 130"')
    ap.add_argument('--dry-run', action='store_true',
                    help='只打印请求体不提交')
    ap.add_argument('--dataset', default='reanalysis-era5-single-levels',
                    help='ERA5 数据集名')
    args = ap.parse_args()

    years = parse_year_arg(args.years) if args.years else DEFAULT_YEARS
    months = args.months if args.months else DEFAULT_MONTHS

    print('=' * 70)
    print('ERA5 CDS API 批量下载')
    print('=' * 70)
    print(f'年份: {years}')
    print(f'月份: {months if len(months) < 12 else "全年"}')
    print(f'变量: {args.vars}')
    print(f'区域: N{args.lat[0]}→S{args.lat[1]}, W{args.lon[0]}→E{args.lon[1]}')
    print(f'数据集: {args.dataset}')
    print(f'输出目录: {DATA_DIR}')

    size_est = estimate_size_mb(years, args.vars, args.lat, args.lon)
    print(f'预估下载大小: ~{size_est:.1f} GB（有压缩）')
    print()

    # ---------- 生成请求预览 ----------
    os.makedirs(DATA_DIR, exist_ok=True)
    requests_to_submit = []
    for y in years:
        req = build_request(y, months, args.vars, args.lat, args.lon)
        out = os.path.join(DATA_DIR, f'era5_{y}.nc')
        if os.path.exists(out):
            print(f'  [SKIP] {out} 已存在，跳过')
            continue
        requests_to_submit.append((y, req, out))

    if not requests_to_submit:
        print('所有年份文件已存在，无需下载')
        return

    print(f'待提交请求: {len(requests_to_submit)} 个')
    print()
    print('=== 第一个请求体预览 ===')
    y, req, out = requests_to_submit[0]
    print(f'年份 {y}:')
    print(json.dumps(req, indent=2, ensure_ascii=False)[:1500])
    print('...')
    print()

    if args.dry_run:
        print('[DRY-RUN] 不提交，退出')
        return

    # ---------- 提交 ----------
    print('开始提交请求（CDS 排队处理，单请求可能 10-60 分钟）')
    print('可在浏览器打开 https://cds.climate.copernicus.eu/cdsapp#!/yourrequests 查看')
    print()
    summary = []
    for i, (y, req, out) in enumerate(requests_to_submit, 1):
        print(f'[{i}/{len(requests_to_submit)}] 年份 {y}')
        ok = submit_and_wait(req, out, args.dataset)
        summary.append((y, 'OK' if ok else 'ERR'))
        if ok and os.path.exists(out):
            sz = os.path.getsize(out) / 1024 / 1024
            print(f'  文件大小: {sz:.1f} MB')

    print()
    print('=== 汇总 ===')
    for y, s in summary:
        print(f'  {y}: {s}')

    # 写元数据 JSON
    meta = {
        'dataset': args.dataset,
        'years': years,
        'months': months,
        'variables': args.vars,
        'area': [args.lat[0], args.lon[0], args.lat[1], args.lon[1]],
        'downloaded_files': [
            {'year': y, 'path': out, 'status': s}
            for y, s in summary
        ],
    }
    meta_path = os.path.join(DATA_DIR, 'era5_batch_metadata.json')
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f'元数据写入: {meta_path}')


if __name__ == '__main__':
    main()
