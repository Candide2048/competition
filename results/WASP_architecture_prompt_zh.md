# WASP 技术架构图 — ChatGPT Web 生图 Prompt（中文主体版）

> **使用方式**：复制下面整段 prompt，粘贴到 ChatGPT 网页端（开启 Create Image / 4o 图像生成），一次生成一张图。
>
> **语言策略**：中文标题 + 中文描述 + 英文技术术语/公式/缩写

---

## Prompt（直接复制使用）

```
Create a clean technical architecture diagram for a wind-assisted ship propulsion decision support system academic paper. Style: lightweight blueprint — white background, thin precise lines, restrained blue-gray palette, compact information density. Portrait orientation, 2:3 aspect ratio.

LAYOUT: Centered vertical flow (3 tiers) with a lateral annotation column on the right side. Each tier is a rounded-corner rectangle with a colored header tab on the top-left corner.

PALETTE:
- Primary lines and headers: Dark navy (#2C3E50)
- Secondary accent: Teal (#00897B)
- Tertiary: Warm gray (#78909C)
- Background: Pure white
- Module fills: Very light gray (#F5F7FA) with 1px navy borders
- Header tabs: Teal (#00897B) with white text

TIER 1 — Header tab text: "数据基础层"
A wide horizontal module. Title inside (bold): "ERA5 气候再分析数据引擎"
Below title, one line of compact specs in smaller font: "0.25° × 逐时 × 30°E–130°E | u10, v10, SST | 2025全年"
Below specs: 5 small minimalist route-dot icons in a horizontal row, labeled underneath: "中东→中国 | 阿拉伯海 | 孟加拉湾 | 南海 | 印度洋"

↓ thin precise downward arrow (navy color, simple triangular arrowhead)

TIER 2 — Header tab text: "计算核心层"
Three parallel vertical sub-modules side by side inside one large container rectangle:

Left sub-module — title "船舶阻力" (bold, navy):
- Line 1: "Holtrop-Mennen (1984)"
- Line 2: "5 SIMMAN 标准船型"
- Line 3: "R_T = f(V, trim, sea state)"

Center sub-module — title "帆型气动力" (bold, navy):
- Line 1: "Flettner: C_L(SR, α)"
- Line 2: "硬质翼帆: C_L(AoA)"
- Line 3: "吸力帆: polar curve"

Right sub-module — title "系统集成" (bold, teal):
- Line 1: "推力平衡方程"
- Line 2: "寄生功率扣除"
- Line 3: "ΔP_fuel 逐时步计算"

Horizontal thin arrows: Left sub-module → Right sub-module, Center sub-module → Right sub-module (both converging at the right module's mid-height)

↓ thin precise downward arrow

TIER 3 — Header tab text: "决策分析层"
Wide module with 4 compact horizontal output rows. Each row has a left metric label connected by a thin arrow to a right context annotation:
- Row 1: "节油矩阵 [%]" ──→ "900 组情景"
- Row 2: "CII 评级变化 [A→E]" ──→ "MEPC.353(78) 基线"
- Row 3: "NPV [USD]" ──→ "燃油 + EU ETS @ €74/t"
- Row 4: "回收期 [年]" ──→ "CAPEX vs. 年节省额"

LATERAL ANNOTATION (right side of the entire diagram):
A thin vertical warm-gray bar running the full height of the diagram, with vertically-rotated text reading: "船东输入: DWT · 航速 · 燃油类型 · 碳价 · 运营天数"

TYPOGRAPHY RULES:
- Chinese text: clean sans-serif font (like Source Han Sans or Noto Sans CJK style)
- English text and formulas: light-weight monospace or technical sans-serif
- Keep all text crisp and legible at small sizes
- Header tab text: white on teal, bold
- Module titles: navy, bold
- Body text: dark gray, regular weight

NEGATIVE CONSTRAINTS:
- No color gradients or glass/glossy effects
- No decorative icons, illustrations, clip art, or emoji
- No marketing or infographic aesthetics
- No drop shadows or 3D effects
- No curved connecting lines — all arrows are straight orthogonal lines
- No rounded bubble or pill shapes for text (only rectangular modules with slight corner radius)
- Maximum precision, minimum decoration
- Flat technical drawing style only
- The diagram should look like it belongs in an IEEE or ACM conference paper
```

---

## 备用：如果中文渲染效果不好，可尝试追加的修正指令

```
Please regenerate. Make sure all Chinese characters are rendered clearly with a proper CJK font — no garbled text, no placeholder boxes. The Chinese text must be fully readable.
```

---

## 生成后检查清单

- [ ] 三层结构清晰可辨（数据→计算→决策）
- [ ] 中文标题无乱码/缺字
- [ ] 英文公式清晰（特别是下标：C_L、R_T、ΔP_fuel）
- [ ] 箭头方向正确（上→下流动，左右→右汇聚）
- [ ] 右侧船东输入栏可见
- [ ] 整体色调统一（蓝灰为主，无彩色装饰）
- [ ] 适合缩小到论文单栏宽度仍可辨认
