# WASP 技术架构图 — F01/F02 正式候选 Prompt

> **基于你选中的风格**：第三张图（竖向三层编号布局 + 右侧 OWNER INPUTS 链式参数栏 + 底部图例）
>
> **语言策略**：中文层级标题 + 中文模块名 + 英文术语/公式
>
> **使用方式**：分别复制 F01 和 F02 的 prompt 到 ChatGPT Web 生成，选出更好的一张

---

## F01 — 中文精修版（保留地图缩略图 + 图标）

```
Create a clean technical architecture diagram for a wind-assisted ship propulsion (WASP) decision support system. This is for an academic competition paper. Portrait orientation, 2:3 aspect ratio (1024×1536px).

STYLE: Lightweight blueprint aesthetic. White background. Thin precise lines. Flat design, no 3D or gradients. Clean and academic.

COLOR PALETTE:
- Primary: Dark navy (#2C3E50) for headers, borders, main arrows
- Accent: Teal (#1ABC9C) for the lateral input column dots and dashed lines
- Module fills: Very light gray (#F8F9FA)
- Module borders: 1px navy
- Background: Pure white (#FFFFFF)
- Legend text: Warm gray (#78909C)

OVERALL LAYOUT:
- Main content: left 75% of canvas width — vertical flow of 3 numbered tiers
- Right column: 25% width — "船东输入" (Owner Inputs) vertical parameter chain
- Bottom strip: line-type legend

═══════════════════════════════════════════════════

TIER 1 — Top section:
- Section header: "1. 数据基础层" (centered, navy, bold, larger font)
- One large rounded-corner rectangle below the header
- Inside the rectangle:
  - Title line (bold): "ERA5 气候再分析数据引擎"
  - Specs line (smaller, gray): "0.25° × 逐时 × 30°E–130°E | u10, v10, SST | 2025全年"
  - Below: 5 small minimalist map thumbnail icons in a horizontal row, each showing a simplified route region outline. Labeled below each: "中东→中国", "阿拉伯海", "孟加拉湾", "南海", "印度洋"

↓ Large bold navy downward-pointing arrow (filled triangle)

═══════════════════════════════════════════════════

TIER 2 — Middle section:
- Section header: "2. 计算核心层" (centered, navy, bold)
- One large container rectangle containing 3 equal-width sub-modules side by side:

Sub-module A (left) — header bar: "A. 船舶阻力"
Three stacked content boxes inside:
  • "Holtrop-Mennen (1984)"
  • "5 SIMMAN 标准船型"
  • "R_T = f(V, trim, sea state)"

Sub-module B (center) — header bar: "B. 帆型气动力"
Three stacked content boxes inside:
  • "Flettner: C_L(SR, α)"
  • "硬质翼帆: C_L(AoA)"
  • "吸力帆: polar curve"

Sub-module C (right) — header bar: "C. 系统集成"
Three stacked content boxes inside:
  • "推力平衡方程"
  • "寄生功率扣除"
  • "ΔP_fuel 逐时步"

ARROWS within Tier 2: Horizontal arrows from A → C and from B → C (converging into module C at mid-height)

↓ Large bold navy downward-pointing arrow

═══════════════════════════════════════════════════

TIER 3 — Bottom section:
- Section header: "3. 决策分析层" (centered, navy, bold)
- One wide container with 4 equal columns inside:

Each column has:
- Top: a metric title box (navy border, bold text)
- Bottom: a context annotation box (lighter, smaller text)
- Connected by a vertical dashed line between them

Column 1: "节油矩阵 [%]" ↓ "900组情景"
Column 2: "CII评级变化 [A→E]" ↓ "MEPC.353(78) 基线"
Column 3: "NPV [USD]" ↓ "燃油 + EU ETS @€74/t"
Column 4: "回收期 [年]" ↓ "CAPEX vs. 年节省额"

═══════════════════════════════════════════════════

RIGHT LATERAL COLUMN — "船东输入" (Owner Inputs):
- Header at top: "船东输入" with a small gear/settings icon
- Below: 5 circular teal nodes arranged vertically, connected by teal dashed lines
- Node labels (one per node, top to bottom): "DWT", "航速", "燃油类型", "碳价", "运营天数"
- Teal dashed arrows from this column pointing left into Tier 2 and Tier 3 (showing input influence)

═══════════════════════════════════════════════════

BOTTOM LEGEND (small, gray text):
"—— 主数据流    - - - 输入影响    —·— 参考链接"

TYPOGRAPHY:
- Chinese: clean sans-serif (Noto Sans CJK / Source Han Sans style)
- English/Math: light monospace
- All text must be crisp and fully legible

ABSOLUTE CONSTRAINTS:
- NO color gradients or glossy effects
- NO 3D shadows or depth effects
- NO curved or wavy connecting lines (all straight/orthogonal)
- NO marketing or infographic clip-art style
- Minimal decorative elements (map thumbnails and gear icon are the ONLY exceptions)
- The result must look like a figure from an IEEE/ASME academic paper
```

---

## F02 — 极简紧凑版（去掉地图/图标，纯文字+线条）

```
Create an ultra-clean technical architecture diagram for a wind-assisted ship propulsion decision support system. Academic paper style. Portrait orientation, 2:3 aspect ratio.

STYLE: Pure technical schematic — no icons, no illustrations, no decorative elements whatsoever. Only text, boxes, and lines. Think: engineering specification drawing.

COLORS: Navy (#2C3E50), Teal (#00897B), Light gray fills (#F5F7FA), White background.

LAYOUT: Vertical 3-tier numbered flow (left 80%) + right annotation column (20%). All boxes have 2px rounded corners (radius 4px).

─────────────────────────────────────────

TIER 1: "1. 数据基础层"
Box content:
  "ERA5 气候再分析数据引擎"
  "0.25° × 逐时 × 30°E–130°E | u10, v10, SST | 2025全年"
  "航线覆盖: 中东→中国 · 阿拉伯海 · 孟加拉湾 · 南海 · 印度洋"

↓ solid navy arrow

TIER 2: "2. 计算核心层"
Three columns within one container:

| A. 船舶阻力           | B. 帆型气动力          | C. 系统集成           |
|----------------------|----------------------|---------------------|
| Holtrop-Mennen(1984) | Flettner: C_L(SR,α)  | 推力平衡方程          |
| 5 SIMMAN 标准船型     | 硬质翼帆: C_L(AoA)    | 寄生功率扣除          |
| R_T=f(V,trim,sea)   | 吸力帆: polar curve   | ΔP_fuel 逐时步       |

Arrows: A→C, B→C (horizontal, at row 2 height)

↓ solid navy arrow

TIER 3: "3. 决策分析层"
Four-column table layout:

| 节油矩阵[%] | CII评级[A→E] | NPV[USD]        | 回收期[年]       |
|------------|-------------|-----------------|----------------|
| 900组情景   | MEPC.353(78)| 燃油+ETS@€74/t  | CAPEX vs.年节省  |

RIGHT COLUMN: "船东输入"
Vertical list with teal bullet dots:
• DWT
• 航速
• 燃油类型
• 碳价
• 运营天数
Teal dashed lines pointing left into Tier 2 and Tier 3.

BOTTOM: "—— 数据流  --- 输入影响"

STRICT RULES:
- ZERO icons, ZERO illustrations, ZERO decorative elements
- ONLY rectangles, text, straight lines, and arrows
- Monochrome navy + teal only
- Looks like a figure from a Chinese master's thesis
- All Chinese text rendered clearly in sans-serif CJK font
```

---

## 对比说明

| 维度 | F01 | F02 |
|------|-----|-----|
| 风格 | 接近你选中的第三张：有地图缩略图+齿轮图标 | 极简到极致：零图标，纯文字+框+线 |
| 信息密度 | 中等，留白舒适 | 高密度，适合窄栏 |
| 适用场景 | 申报书正文主图 | 备用 / PPT 缩略图 |
| 中文可读性 | 高（字号充裕） | 高（纯文字无干扰） |

---

## 生成后检查清单

- [ ] 三层编号（1/2/3）清晰可见
- [ ] 右侧"船东输入"链完整（5个参数节点）
- [ ] 中文标题无乱码（数据基础层/计算核心层/决策分析层）
- [ ] 英文公式正确（R_T、C_L、ΔP_fuel）
- [ ] 箭头方向：垂直↓ + 水平→C 汇聚
- [ ] 色调统一（navy+teal，无多余彩色）
- [ ] 底部图例可见

## 如果中文渲染不清晰，追加指令：

```
Regenerate with all Chinese characters clearly rendered using a proper sans-serif CJK font. No garbled text or missing characters. Every Chinese character must be fully readable.
```
