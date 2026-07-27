# -*- coding: utf-8 -*-
"""Generate a clean technical architecture diagram for the WASP decision support system.

Style: lightweight blueprint — white background, thin precise lines,
restrained blue-gray palette, compact information density.
Portrait orientation, 2:3 aspect ratio (1000 × 1500).

Output:
    shipping_wasp/results/fig_architecture_diagram.svg
    shipping_wasp/results/fig_architecture_diagram.png  (if cairosvg available)

Usage:
    cd shipping_wasp/code
    python generate_architecture_diagram.py
"""
import os
import textwrap

# ---------- Palette ----------
NAVY      = "#2C3E50"   # primary lines and headers
TEAL      = "#00897B"   # secondary accent
GRAY      = "#78909C"   # tertiary (warm gray)
WHITE     = "#FFFFFF"
FILL      = "#F5F7FA"   # module fills
GRAY_LIGHT= "#CFD8DC"   # annotation bar fill
TEXT_DARK = "#333333"
TEXT_MED  = "#666666"
TEXT_SPEC = "#555555"

# ---------- Font stacks ----------
FONT_CJK  = "'Noto Sans CJK SC', 'Source Han Sans SC', 'Microsoft YaHei', 'SimHei', sans-serif"
FONT_MONO = "'Consolas', 'Courier New', monospace"
FONT_SANS = "'Helvetica Neue', 'Arial', sans-serif"

# ---------- Canvas ----------
W = 1000
H = 1500

# ---------- Layout constants ----------
LEFT   = 50          # left content margin
RIGHT  = 890         # right content edge
CW     = RIGHT - LEFT  # content width = 840
BAR_X  = 915         # annotation bar x
BAR_W  = 30          # annotation bar width

# Tier Y positions
T1_Y = 50;   T1_H = 270
T2_Y = 380;  T2_H = 600
T3_Y = 1040; T3_H = 380

# Arrow positions
ARROW1_Y1 = T1_Y + T1_H       # 320
ARROW1_Y2 = T2_Y - 5          # 375
ARROW2_Y1 = T2_Y + T2_H       # 980
ARROW2_Y2 = T3_Y - 5          # 1035

CENTER_X = (LEFT + RIGHT) // 2  # 470

# Sub-module positions (Tier 2)
SUB_Y = 440
SUB_H = 440
SUB_W = 240
SUB_GAP = 30
SUB1_X = 80
SUB2_X = SUB1_X + SUB_W + SUB_GAP   # 350
SUB3_X = SUB2_X + SUB_W + SUB_GAP   # 620
SUB_MID_Y = SUB_Y + SUB_H // 2      # 660


def svg_header() -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <marker id="arrow-navy" markerWidth="10" markerHeight="8"
            refX="9" refY="4" orient="auto" markerUnits="strokeWidth">
      <polygon points="0,0 10,4 0,8" fill="{NAVY}"/>
    </marker>
    <marker id="arrow-teal" markerWidth="10" markerHeight="8"
            refX="9" refY="4" orient="auto" markerUnits="strokeWidth">
      <polygon points="0,0 10,4 0,8" fill="{TEAL}"/>
    </marker>
    <marker id="arrow-gray" markerWidth="8" markerHeight="6"
            refX="7" refY="3" orient="auto" markerUnits="strokeWidth">
      <polygon points="0,0 8,3 0,6" fill="{GRAY}"/>
    </marker>
  </defs>
  <rect width="{W}" height="{H}" fill="{WHITE}"/>
'''


def header_tab(x, y, w, h, text) -> str:
    """Colored header tab with white text, top-left of a container."""
    return f'''    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4"
          fill="{TEAL}" stroke="none"/>
    <text x="{x + w//2}" y="{y + h//2 + 5}" text-anchor="middle"
          font-family="{FONT_CJK}" font-size="15" font-weight="bold"
          fill="{WHITE}">{text}</text>
'''


def container(x, y, w, h, rx=6) -> str:
    """Light-gray filled container with navy border."""
    return f'''    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}"
          fill="{FILL}" stroke="{NAVY}" stroke-width="1"/>
'''


def sub_module(x, y, w, h, title, title_color, lines, border_color=None) -> str:
    """A sub-module box with title and content lines."""
    if border_color is None:
        border_color = NAVY
    sw = "1.5" if border_color == TEAL else "1"
    parts = []
    parts.append(
        f'    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4"\n'
        f'          fill="{WHITE}" stroke="{border_color}" stroke-width="{sw}"/>'
    )
    # Title
    cx = x + w // 2
    parts.append(
        f'    <text x="{cx}" y="{y + 38}" text-anchor="middle"\n'
        f'          font-family="{FONT_CJK}" font-size="18" font-weight="bold"\n'
        f'          fill="{title_color}">{title}</text>'
    )
    # Separator line under title
    sep_y = y + 52
    parts.append(
        f'    <line x1="{x + 20}" y1="{sep_y}" x2="{x + w - 20}" y2="{sep_y}"\n'
        f'          stroke="{GRAY}" stroke-width="0.5" stroke-dasharray="3,3"/>'
    )
    # Content lines
    for i, (text, is_mono) in enumerate(lines):
        ly = sep_y + 38 + i * 32
        ff = FONT_MONO if is_mono else FONT_CJK
        parts.append(
            f'    <text x="{cx}" y="{ly}" text-anchor="middle"\n'
            f'          font-family="{ff}" font-size="13"\n'
            f'          fill="{TEXT_DARK}">{text}</text>'
        )
    return "\n".join(parts) + "\n"


def tier1() -> str:
    """Data Foundation Layer."""
    parts = []
    parts.append(container(LEFT, T1_Y, CW, T1_H))
    parts.append(header_tab(LEFT, T1_Y, 140, 32, "数据基础层"))

    # Title
    parts.append(
        f'    <text x="{CENTER_X}" y="{T1_Y + 75}" text-anchor="middle"\n'
        f'          font-family="{FONT_CJK}" font-size="24" font-weight="bold"\n'
        f'          fill="{NAVY}">ERA5 气候再分析数据引擎</text>'
    )
    # Specs
    parts.append(
        f'    <text x="{CENTER_X}" y="{T1_Y + 110}" text-anchor="middle"\n'
        f'          font-family="{FONT_MONO}" font-size="14"\n'
        f'          fill="{TEXT_SPEC}">0.25° × 逐时 × 30°E–130°E | u10, v10, SST | 2025全年</text>'
    )

    # Route dots — 5 dots connected by a thin line
    dot_y = T1_Y + 165
    dot_xs = [130, 300, 470, 640, 810]
    # Connecting line
    parts.append(
        f'    <line x1="{dot_xs[0]}" y1="{dot_y}" x2="{dot_xs[-1]}" y2="{dot_y}"\n'
        f'          stroke="{GRAY}" stroke-width="1"/>'
    )
    # Dots
    for dx in dot_xs:
        parts.append(
            f'    <circle cx="{dx}" cy="{dot_y}" r="5" fill="{TEAL}" stroke="{NAVY}" stroke-width="0.5"/>'
        )
    # Labels
    labels = ["中东→中国", "阿拉伯海", "孟加拉湾", "南海", "印度洋"]
    label_y = dot_y + 28
    for dx, lbl in zip(dot_xs, labels):
        parts.append(
            f'    <text x="{dx}" y="{label_y}" text-anchor="middle"\n'
            f'          font-family="{FONT_CJK}" font-size="12"\n'
            f'          fill="{TEXT_MED}">{lbl}</text>'
        )

    return "\n".join(parts) + "\n"


def tier2() -> str:
    """Computation Core Layer."""
    parts = []
    parts.append(container(LEFT, T2_Y, CW, T2_H))
    parts.append(header_tab(LEFT, T2_Y, 140, 32, "计算核心层"))

    # Three sub-modules
    parts.append(sub_module(
        SUB1_X, SUB_Y, SUB_W, SUB_H,
        "船舶阻力", NAVY,
        [("Holtrop-Mennen (1984)", True),
         ("5 SIMMAN 标准船型", False),
         ("R_T = f(V, trim, sea state)", True)],
        border_color=NAVY,
    ))
    parts.append(sub_module(
        SUB2_X, SUB_Y, SUB_W, SUB_H,
        "帆型气动力", NAVY,
        [("Flettner: C_L(SR, α)", True),
         ("硬质翼帆: C_L(AoA)", True),
         ("吸力帆: polar curve", True)],
        border_color=NAVY,
    ))
    parts.append(sub_module(
        SUB3_X, SUB_Y, SUB_W, SUB_H,
        "系统集成", TEAL,
        [("推力平衡方程", False),
         ("寄生功率扣除", False),
         ("ΔP_fuel 逐时步计算", False)],
        border_color=TEAL,
    ))

    # Converging arrows (orthogonal, navy)
    # Sub2 → Sub3: direct horizontal at mid-height
    parts.append(
        f'    <line x1="{SUB2_X + SUB_W}" y1="{SUB_MID_Y}" '
        f'x2="{SUB3_X - 2}" y2="{SUB_MID_Y}"\n'
        f'          stroke="{NAVY}" stroke-width="1" '
        f'marker-end="url(#arrow-navy)"/>'
    )

    # Sub1 → Sub3: route below Sub2 (orthogonal)
    # Path: (SUB1 right, lower) → down → right (below sub2) → up → right into Sub3
    p_start_x = SUB1_X + SUB_W      # 320
    p_start_y = SUB_MID_Y + 120     # 780 (lower part of Sub1)
    p_down_y  = SUB_Y + SUB_H + 30  # 910 (below sub-modules)
    p_up_x    = SUB3_X - 15         # 605 (in gap before Sub3)
    p_end_y   = SUB_MID_Y           # 660

    polyline_points = (
        f"{p_start_x},{p_start_y} "
        f"{p_start_x + 15},{p_start_y} "
        f"{p_start_x + 15},{p_down_y} "
        f"{p_up_x},{p_down_y} "
        f"{p_up_x},{p_end_y} "
        f"{SUB3_X - 2},{p_end_y}"
    )
    parts.append(
        f'    <polyline points="{polyline_points}"\n'
        f'          fill="none" stroke="{NAVY}" stroke-width="1" '
        f'marker-end="url(#arrow-navy)"/>'
    )

    return "\n".join(parts) + "\n"


def tier3() -> str:
    """Decision Analysis Layer."""
    parts = []
    parts.append(container(LEFT, T3_Y, CW, T3_H))
    parts.append(header_tab(LEFT, T3_Y, 140, 32, "决策分析层"))

    # 4 rows: left metric → arrow → right context
    rows = [
        ("节油矩阵 [%]",        "900 组情景"),
        ("CII 评级变化 [A→E]",  "MEPC.353(78) 基线"),
        ("NPV [USD]",           "燃油 + EU ETS @ €74/t"),
        ("回收期 [年]",         "CAPEX vs. 年节省额"),
    ]

    row_start_y = T3_Y + 70
    row_spacing = 70
    label_x  = LEFT + 70     # 120 — left-aligned metric
    arrow_x1 = LEFT + 250    # 300
    arrow_x2 = LEFT + 430    # 480
    annot_x  = LEFT + 460    # 510 — left-aligned context

    for i, (metric, context) in enumerate(rows):
        ry = row_start_y + i * row_spacing

        # Left metric label
        parts.append(
            f'    <text x="{label_x}" y="{ry}" text-anchor="start"\n'
            f'          font-family="{FONT_CJK}" font-size="15" font-weight="bold"\n'
            f'          fill="{NAVY}">{metric}</text>'
        )
        # Arrow
        parts.append(
            f'    <line x1="{arrow_x1}" y1="{ry - 4}" x2="{arrow_x2}" y2="{ry - 4}"\n'
            f'          stroke="{NAVY}" stroke-width="1" '
            f'marker-end="url(#arrow-navy)"/>'
        )
        # Right context annotation
        parts.append(
            f'    <text x="{annot_x}" y="{ry}" text-anchor="start"\n'
            f'          font-family="{FONT_CJK}" font-size="14"\n'
            f'          fill="{TEXT_MED}">{context}</text>'
        )

    return "\n".join(parts) + "\n"


def vertical_arrow(x, y1, y2, color=NAVY) -> str:
    """Thin precise downward arrow with triangular arrowhead."""
    return (
        f'    <line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}"\n'
        f'          stroke="{color}" stroke-width="1.5" '
        f'marker-end="url(#arrow-navy)"/>'
    )


def annotation_bar() -> str:
    """Lateral annotation column on the right side."""
    bar_y = T1_Y                    # 50
    bar_h = T3_Y + T3_H - T1_Y     # 1370
    bar_cy = bar_y + bar_h // 2     # 735

    parts = []
    # Vertical warm-gray bar
    parts.append(
        f'    <rect x="{BAR_X}" y="{bar_y}" width="{BAR_W}" height="{bar_h}"\n'
        f'          fill="{GRAY_LIGHT}" stroke="{GRAY}" stroke-width="0.5" rx="3"/>'
    )
    # Rotated text (vertical, reading bottom-to-top)
    text_content = "船东输入: DWT · 航速 · 燃油类型 · 碳价 · 运营天数"
    parts.append(
        f'    <text x="{BAR_X + BAR_W // 2}" y="{bar_cy}"\n'
        f'          text-anchor="middle"\n'
        f'          font-family="{FONT_CJK}" font-size="14"\n'
        f'          fill="#546E7A"\n'
        f'          transform="rotate(-90, {BAR_X + BAR_W // 2}, {bar_cy})">{text_content}</text>'
    )
    return "\n".join(parts) + "\n"


def generate_svg() -> str:
    parts = []
    parts.append(svg_header())
    parts.append("  <!-- ===== TIER 1: Data Foundation ===== -->")
    parts.append(tier1())
    parts.append(f"  <!-- ===== Arrow: Tier 1 → Tier 2 ===== -->")
    parts.append(vertical_arrow(CENTER_X, ARROW1_Y1, ARROW1_Y2))
    parts.append("  <!-- ===== TIER 2: Computation Core ===== -->")
    parts.append(tier2())
    parts.append(f"  <!-- ===== Arrow: Tier 2 → Tier 3 ===== -->")
    parts.append(vertical_arrow(CENTER_X, ARROW2_Y1, ARROW2_Y2))
    parts.append("  <!-- ===== TIER 3: Decision Analysis ===== -->")
    parts.append(tier3())
    parts.append("  <!-- ===== Lateral Annotation Bar ===== -->")
    parts.append(annotation_bar())
    parts.append("</svg>")
    return "\n".join(parts)


def main():
    svg_content = generate_svg()

    # Output paths
    results_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "results"
    )
    os.makedirs(results_dir, exist_ok=True)

    svg_path = os.path.join(results_dir, "fig_architecture_diagram.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(f"[OK] SVG saved: {svg_path}")
    print(f"     Size: {os.path.getsize(svg_path):,} bytes")

    # Try to render PNG (optional)
    png_path = os.path.join(results_dir, "fig_architecture_diagram.png")
    try:
        import cairosvg
        cairosvg.svg2png(
            bytestring=svg_content.encode("utf-8"),
            write_to=png_path,
            output_width=W * 2,   # 2× for retina
            output_height=H * 2,
        )
        print(f"[OK] PNG saved: {png_path}")
        print(f"     Size: {os.path.getsize(png_path):,} bytes")
    except ImportError:
        print("[INFO] cairosvg not installed — skipping PNG render.")
        print("       Install with: pip install cairosvg")
        print("       Or open SVG in browser/Inkscape to view.")


if __name__ == "__main__":
    main()
