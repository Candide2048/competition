# -*- coding: utf-8 -*-
"""WASP 仪表盘设计系统 —— Clean Cleantech（bound4blue 风 · 亮色简约高级）

集中定义配色 tokens、字体、注入式全局 CSS、以及一组返回 HTML 字符串的
自定义组件函数（供 st.markdown(..., unsafe_allow_html=True) 渲染）。

设计取向（提炼自 impeccable/distill · ui-ux-pro-max 低 variance 档 ·
awesome-design-md 的 tesla/spacex/linear/stripe tokens · react-bits 克制动效）:
    - 纯白底 + 深 navy 文本 + 单一 teal 强调，克制到「强调色只用于一个数」
    - 陈述先行：超大粗体结论 + 超大统计数字（Space Grotesk / tabular-nums）
    - 慷慨留白、扁平、去发光重边框；层次靠间距与字重，不靠装饰
    - 入场动效克制：分区淡入上移 + KPI 数字揭示（尊重 prefers-reduced-motion）

无 Streamlit 强依赖（inject_css/组件返回 HTML；plotly_layout 返回 dict），可独立单测。
"""

# ═══════════════════════════════════════════════════════════
# 配色 tokens — Clean Cleantech（亮色）
# ═══════════════════════════════════════════════════════════
PALETTE = {
    "bg": "#FFFFFF",          # 纯白背景
    "panel": "#F4F7FA",       # 浅蓝灰分区/侧栏底
    "card": "#FFFFFF",        # 卡片白
    "border": "#E4EBF1",      # 发丝级边框 / 分隔线
    "sidebar": "#F5F8FB",     # 侧边栏底
    "accent": "#12A594",      # 主强调（teal）
    "accent2": "#0B6E7A",     # 次强调（深 teal）
    "pos": "#0E9F6E",         # 正向 / 节省
    "warn": "#B7791F",        # 警示（深琥珀，亮底更高级）
    "neg": "#D64545",         # 负向（柔和红）
    "text": "#0A2540",        # 文本主（深 navy）
    "muted": "#5B6B7B",       # 文本弱
}

# CII 评级色（A 最优 → E 最差，亮底可读）
CII_COLORS = {
    "A": "#0E9F6E",
    "B": "#4BB543",
    "C": "#D9A400",
    "D": "#E8770C",
    "E": "#D64545",
}

# 语义 → 数值着色
_SEMANTIC = {
    "pos": PALETTE["pos"],
    "neg": PALETTE["neg"],
    "warn": PALETTE["warn"],
    "accent": PALETTE["accent"],
    "neutral": PALETTE["text"],
}

# ═══════════════════════════════════════════════════════════
# pydeck 常量（亮色地图 + teal 航路）
# ═══════════════════════════════════════════════════════════
PYDECK_MAP_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
PATH_COLOR_RGBA = [18, 165, 148, 235]    # teal 航路
POINT_COLOR_RGBA = [10, 37, 64, 235]     # navy 航路点


def _esc(v) -> str:
    """极简 HTML 转义（组件内联文本用）"""
    return (str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ═══════════════════════════════════════════════════════════
# 全局 CSS 注入
# ═══════════════════════════════════════════════════════════
def inject_css() -> str:
    """返回全局 <style>（字体 @import + 组件样式 + 克制入场动效）

    返回字符串供 st.markdown(inject_css(), unsafe_allow_html=True) 注入。
    """
    p = PALETTE
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&family=Noto+Sans+SC:wght@400;500;700&display=swap');

:root {{
  --wasp-bg: {p['bg']};
  --wasp-panel: {p['panel']};
  --wasp-card: {p['card']};
  --wasp-border: {p['border']};
  --wasp-accent: {p['accent']};
  --wasp-accent2: {p['accent2']};
  --wasp-text: {p['text']};
  --wasp-muted: {p['muted']};
}}

html, body, [class*="css"], .stApp {{
  font-family: 'Inter', 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}}
.stApp {{ background: {p['bg']}; color: {p['text']}; }}

/* 慷慨留白：主区块更宽的上下呼吸感 */
.block-container {{ padding-top: 2.6rem; padding-bottom: 4rem; max-width: 1180px; }}

/* 标题：深 navy、粗、陈述性 */
h1, h2, h3, h4, h5, h6 {{ color: {p['text']}; letter-spacing: -.01em; }}
.stApp p, .stApp li, .stApp span, .stApp label {{ color: {p['text']}; }}
.stApp .stCaption, .stApp small {{ color: {p['muted']}; }}

/* 侧边栏：浅底 + 右侧发丝分隔 */
section[data-testid="stSidebar"] > div {{
  background: {p['sidebar']}; border-right: 1px solid {p['border']};
}}
section[data-testid="stSidebar"] .stSlider [role="slider"] {{ background: {p['accent']}; }}
section[data-testid="stSidebar"] h1 {{ font-size: 20px; }}

/* Tab 栏：极简，选中 navy + teal 下划线 */
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {p['border']}; }}
.stTabs [data-baseweb="tab"] {{
  color: {p['muted']}; background: transparent; font-weight: 600;
  padding: 8px 16px; border-radius: 8px 8px 0 0;
}}
.stTabs [aria-selected="true"] {{
  color: {p['text']} !important;
  border-bottom: 2px solid {p['accent']};
}}

/* 克制入场动效（分区淡入上移 / 数字揭示）*/
@keyframes waspFadeUp {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
@keyframes waspReveal {{ from {{ opacity: 0; transform: translateY(6px); filter: blur(4px); }} to {{ opacity: 1; transform: translateY(0); filter: blur(0); }} }}

/* Hero 结论条：白卡 + 左 teal 细线，超大陈述性排版 */
.wasp-hero {{
  position: relative; border-radius: 16px; padding: 30px 34px 28px 38px;
  background: {p['card']}; border: 1px solid {p['border']};
  box-shadow: 0 1px 2px rgba(10,37,64,.04); margin-bottom: 26px; overflow: hidden;
  animation: waspFadeUp .5s ease-out both;
}}
.wasp-hero::before {{
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
  background: {p['accent']};
}}
.wasp-hero .eyebrow {{
  font-size: 12px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase;
  color: {p['accent']}; margin-bottom: 12px;
}}
.wasp-hero .verdict {{
  font-size: 30px; font-weight: 700; line-height: 1.38; color: {p['text']};
  letter-spacing: -.015em;
}}
.wasp-hero .verdict b {{
  color: {p['accent2']}; font-family: 'Space Grotesk', sans-serif; font-weight: 700;
  font-variant-numeric: tabular-nums;
}}
.wasp-hero .chips {{ margin-top: 20px; display: flex; flex-wrap: wrap; gap: 8px; }}
.wasp-chip {{
  font-size: 12px; font-weight: 600; color: {p['muted']};
  background: {p['panel']}; border: 1px solid {p['border']};
  border-radius: 999px; padding: 5px 13px;
}}
.wasp-chip.tag-live {{ color: {p['warn']}; border-color: rgba(183,121,31,.35); background: rgba(183,121,31,.06); }}
.wasp-chip.tag-grid {{ color: {p['pos']}; border-color: rgba(14,159,110,.35); background: rgba(14,159,110,.06); }}

/* KPI 卡片：白卡 + 发丝边框，超大数字，入场淡入（分级 stagger）*/
.wasp-kpi {{
  background: {p['card']}; border: 1px solid {p['border']}; border-radius: 16px;
  padding: 22px 24px; height: 100%;
  transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease;
  animation: waspFadeUp .5s ease-out both;
}}
.wasp-kpi:hover {{
  border-color: {p['accent']};
  box-shadow: 0 6px 20px rgba(10,37,64,.07); transform: translateY(-2px);
}}
.wasp-kpi .label {{
  font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
  color: {p['muted']}; margin-bottom: 14px;
}}
.wasp-kpi .value {{
  font-family: 'Space Grotesk', sans-serif; font-weight: 700;
  font-size: clamp(22px, 3.4vw, 38px); line-height: 1.05; white-space: nowrap;
  font-variant-numeric: tabular-nums; letter-spacing: -.02em;
  animation: waspReveal .7s ease-out both;
}}
.wasp-kpi .delta {{
  display: inline-block; margin-top: 14px; font-size: 12px; font-weight: 600;
  border-radius: 999px; padding: 4px 11px;
  background: rgba(18,165,148,.09); color: {p['accent2']};
}}
.wasp-kpi .foot {{ margin-top: 10px; font-size: 12px; color: {p['muted']}; }}

/* CII badge */
.wasp-cii {{ display: flex; align-items: center; gap: 12px; margin-top: 4px; }}
.wasp-cii .pill {{
  font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 24px;
  width: 46px; height: 46px; display: flex; align-items: center; justify-content: center;
  border-radius: 12px; color: #FFFFFF;
}}
.wasp-cii .arrow {{ color: {p['muted']}; font-size: 22px; }}

/* benchmark 对照条：浅轨 + teal 带 + navy 标记 */
.wasp-bench {{ margin: 8px 0 2px; }}
.wasp-bench .track {{
  position: relative; height: 10px; border-radius: 6px;
  background: {p['panel']}; border: 1px solid {p['border']};
}}
.wasp-bench .band {{
  position: absolute; top: 0; bottom: 0; border-radius: 6px;
  background: rgba(18,165,148,.24);
}}
.wasp-bench .marker {{
  position: absolute; top: -3px; width: 3px; height: 16px; border-radius: 2px;
  background: {p['text']};
}}
.wasp-bench .cap {{ font-size: 12px; color: {p['muted']}; margin-top: 8px; }}
.wasp-bench .cap b {{ color: {p['accent2']}; font-variant-numeric: tabular-nums; }}

/* 尊重减少动效偏好 */
@media (prefers-reduced-motion: reduce) {{
  .wasp-hero, .wasp-kpi, .wasp-kpi .value {{ animation: none !important; }}
}}
</style>
"""


# ═══════════════════════════════════════════════════════════
# 组件：Hero 结论条
# ═══════════════════════════════════════════════════════════
def verdict_hero(verdict_html: str, chips: list[tuple[str, str]] | None = None,
                 eyebrow: str = "WASP 风帆辅助推进 · 效益结论") -> str:
    """全宽结论条（白卡 + 左 teal 细线，超大陈述性排版）

    Args:
        verdict_html: 一句话结论（允许内嵌 <b> 高亮数值）
        chips: [(label, kind)]，kind ∈ {"", "live", "grid"}
        eyebrow: 顶部小标签
    """
    chip_html = ""
    if chips:
        items = []
        for label, kind in chips:
            cls = f"wasp-chip tag-{kind}" if kind in ("live", "grid") else "wasp-chip"
            items.append(f'<span class="{cls}">{_esc(label)}</span>')
        chip_html = f'<div class="chips">{"".join(items)}</div>'
    return (
        f'<div class="wasp-hero">'
        f'<div class="eyebrow">{_esc(eyebrow)}</div>'
        f'<div class="verdict">{verdict_html}</div>'
        f'{chip_html}</div>'
    )


# ═══════════════════════════════════════════════════════════
# 组件：KPI 卡片
# ═══════════════════════════════════════════════════════════
def kpi_card(label: str, value: str, delta: str | None = None,
             foot: str | None = None, semantic: str = "neutral",
             delay: float = 0.0) -> str:
    """语义着色 KPI 卡片（超大数字 + 数字揭示动效）

    Args:
        label:    弱色大写标签
        value:    大数（Space Grotesk / tabular-nums）
        delta:    圆角 pill（None 不显示）
        foot:     弱色脚注（None 不显示）
        semantic: 数值着色 pos/neg/warn/accent/neutral
        delay:    入场动效延迟（秒），用于 KPI 带的分级 stagger
    """
    color = _SEMANTIC.get(semantic, PALETTE["text"])
    delta_html = f'<div class="delta">{_esc(delta)}</div>' if delta else ""
    foot_html = f'<div class="foot">{_esc(foot)}</div>' if foot else ""
    # 卡片与数字的入场延迟（stagger），揭示动效比卡片略晚
    card_style = f' style="animation-delay:{delay:.2f}s"' if delay else ""
    val_style = f'animation-delay:{delay + 0.08:.2f}s;' if delay else ""
    return (
        f'<div class="wasp-kpi"{card_style}>'
        f'<div class="label">{_esc(label)}</div>'
        f'<div class="value" style="color:{color};{val_style}">{_esc(value)}</div>'
        f'{delta_html}{foot_html}</div>'
    )


# ═══════════════════════════════════════════════════════════
# 组件：CII 评级跃迁 badge
# ═══════════════════════════════════════════════════════════
def cii_badge(before: str, after: str) -> str:
    """彩色字母 pill，before → after 箭头跃迁"""
    cb = CII_COLORS.get(before, PALETTE["muted"])
    ca = CII_COLORS.get(after, PALETTE["muted"])
    return (
        f'<div class="wasp-cii">'
        f'<span class="pill" style="background:{cb}">{_esc(before)}</span>'
        f'<span class="arrow">→</span>'
        f'<span class="pill" style="background:{ca}">{_esc(after)}</span>'
        f'</div>'
    )


# ═══════════════════════════════════════════════════════════
# 组件：benchmark 对照条
# ═══════════════════════════════════════════════════════════
def benchmark_bar(value: float, lo: float, hi: float, refs: str = "") -> str:
    """本场景值 vs 实船报道区间（min-max 带）横条

    Args:
        value: 本场景值（%）
        lo/hi: 实船报道区间下/上界（%）
        refs:  区间来源说明
    """
    axis_hi = max(hi, value) * 1.15 + 1e-9
    band_l = max(0.0, lo) / axis_hi * 100.0
    band_w = max(0.0, (hi - lo)) / axis_hi * 100.0
    mark = min(100.0, max(0.0, value / axis_hi * 100.0))
    cap = (f'本场景 <b>{value:.2f}%</b>　实船报道区间 {lo:.0f}–{hi:.0f}%'
           + (f'　·　{_esc(refs)}' if refs else ''))
    return (
        f'<div class="wasp-bench">'
        f'<div class="track">'
        f'<div class="band" style="left:{band_l:.1f}%;width:{band_w:.1f}%"></div>'
        f'<div class="marker" style="left:{mark:.1f}%"></div>'
        f'</div>'
        f'<div class="cap">{cap}</div>'
        f'</div>'
    )


# ═══════════════════════════════════════════════════════════
# Plotly 亮色主题
# ═══════════════════════════════════════════════════════════
def plotly_layout() -> dict:
    """统一 Plotly 亮色 layout（透明底 / Inter / 浅网格 / teal 色序）"""
    p = PALETTE
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Noto Sans SC, sans-serif", color=p["text"], size=13),
        xaxis=dict(gridcolor=p["border"], zerolinecolor=p["border"]),
        yaxis=dict(gridcolor=p["border"], zerolinecolor=p["border"]),
        colorway=[p["accent"], p["accent2"], p["pos"], p["warn"], p["neg"]],
        margin=dict(l=10, r=10, t=30, b=10),
    )


# 向后兼容别名（旧调用点 plotly_dark_layout → 亮色 layout）
plotly_dark_layout = plotly_layout


# 热力图自定义色阶（浅 → teal 深）
HEATMAP_COLORSCALE = [
    [0.0, "#EAF3F4"],
    [0.5, "#7FC9C2"],
    [1.0, "#0B6E7A"],
]
