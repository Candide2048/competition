# WASP 项目框架图 — S2 Image Generation Prompts

> **使用方式**：将下面每个 `C01`–`C04` 的 prompt 文本块分别复制粘贴到 ChatGPT 网页端（需开启 Create Image 模式），每次粘贴一个，生成一张候选框架图。
>
> **参考风格**：用户提供的干旱研究 pipeline 参考图（pill 形标题、圆角内容框、白底、清晰箭头连接）

---

## C01 — Top-Down Technical Pipeline (参考图风格复刻)

```text
Create a publication-ready academic framework diagram for a research paper titled "Wind-Assisted Ship Propulsion Benefit Prediction and Low-Carbon Route Adaptation Decision System". The diagram should follow the exact visual style of top-tier Chinese academic pipeline figures:

LAYOUT: Top-to-bottom vertical pipeline, 4 major layers connected by bold downward arrows. White background, clean and uncluttered.

STYLE REQUIREMENTS:
- Section headers: Rounded pill/capsule shapes with solid dark fill (navy #1A3A5C) and white bold text
- Content boxes: Rounded-corner rectangles with thin gray borders and light fill
- Sub-items inside boxes: arranged in neat 2-3 column grid
- Arrows: Thick directional arrows between major layers, dark gray or navy
- Small illustrative icons or mini-diagrams inside content boxes where relevant (weather maps, ship silhouettes, charts)
- Font: Clean sans-serif, English labels preferred
- No gradients, no 3D effects, no decorative elements
- Aspect ratio: Portrait (roughly 2:3)

STRUCTURE (top to bottom):

LAYER 1 HEADER (pill): "Data Acquisition Layer"
Content box below with items:
- "ERA5 Reanalysis (u10, v10)" with small wind map icon
- "0.25° grid, hourly, 4.21 GB"
- "Coverage: 30°E–130°E, 10°S–40°N"
- "5 Asian energy import corridors"
- "4 seasonal departure profiles"

↓ (bold arrow)

LAYER 2 HEADER (pill): "Physical Modeling Layer"
Content box with 3 parallel sub-modules:
Left: "Holtrop-Mennen Resistance" (with formula hint: RT = RF + RAPP + RW + RB + RTR + RA)
Center: "Tri-Sail Aerodynamics" (sub-items: Flettner CL/CD regression, Rigid Wing wind tunnel, Suction Wing polar)
Right: "Thrust Balance" (with: Power deduction, Rotor/fan parasitic load, Speed-power equilibrium)

↓ (bold arrow)

LAYER 3 HEADER (pill): "Scenario Analysis Layer"
Content box with items:
- "900-Scenario Matrix: 5 ships × 5 routes × 4 seasons × 3 sails × 3 speeds"
- "Fuel Saving Rate (%)" 
- "CII Rating Improvement (MEPC.353(78), 14 ship types)"
- "NPV & Payback (fuel saving + EU ETS €74/tCO₂)"
- "Owner-adjustable parameters"

↓ (bold arrow)

LAYER 4 HEADER (pill): "Decision Delivery Layer"  
Content box with items:
- "FastAPI + React Dashboard (public web)"
- "Route Animation Map"
- "Benefit Heatmap Matrix"
- "KPI Gauges & Markdown Report Export"

NEGATIVE CONSTRAINTS:
- No AI-blue/purple gradient backgrounds
- No glossy orb effects or neon colors
- No decorative photo thumbnails
- No complex internal diagrams within boxes
- Keep text readable at journal column width
- Do not include any Chinese characters
```

---

## C02 — Nature Communications Color-Region Style

```text
Create a publication-ready method overview figure for a maritime decarbonization research paper. Use the visual style of Nature Communications figures: distinct color-coded functional regions on a white canvas, with clean data flow arrows connecting them.

LAYOUT: Left-to-right primary flow with 4 color-coded regions. White background. Each region is a soft-colored rectangular area containing module boxes.

STYLE:
- 4 distinct soft-pastel background regions (not boxes, but subtle shaded areas)
- Region 1 (Inputs): Light teal (#E0F2F1) background
- Region 2 (Physics Engine): Light blue (#E3F2FD) background  
- Region 3 (Analysis): Light amber (#FFF8E1) background
- Region 4 (Outputs): Light green (#E8F5E9) background
- Module boxes inside regions: White with thin colored border matching region
- Arrows: Solid dark gray with arrowheads, connecting modules across regions
- Labels: Small clean sans-serif text
- No gradients, no 3D, no decorative elements
- Aspect ratio: Landscape (roughly 3:2)

REGION 1 — INPUTS (left, teal area):
Boxes:
- "ERA5 Wind Field (u10, v10)" 
- "Ship Parameters (L, B, T, Cb, DWT)"
- "Route Waypoints (5 corridors)"
- "Economic Parameters (fuel price, carbon price)"

→ arrows flow right into →

REGION 2 — PHYSICS ENGINE (center-left, blue area, dashed border):
Boxes arranged vertically:
- "Holtrop-Mennen Ship Resistance"
- "Sail Aerodynamic Force (CL, CD → Thrust)"
- "Thrust Balance & Power Reduction"
Connected by internal vertical arrows

→ arrows flow right into →

REGION 3 — ANALYSIS (center-right, amber area):
Boxes:
- "900 Scenario Pre-computation"
- "Fuel Saving Rate (%)"
- "CII Δ Rating (MEPC.353(78))"
- "NPV & Payback Period"
Connected by internal flow

→ arrows flow right into →

REGION 4 — OUTPUTS (right, green area):
Boxes:
- "Interactive Web Dashboard"
- "Benefit Heatmap"
- "Route Optimization Map"
- "Technical Assessment Report"

BOTTOM ANNOTATION: A thin horizontal bar showing "5 Ships × 5 Routes × 3 Sails × 4 Seasons × 3 Speeds = 900 Scenarios"

NEGATIVE CONSTRAINTS:
- No Chinese characters
- No photo-realistic elements
- No neon or saturated colors
- No marketing-poster aesthetics
- Keep compact, no excessive whitespace
- All text must be readable at 80mm figure width
```

---

## C03 — Compact Method Architecture (Blueprint Style)

```text
Create a clean technical architecture diagram for a wind-assisted ship propulsion decision support system paper. Style: lightweight blueprint — white background, thin precise lines, restrained blue-gray palette, compact information density.

LAYOUT: Centered vertical flow (3 tiers) with a lateral annotation column. Portrait orientation.

PALETTE:
- Primary lines and headers: Dark navy (#2C3E50)
- Secondary accent: Teal (#00897B)  
- Tertiary: Warm gray (#78909C)
- Background: Pure white
- Module fills: Very light gray (#F5F7FA) with 1px navy borders

TIER 1 — DATA INFRASTRUCTURE:
A wide horizontal module labeled "ERA5 Climate Reanalysis Data Engine"
Inside: compact text "0.25° × hourly × 30°E-130°E | u10, v10, SST | 2025 full year"
Below: 5 small route-path icons labeled "ME→CN | Arabian | Bengal | SCS | IO"

↓ thin precise arrow

TIER 2 — COMPUTATIONAL CORE:
Three parallel vertical sub-modules side by side, each with internal layers:

Module A: "Ship Resistance"
- "Holtrop-Mennen (1984)"
- "5 SIMMAN hulls"
- "RT = f(V, trim, sea state)"

Module B: "Sail Aerodynamics"  
- "Flettner: CL(SR,α)"
- "Rigid Wing: CL(AoA)"
- "Suction Wing: polar curve"

Module C: "Integration"
- "Thrust balance"
- "Parasitic power deduction"
- "ΔP_fuel per timestep"

Horizontal arrows connecting A→C and B→C at mid-height

↓ thin precise arrow

TIER 3 — DECISION ANALYTICS:
Wide module with 4 output lanes:
- "Fuel Saving Matrix [%]" → connects to "900 scenarios"
- "CII Rating Change [A→E]" → connects to "MEPC.353(78) baseline"
- "NPV [USD]" → connects to "fuel + EU ETS @ €74/t"
- "Payback [years]" → connects to "CAPEX vs. annual saving"

LATERAL ANNOTATION (right side, thin vertical bar):
"Owner Inputs: DWT, speed, fuel type, carbon price, operational days"

NEGATIVE CONSTRAINTS:
- No color gradients or glass effects
- No decorative icons or illustrations
- No marketing aesthetics
- Maximum precision, minimum decoration
- All English text, no Chinese
- Suitable for IEEE/ACM double-column format at 88mm width
```

---

## C04 — Storytelling Pipeline with Internal Mechanism Detail

```text
Create a research paper framework figure showing the complete methodology pipeline for a Wind-Assisted Ship Propulsion (WASP) benefit prediction system. Style: formal publication schematic with visible internal mechanisms for core modules — the reviewer should immediately understand HOW each step works, not just WHAT it does.

LAYOUT: Top-to-bottom pipeline with 4 major stages. Each stage shows its internal mechanism using simple visual motifs. White background, portrait orientation.

STYLE:
- Stage containers: Rounded rectangles with colored left-border accent (4 distinct colors)
- Stage headers: Bold text at top of each container
- Internal mechanisms: Simple process-flow tokens, formulas, or state-change indicators
- Inter-stage arrows: Bold dark arrows with edge labels showing what data flows
- Palette: Restrained — Teal (#00897B), Navy (#1A3A5C), Amber (#F59E0B), Coral (#E05A47)
- Clean sans-serif font throughout

STAGE 1 (teal accent): "Meteorological Data Acquisition"
Internal mechanism shown:
[ERA5 API] → [Spatial crop: 30°E-130°E] → [Temporal: 4 seasons × hourly] → [Grid: 0.25°]
Edge label on output arrow: "Wind vectors (u10, v10) along route waypoints"

STAGE 2 (navy accent): "Multi-Physics Simulation Engine"
Internal mechanism (3 parallel paths merging):
Path A: [Hull geometry] → [Holtrop-Mennen] → [RT(V)]
Path B: [Wind angle α] → [Sail model CL/CD] → [Thrust T_sail]  
Path C: [Propeller η] → [Power balance] → [ΔP_fuel]
Merge point: "Net fuel saving per timestep Δt"
Edge label on output: "Fuel saving rate per route segment"

STAGE 3 (amber accent): "Scenario Matrix & KPI Computation"
Internal mechanism:
[5×5×3×4×3 = 900 scenarios] → parallel outputs:
  → "Fuel saving (%)" 
  → "CO₂ reduction (t/voyage)"
  → "CII Δrating (MEPC.353(78))"
  → "NPV & payback (fuel + ETS)"
Edge label: "Owner-parameterized economics"

STAGE 4 (coral accent): "Interactive Decision Dashboard"
Internal mechanism:
[API endpoint] → parallel deliverables:
  → "Route map with wind overlay"
  → "900-cell benefit heatmap"
  → "KPI comparison gauges"
  → "Downloadable assessment report"

BOTTOM NOTE (small, gray): "Validated: 7.55% fuel saving (ME→CN, Flettner ×4) aligned with Norsepower 6.1% / bound4blue 8%"

NEGATIVE CONSTRAINTS:
- No Chinese characters in the figure
- No AI-gradient or neon artifacts
- No glossy/3D effects
- Internal mechanisms use simple tokens (rectangles, arrows, merge points), NOT complex sub-diagrams
- Keep figure readable at single-column journal width
- No decorative illustrations or photos
```

---

## 使用说明

1. 打开 ChatGPT 网页端（chat.openai.com）
2. 确保使用 GPT-4o 或更高版本，开启 Create Image 功能
3. 每次粘贴一个 prompt 块（从 "Create a..." 开始到最后一个 constraint）
4. 等待生成，保存为 C01.png – C04.png
5. 选出你最满意的 1-2 张，反馈给我进入 S3/S4 精修阶段

### 推荐组合

- **C01** 最贴近你提供的参考图风格（pill header + grid items）
- **C02** Nature Comms 色块区域风格，横向排列
- **C03** 极简蓝图风格，适合 IEEE/ACM 双栏论文
- **C04** 内部机制可见的叙事 pipeline，审稿人一看就懂 HOW

### 如果需要中文版

在任何 prompt 末尾删除 "No Chinese characters" 的约束，并添加：
```
All text labels should be in Chinese (简体中文). Use professional academic Chinese terminology.
```
