# -*- coding: utf-8 -*-
"""WASP 交互仪表盘 — Streamlit 单页应用

运行:
    streamlit run code/app/dashboard.py

架构（计算分层）:
    物理层（船型×航速×航线×季节×帆型，ERA5 逐小时积分）由 precompute_grid.py
    离线预计算成 physics_grid.json，本应用以 @st.cache_data 秒级加载；经济性 /
    CII 后处理为纯算术，随左侧滑杆实时重算。第②层实船几何覆盖 / 非标准航速则
    走 @st.cache_data 包裹的 live 物理重算（首次几秒、重复命中缓存瞬时）。

布局:
    左侧 st.sidebar 输入栏（映射 OwnerInputs 两层模型）
    右侧 4 个 st.tabs：指标卡 / 航线地图 / 效益矩阵热力图 / 自动分析报告
"""
import os
import sys
import json

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import pydeck as pdk

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from core.owner_inputs import (
    VALID_SHIP_TYPES, VALID_SAIL_TYPES, VALID_FLETTNER_SPECS,
    VALID_FUEL_TYPES,
)
import app.data_access as da
import app.theme as theme
from app.report import (
    generate_report, SAIL_LABELS, SHIP_LABELS, SEASON_LABELS,
)

st.set_page_config(page_title="WASP 风帆辅助推进效益仪表盘",
                   page_icon="⛵", layout="wide")

# 注入全局深色主题 CSS（字体 + 组件样式）
st.markdown(theme.inject_css(), unsafe_allow_html=True)

SPEED_TOL = 1e-6

# 帆型实船报道节油率区间（%，用于 benchmark_bar 对照）
SAIL_BENCH_RANGE = {
    "flettner": (6.0, 8.2, "Norsepower Estraden 6.1% / Pelican 8.2%"),
    "rigid_wing": (7.0, 14.0, "Oceanbird 7-10% / Pyxis Ocean ~14% (DNV)"),
    "suction_wing": (5.5, 8.0, "bound4blue Pacific Sentinel ~8%"),
}


# ═══════════════════════════════════════════════════════════
# 缓存包裹
# ═══════════════════════════════════════════════════════════

@st.cache_data(show_spinner="加载物理层预计算网格...")
def cached_load_grid():
    """加载 physics_grid.json（进程内一次）"""
    return da.load_grid()


@st.cache_data(show_spinner="首次运行该实船/非标准航速场景，逐小时 ERA5 积分中（约数秒）...")
def cached_run_single(ship, speed_kn, route, season, sail,
                      flettner_spec, sfoc_g_per_kwh, overrides_key):
    """第②层 live 物理重算（按参数缓存，重复命中瞬时）

    overrides_key: ship_overrides 的 JSON 串（保证可哈希）
    """
    overrides = json.loads(overrides_key) if overrides_key else None
    return da.run_single_scenario(
        ship=ship, speed_kn=speed_kn, route=route, season=season, sail=sail,
        flettner_spec=flettner_spec, sfoc_g_per_kwh=sfoc_g_per_kwh,
        ship_overrides=overrides,
    )


# ═══════════════════════════════════════════════════════════
# 加载网格（失败则给出提示）
# ═══════════════════════════════════════════════════════════

try:
    META, DF = cached_load_grid()
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()

GRID_SPEEDS = [float(s) for s in META["speeds_kn"]]
SAIL_INSTALL = META["sail_install"]
ROUTES_META = META["routes"]
SEASONS_META = META["seasons"]
SHIP_META = META["ship_meta"]


# ═══════════════════════════════════════════════════════════
# 侧边栏输入（映射 OwnerInputs 两层模型）
# ═══════════════════════════════════════════════════════════

st.sidebar.title("⛵ 输入参数")

# —— ① 船型（必填单选）——
ship = st.sidebar.selectbox(
    "船型",
    options=[s for s in VALID_SHIP_TYPES if s in SHIP_META],
    format_func=lambda s: SHIP_LABELS.get(s, s),
    help="第①层必填：决定几何/水动力/CII 参考线",
)

# —— ② 实船参数覆盖（高级，可选）——
with st.sidebar.expander("▸ 实船参数（高级，可选）"):
    use_override = st.checkbox("启用实船几何覆盖", value=False,
                               help="填写实船主尺度以覆盖代表船；触发 live 物理重算")
    smeta = SHIP_META[ship]
    ov_dwt = st.number_input("DWT (t)", value=float(smeta["DWT"]),
                             min_value=1000.0, step=1000.0, disabled=not use_override)
    ov_L = st.number_input("垂线间长 L (m)", value=float(smeta["L"]),
                           min_value=10.0, step=1.0, disabled=not use_override)
    ov_B = st.number_input("型宽 B (m)", value=float(smeta["B"]),
                           min_value=1.0, step=0.5, disabled=not use_override)
    ov_T = st.number_input("吃水 draft (m)", value=float(smeta["T"]),
                           min_value=0.5, step=0.2, disabled=not use_override)
    ov_CB = st.number_input("方形系数 C_B", value=float(smeta["C_B"]),
                            min_value=0.3, max_value=0.99, step=0.01,
                            disabled=not use_override)
    sfoc = st.number_input("主机比油耗 SFOC (g/kWh)", value=180.0,
                           min_value=140.0, max_value=220.0, step=1.0,
                           help="标准 180；改动将触发 live 重算")

# —— 航速 ——
speed = st.sidebar.slider("航速 (kn)", min_value=8.0, max_value=18.0,
                          value=14.0, step=0.5,
                          help=f"标准集 {GRID_SPEEDS} 秒级取数；其它航速触发 live 重算")

# —— ③ 帆型 ——
sail = st.sidebar.radio(
    "风帆技术类型",
    options=list(VALID_SAIL_TYPES),
    format_func=lambda s: SAIL_LABELS.get(s, s),
    horizontal=True,
)
flettner_spec = "24x4"
if sail == "flettner":
    flettner_spec = st.sidebar.selectbox(
        "Flettner 规格 (H×D)", options=list(VALID_FLETTNER_SPECS), index=1)
n_sails = SAIL_INSTALL[sail]
st.sidebar.caption(f"安装台数：{n_sails} 台（等面积归一化，用于公平对比）")

# —— ④ 航线 / 季节 ——
route = st.sidebar.selectbox(
    "航线", options=list(ROUTES_META.keys()),
    format_func=lambda r: ROUTES_META[r]["name"])
season = st.sidebar.selectbox(
    "季节", options=list(SEASONS_META.keys()),
    format_func=lambda s: SEASON_LABELS.get(s, s))

# —— ⑤ 经济性滑杆 ——
st.sidebar.subheader("经济性参数")
fuel_type = st.sidebar.selectbox("燃料类型", options=list(VALID_FUEL_TYPES), index=0)
fuel_price = st.sidebar.slider("燃油价 (USD/kg)", 0.30, 1.00, 0.60, 0.01)
co2_price = st.sidebar.slider("碳价 (EUR/tCO₂)", 0.0, 150.0, 74.0, 1.0)
default_unit_cost = da.resolve_unit_cost(sail, flettner_spec)
unit_cost = st.sidebar.number_input(
    "单台成本 (USD)", value=float(default_unit_cost),
    min_value=100000.0, step=50000.0)
sea_ratio = st.sidebar.slider("海上作业时间比例", 0.40, 0.95, 0.742, 0.001,
                              help="年航行小时 / 8765，用于换算年航次数")


# ═══════════════════════════════════════════════════════════
# 计算：判定 live vs 网格取数，再做经济性后处理
# ═══════════════════════════════════════════════════════════

overrides = None
if use_override:
    overrides = {"DWT": ov_dwt, "L": ov_L, "B": ov_B,
                 "draft": ov_T, "C_B": ov_CB}

speed_in_grid = any(abs(speed - g) < SPEED_TOL for g in GRID_SPEEDS)
is_live = bool(overrides) or (not speed_in_grid) or abs(sfoc - 180.0) > SPEED_TOL

if is_live:
    row = cached_run_single(
        ship, float(speed), route, season, sail,
        flettner_spec, float(sfoc),
        json.dumps(overrides, sort_keys=True) if overrides else "")
    ship_meta_for_pp = {"DWT": row["dwt"], "ship_type_imo": row["ship_type_imo"],
                        "GT": row.get("GT")}
    speed_used, speed_exact = float(speed), True
else:
    row = da.pick_physics(DF, ship, float(speed), route, season, sail)
    ship_meta_for_pp = SHIP_META[ship]
    speed_used, speed_exact = row["speed_used"], row["speed_exact"]

cell = da.postprocess(
    row, ship=ship, sail=sail, sea_operating_ratio=sea_ratio,
    unit_cost_usd=unit_cost, flettner_spec=flettner_spec,
    fuel_type=fuel_type, fuel_price_usd_per_kg=fuel_price,
    co2_price_eur_per_t=co2_price, ship_meta=ship_meta_for_pp)

route_name = ROUTES_META[route]["name"]


# ═══════════════════════════════════════════════════════════
# 主区
# ═══════════════════════════════════════════════════════════

trips = sea_ratio * 8765.0 / float(row["duration_h"])
_payback_txt = "不可回收" if cell["payback_years"] is None else f"{cell['payback_years']:.1f} 年"
_verdict = (
    f"为 {SHIP_LABELS.get(ship, ship)} 加装 <b>{n_sails}</b> 台{SAIL_LABELS.get(sail, sail)}："
    f"节油 <b>{cell['saving_rate_pct']:.2f}%</b> · "
    f"CII <b>{cell['cii_rating_baseline']}→{cell['cii_rating_with_sail']}</b> · "
    f"回收 <b>{_payback_txt}</b>"
)
_mode_chip = ("实时物理重算 (live)", "live") if is_live else ("预计算网格 (缓存)", "grid")
_chips = [
    (route_name, ""),
    (SEASON_LABELS.get(season, season), ""),
    (f"{speed_used:.0f} kn", ""),
    _mode_chip,
]
st.markdown(theme.verdict_hero(_verdict, _chips), unsafe_allow_html=True)

# 帆型-船型兼容性警告
if cell.get("compatible") is False:
    st.error("⚠️ 该帆型与当前船型不兼容，计算结果仅供参考。")
elif cell.get("compatibility", 1.0) < 1.0:
    _pct = cell["compatibility"] * 100
    st.warning(f"ℹ️ 该帆型与当前船型有条件兼容（{_pct:.0f}%），效益已按比例折减。")

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 效益指标", "🗺️ 航线地图", "🔥 效益矩阵", "📄 分析报告"])


# —— Tab1：指标卡 ——
with tab1:
    if not speed_exact:
        st.info(f"航速 {speed:.1f} kn 不在标准集，已取最近邻 {speed_used:.0f} kn 网格值。")

    # KPI 卡片带（6 卡，分级 stagger 淡入）
    r1 = st.columns(3)
    r1[0].markdown(theme.kpi_card(
        "节油率", f"{cell['saving_rate_pct']:.2f}%", semantic="pos",
        foot=f"单航次节油 {cell['fuel_saved_t']:.1f} t", delay=0.00), unsafe_allow_html=True)
    r1[1].markdown(theme.kpi_card(
        "单航次 CO₂ 减排", f"{cell['co2_reduced_t']:.1f} t", semantic="accent",
        foot=f"排放因子口径", delay=0.06), unsafe_allow_html=True)
    r1[2].markdown(theme.kpi_card(
        "年净节省", f"${cell['annual_savings_usd']:,.0f}", semantic="pos",
        delta=f"{trips:.1f} 航次/年", delay=0.12), unsafe_allow_html=True)

    r2 = st.columns(3)
    _pb_semantic = "neg" if cell["payback_years"] is None else (
        "pos" if cell["payback_years"] <= 8 else "warn")
    r2[0].markdown(theme.kpi_card(
        "投资回收期", _payback_txt, semantic=_pb_semantic,
        foot=f"初始投资 ${cell['initial_cost_usd']:,.0f}", delay=0.18), unsafe_allow_html=True)
    r2[1].markdown(theme.kpi_card(
        "10 年 NPV", f"${cell['npv_10y_usd']:,.0f}",
        semantic="pos" if cell["npv_10y_usd"] >= 0 else "neg", delay=0.24), unsafe_allow_html=True)
    r2[2].markdown(theme.kpi_card(
        "20 年 NPV", f"${cell['npv_20y_usd']:,.0f}",
        semantic="pos" if cell["npv_20y_usd"] >= 0 else "neg", delay=0.30), unsafe_allow_html=True)

    st.divider()

    cL, cR = st.columns([1, 1.4])
    with cL:
        st.markdown("###### CII 评级跃迁")
        st.markdown(theme.cii_badge(cell["cii_rating_baseline"],
                                    cell["cii_rating_with_sail"]),
                    unsafe_allow_html=True)
        st.caption(f"改善 {cell['cii_improvement_pct']:.1f}%"
                   f"（{SHIP_LABELS.get(ship, ship)}"
                   f"{'，GT 容量基数' if ship == 'pctc' else ''}）")
    with cR:
        st.markdown(f"###### 实船报道区间对照（{SAIL_LABELS.get(sail, sail)}）")
        lo, hi, refs = SAIL_BENCH_RANGE.get(sail, (0.0, 10.0, ""))
        st.markdown(theme.benchmark_bar(cell["saving_rate_pct"], lo, hi, refs),
                    unsafe_allow_html=True)


# —— Tab2：航线地图 ——
with tab2:
    wps = ROUTES_META[route]["waypoints"]  # [[lat, lon], ...]
    path_coords = [[lon, lat] for lat, lon in wps]  # pydeck 用 [lon, lat]
    pts = pd.DataFrame(
        {"lat": [w[0] for w in wps], "lon": [w[1] for w in wps],
         "idx": list(range(len(wps)))})

    path_layer = pdk.Layer(
        "PathLayer",
        data=[{"path": path_coords}],
        get_path="path", get_width=5, width_min_pixels=3,
        get_color=theme.PATH_COLOR_RGBA)
    point_layer = pdk.Layer(
        "ScatterplotLayer", data=pts,
        get_position="[lon, lat]", get_radius=16000,
        get_fill_color=theme.POINT_COLOR_RGBA, pickable=True)
    mid_lat = float(np.mean([w[0] for w in wps]))
    mid_lon = float(np.mean([w[1] for w in wps]))
    view = pdk.ViewState(latitude=mid_lat, longitude=mid_lon, zoom=3.2, pitch=0)
    st.pydeck_chart(pdk.Deck(
        layers=[path_layer, point_layer], initial_view_state=view,
        map_style=theme.PYDECK_MAP_STYLE,
        tooltip={"text": "航路点 {idx}\nlat {lat} lon {lon}"}))
    st.caption(f"航线 **{route_name}**：{row['distance_nm']:,.0f} nm，"
               f"单程约 {row['duration_h']:.0f} h，"
               f"平均风速 {row['mean_wind_ms']:.1f} m/s（{SEASON_LABELS.get(season, season)}）。")


# —— Tab3：效益矩阵热力图 ——
with tab3:
    st.markdown(f"**{SAIL_LABELS.get(sail, sail)}** 节油率热力图（航线 × 季节）")
    # 取当前船型、当前帆型、最近网格航速
    grid_speed = min(GRID_SPEEDS, key=lambda g: abs(g - speed))
    sub = DF[(DF["ship"] == ship) & (DF["sail"] == sail)
             & (np.abs(DF["speed_kn"] - grid_speed) < SPEED_TOL)]
    if sub.empty:
        st.warning("该组合在预计算网格中无数据。")
    else:
        piv = sub.pivot_table(index="route", columns="season",
                              values="saving_rate_pct")
        # 排序季节与航线为可读顺序
        season_order = [s for s in SEASONS_META if s in piv.columns]
        route_order = [r for r in ROUTES_META if r in piv.index]
        piv = piv.reindex(index=route_order, columns=season_order)
        fig = px.imshow(
            piv.values,
            x=[SEASON_LABELS.get(s, s) for s in season_order],
            y=[ROUTES_META[r]["name"] for r in route_order],
            color_continuous_scale=theme.HEATMAP_COLORSCALE, aspect="auto",
            labels=dict(color="节油率 %"), text_auto=".1f")
        fig.update_layout(height=420, **theme.plotly_layout())
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=False)
        st.plotly_chart(fig, width="stretch")
        st.caption(f"航速 {grid_speed:.0f} kn（网格标准值）。颜色越深节油率越高，"
                   "可见强季风区段（阿拉伯海/南海）节油率显著高于弱风区。")


# —— Tab4：自动分析报告 ——
with tab4:
    report_md = generate_report(
        ship=ship, sail=sail, route=route, route_name=route_name,
        season=season, speed_used=speed_used, speed_exact=speed_exact,
        physics=row, cell=cell, sea_operating_ratio=sea_ratio,
        fuel_type=fuel_type, fuel_price=fuel_price, co2_price=co2_price,
        unit_cost_usd=unit_cost, n_sails=n_sails,
        flettner_spec=flettner_spec if sail == "flettner" else None,
        is_live=is_live, ship_overrides=overrides)
    st.markdown(report_md)
    st.download_button(
        "⬇️ 下载报告 (Markdown)", data=report_md,
        file_name=f"WASP_报告_{ship}_{sail}_{route}_{season}.md",
        mime="text/markdown")
