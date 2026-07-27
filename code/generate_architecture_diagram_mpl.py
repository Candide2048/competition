# -*- coding: utf-8 -*-
"""Generate the WASP architecture diagram using matplotlib (native PNG/PDF/SVG).

Style: lightweight blueprint — white background, thin precise lines,
restrained blue-gray palette, compact information density.
Portrait orientation, 2:3 aspect ratio.

Outputs:
    shipping_wasp/results/fig_architecture_diagram_mpl.png
    shipping_wasp/results/fig_architecture_diagram_mpl.pdf
    shipping_wasp/results/fig_architecture_diagram_mpl.svg

Usage:
    cd shipping_wasp/code
    python generate_architecture_diagram_mpl.py
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, Circle, Rectangle, FancyBboxPatch
import matplotlib.font_manager as fm

# ---------- Palette ----------
NAVY       = "#2C3E50"
TEAL       = "#00897B"
GRAY       = "#78909C"
WHITE      = "#FFFFFF"
FILL       = "#F5F7FA"
GRAY_LIGHT = "#CFD8DC"
TEXT_DARK  = "#333333"
TEXT_MED   = "#666666"
TEXT_SPEC  = "#555555"
ROTATED    = "#546E7A"

# ---------- Canvas (2:3 portrait) ----------
W, H = 10, 15  # inches → at 150 dpi = 1500 × 2250 px

# ---------- Layout coordinates (in data units = inches) ----------
LEFT   = 0.5
RIGHT  = 8.9
CW     = RIGHT - LEFT
BAR_X  = 9.15
BAR_W  = 0.30

T1_Y, T1_H = 0.5, 2.7
T2_Y, T2_H = 3.8, 6.0
T3_Y, T3_H = 10.4, 3.8

CENTER_X = (LEFT + RIGHT) / 2  # 4.7

# Sub-module positions
SUB_Y   = 4.4
SUB_H   = 4.4
SUB_W   = 2.4
SUB_GAP = 0.3
SUB1_X  = 0.8
SUB2_X  = SUB1_X + SUB_W + SUB_GAP
SUB3_X  = SUB2_X + SUB_W + SUB_GAP
SUB_MID_Y = SUB_Y + SUB_H / 2


def setup_figure():
    """Create figure with white background, no axes."""
    # Set CJK-capable font (Microsoft YaHei is standard on Windows)
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False  # Fix minus sign rendering

    fig, ax = plt.subplots(1, 1, figsize=(W, H), dpi=150)
    fig.patch.set_facecolor(WHITE)
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.invert_yaxis()  # Y increases downward (like screen coords)
    return fig, ax


def draw_container(ax, x, y, w, h, rx=0.06):
    """Light-gray filled container with thin navy border."""
    rect = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={rx}",
        facecolor=FILL, edgecolor=NAVY, linewidth=0.8, zorder=1,
    )
    ax.add_patch(rect)


def draw_header_tab(ax, x, y, w, h, text):
    """Teal header tab with white bold text."""
    rect = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0,rounding_size=0.04",
        facecolor=TEAL, edgecolor="none", zorder=2,
    )
    ax.add_patch(rect)
    ax.text(x + w / 2, y + h / 2, text,
            ha="center", va="center",
            fontsize=9, fontweight="bold", color=WHITE,
            fontfamily="sans-serif", zorder=3)


def draw_sub_module(ax, x, y, w, h, title, title_color, lines, border_color=None):
    """Sub-module with title and content lines."""
    if border_color is None:
        border_color = NAVY
    lw = 1.2 if border_color == TEAL else 0.8
    rect = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0,rounding_size=0.04",
        facecolor=WHITE, edgecolor=border_color, linewidth=lw, zorder=2,
    )
    ax.add_patch(rect)

    cx = x + w / 2
    # Title
    ax.text(cx, y + 0.38, title,
            ha="center", va="center",
            fontsize=11, fontweight="bold", color=title_color,
            fontfamily="sans-serif", zorder=3)
    # Separator
    ax.plot([x + 0.2, x + w - 0.2], [y + 0.55, y + 0.55],
            color=GRAY, linewidth=0.4, linestyle=(0, (3, 3)), zorder=3)
    # Content lines
    for i, (text, is_mono) in enumerate(lines):
        ly = y + 0.95 + i * 0.32
        ff = "monospace" if is_mono else "sans-serif"
        ax.text(cx, ly, text,
                ha="center", va="center",
                fontsize=8.5, color=TEXT_DARK,
                fontfamily=ff, zorder=3)


def draw_down_arrow(ax, x, y1, y2, color=NAVY, lw=1.2):
    """Vertical downward arrow with triangular head."""
    ax.annotate(
        "",
        xy=(x, y2), xytext=(x, y1),
        arrowprops=dict(
            arrowstyle="-|>",
            color=color, lw=lw,
            mutation_scale=10,
            shrinkA=0, shrinkB=0,
        ),
        zorder=4,
    )


def draw_h_arrow(ax, x1, y1, x2, y2, color=NAVY, lw=0.8):
    """Horizontal arrow with triangular head."""
    ax.annotate(
        "",
        xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle="-|>",
            color=color, lw=lw,
            mutation_scale=8,
            shrinkA=0, shrinkB=0,
        ),
        zorder=4,
    )


def draw_orthogonal_arrow(ax, points, color=NAVY, lw=0.8):
    """Multi-segment orthogonal arrow path. points = [(x1,y1), (x2,y2), ...]"""
    # Draw all segments except the last as plain lines
    for i in range(len(points) - 2):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        ax.plot([x1, x2], [y1, y2], color=color, linewidth=lw, zorder=4)
    # Last segment as arrow
    px, py = points[-2]
    ex, ey = points[-1]
    draw_h_arrow(ax, px, py, ex, ey, color=color, lw=lw)


def draw_tier1(ax):
    """Data Foundation Layer."""
    draw_container(ax, LEFT, T1_Y, CW, T1_H)
    draw_header_tab(ax, LEFT, T1_Y, 1.4, 0.32, "数据基础层")

    # Title
    ax.text(CENTER_X, T1_Y + 0.75, "ERA5 气候再分析数据引擎",
            ha="center", va="center",
            fontsize=14, fontweight="bold", color=NAVY,
            fontfamily="sans-serif", zorder=3)
    # Specs
    ax.text(CENTER_X, T1_Y + 1.10,
            "0.25° × 逐时 × 30°E–130°E  |  u10, v10, SST  |  2025全年",
            ha="center", va="center",
            fontsize=8.5, color=TEXT_SPEC,
            fontfamily="sans-serif", zorder=3)

    # Route dots
    dot_y = T1_Y + 1.65
    dot_xs = [1.3, 3.0, 4.7, 6.4, 8.1]
    ax.plot([dot_xs[0], dot_xs[-1]], [dot_y, dot_y],
            color=GRAY, linewidth=0.8, zorder=3)
    for dx in dot_xs:
        circ = Circle((dx, dot_y), 0.05, facecolor=TEAL,
                      edgecolor=NAVY, linewidth=0.4, zorder=4)
        ax.add_patch(circ)

    labels = ["中东→中国", "阿拉伯海", "孟加拉湾", "南海", "印度洋"]
    for dx, lbl in zip(dot_xs, labels):
        ax.text(dx, dot_y + 0.28, lbl,
                ha="center", va="center",
                fontsize=7.5, color=TEXT_MED,
                fontfamily="sans-serif", zorder=3)


def draw_tier2(ax):
    """Computation Core Layer."""
    draw_container(ax, LEFT, T2_Y, CW, T2_H)
    draw_header_tab(ax, LEFT, T2_Y, 1.4, 0.32, "计算核心层")

    # Three sub-modules
    draw_sub_module(ax, SUB1_X, SUB_Y, SUB_W, SUB_H,
                    "船舶阻力", NAVY,
                    [("Holtrop-Mennen (1984)", True),
                     ("5 SIMMAN 标准船型", False),
                     ("R_T = f(V, trim, sea state)", True)],
                    border_color=NAVY)

    draw_sub_module(ax, SUB2_X, SUB_Y, SUB_W, SUB_H,
                    "帆型气动力", NAVY,
                    [("Flettner: C_L(SR, α)", False),
                     ("硬质翼帆: C_L(AoA)", False),
                     ("吸力帆: polar curve", False)],
                    border_color=NAVY)

    draw_sub_module(ax, SUB3_X, SUB_Y, SUB_W, SUB_H,
                    "系统集成", TEAL,
                    [("推力平衡方程", False),
                     ("寄生功率扣除", False),
                     ("ΔP_fuel 逐时步计算", False)],
                    border_color=TEAL)

    # Converging arrows (orthogonal, navy)
    # Sub2 → Sub3: direct horizontal at mid-height
    draw_h_arrow(ax, SUB2_X + SUB_W, SUB_MID_Y,
                 SUB3_X - 0.02, SUB_MID_Y, color=NAVY)

    # Sub1 → Sub3: route below Sub2
    p_start_x = SUB1_X + SUB_W
    p_start_y = SUB_MID_Y + 1.2
    p_down_y  = SUB_Y + SUB_H + 0.3
    p_up_x    = SUB3_X - 0.15
    p_end_y   = SUB_MID_Y

    points = [
        (p_start_x, p_start_y),
        (p_start_x + 0.15, p_start_y),
        (p_start_x + 0.15, p_down_y),
        (p_up_x, p_down_y),
        (p_up_x, p_end_y),
        (SUB3_X - 0.02, p_end_y),
    ]
    draw_orthogonal_arrow(ax, points, color=NAVY)


def draw_tier3(ax):
    """Decision Analysis Layer."""
    draw_container(ax, LEFT, T3_Y, CW, T3_H)
    draw_header_tab(ax, LEFT, T3_Y, 1.4, 0.32, "决策分析层")

    rows = [
        ("节油矩阵 [%]",        "900 组情景"),
        ("CII 评级变化 [A→E]",  "MEPC.353(78) 基线"),
        ("NPV [USD]",           "燃油 + EU ETS @ €74/t"),
        ("回收期 [年]",         "CAPEX vs. 年节省额"),
    ]

    row_start_y = T3_Y + 0.70
    row_spacing = 0.70
    label_x  = LEFT + 0.70
    arrow_x1 = LEFT + 2.50
    arrow_x2 = LEFT + 4.30
    annot_x  = LEFT + 4.60

    for i, (metric, context) in enumerate(rows):
        ry = row_start_y + i * row_spacing
        ax.text(label_x, ry, metric,
                ha="left", va="center",
                fontsize=9.5, fontweight="bold", color=NAVY,
                fontfamily="sans-serif", zorder=3)
        draw_h_arrow(ax, arrow_x1, ry - 0.04, arrow_x2, ry - 0.04, color=NAVY)
        ax.text(annot_x, ry, context,
                ha="left", va="center",
                fontsize=9, color=TEXT_MED,
                fontfamily="sans-serif", zorder=3)


def draw_annotation_bar(ax):
    """Lateral annotation column on the right side."""
    bar_y = T1_Y
    bar_h = T3_Y + T3_H - T1_Y
    bar_cy = bar_y + bar_h / 2

    rect = FancyBboxPatch(
        (BAR_X, bar_y), BAR_W, bar_h,
        boxstyle="round,pad=0,rounding_size=0.03",
        facecolor=GRAY_LIGHT, edgecolor=GRAY, linewidth=0.4, zorder=1,
    )
    ax.add_patch(rect)

    text_content = "船东输入: DWT · 航速 · 燃油类型 · 碳价 · 运营天数"
    ax.text(BAR_X + BAR_W / 2, bar_cy, text_content,
            ha="center", va="center",
            fontsize=9, color=ROTATED,
            fontfamily="sans-serif",
            rotation=90, rotation_mode="anchor",
            zorder=3)


def main():
    fig, ax = setup_figure()

    # Tier 1
    draw_tier1(ax)
    # Arrow: Tier 1 → Tier 2
    draw_down_arrow(ax, CENTER_X, T1_Y + T1_H, T2_Y - 0.05)
    # Tier 2
    draw_tier2(ax)
    # Arrow: Tier 2 → Tier 3
    draw_down_arrow(ax, CENTER_X, T2_Y + T2_H, T3_Y - 0.05)
    # Tier 3
    draw_tier3(ax)
    # Annotation bar
    draw_annotation_bar(ax)

    plt.tight_layout(pad=0)

    # Output paths
    results_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "results"
    )
    os.makedirs(results_dir, exist_ok=True)

    base = "fig_architecture_diagram_mpl"
    for ext in ["png", "pdf", "svg"]:
        path = os.path.join(results_dir, f"{base}.{ext}")
        fig.savefig(path, format=ext, dpi=200,
                    facecolor=WHITE, pad_inches=0.05)
        print(f"[OK] {ext.upper()}: {path}  ({os.path.getsize(path):,} bytes)")

    plt.close(fig)


if __name__ == "__main__":
    main()
