// 中文翻译（默认语言）

export interface I18nKeys {
  brand_sub: string
  hero_eyebrow: string
  hero_verdict: (ship: string, n: number, sail: string, saving: string, ciiFrom: string, ciiTo: string, payback: string) => string
  chip_live: string
  chip_cache: string
  sec_kpi: string
  sec_kpi_title: string
  sec_cashflow: string
  sec_cashflow_title: string
  sec_cii: string
  sec_cii_title: string
  sec_sail: string
  sec_sail_title: string
  sec_bench: string
  sec_bench_title: string
  sec_matrix: string
  sec_matrix_title: string
  sec_route: string
  sec_report: string
  sec_report_title: string
  kpi_payback: string
  kpi_payback_unrecoverable: string
  kpi_payback_foot: (cost: string) => string
  kpi_annual: string
  kpi_annual_foot: (trips: string) => string
  kpi_saving: string
  kpi_saving_foot: (t: string) => string
  kpi_profit: string
  kpi_profit_earning: (yr: string) => string
  kpi_profit_expect: (yr: string) => string
  kpi_profit_none: string
  kpi_co2: string
  kpi_co2_foot: (t: string) => string
  kpi_cii: string
  kpi_cii_foot: (pct: string) => string
  cf_breakeven: (yr: string) => string
  cf_note: (yr: number) => string
  cf_warn: string
  cii_improve: (pct: string) => string
  cii_penalty: (k: string) => string
  sail_payback: string
  sail_saving: string
  sail_annual: string
  sb_ship: string
  sb_adv: string
  sb_override: string
  sb_override_note: string
  sb_speed: string
  sb_speed_hint: (speeds: string) => string
  sb_sail_type: string
  sb_sail_hint: (n: number) => string
  sb_flettner_spec: string
  sb_route: string
  sb_season: string
  sb_econ: string
  sb_fuel_type: string
  sb_fuel_price: string
  sb_co2_price: string
  sb_unit_cost: string
  sb_sea_ratio: string
  sb_sfoc: string
  sb_sfoc_note: string
  sb_draft: string
  loading: string
  loading_live: string
  err_api: string
  err_hint: string
  err_scenario: string
  speed_note: (sp: string, used: string) => string
  labels: Record<string, string>
  // Matrix
  matrix_saving: string
  matrix_annual: string
  matrix_payback: string
  matrix_corner: string
  matrix_loading: string
  matrix_err: (msg: string) => string
  // Welcome
  welcome: string
}

const zh: I18nKeys = {
  // Brand
  brand_sub: '风帆辅助推进 · 效益决策',
  // Hero
  hero_eyebrow: 'Wind-Assisted Ship Propulsion · 效益决策',
  hero_verdict: (ship: string, n: number, sail: string, saving: string, ciiFrom: string, ciiTo: string, payback: string) =>
    `为 ${ship} 加装 ${n} 台${sail}，节油 ${saving}%，CII ${ciiFrom}→${ciiTo}，回收 ${payback}。`,
  chip_live: '实时物理重算 (live)',
  chip_cache: '预计算网格 (缓存)',
  // Section headers
  sec_kpi: '核心效益',
  sec_kpi_title: '投资回收与节能指标',
  sec_cashflow: '投资回报',
  sec_cashflow_title: '累计净现金流（含贴现）',
  sec_cii: 'IMO合规',
  sec_cii_title: 'CII 评级跃迁 · 避免合规罚款',
  sec_sail: '帆型PK',
  sec_sail_title: '三帆型同条件横向对比',
  sec_bench: '实船校验',
  sec_bench_title: '节油率 vs 公开报道区间',
  sec_matrix: '全景矩阵',
  sec_matrix_title: '帆型 × 航速 效益热力图',
  sec_route: '航线',
  sec_report: '报告',
  sec_report_title: '自动生成技术分析',
  // KPI
  kpi_payback: '投资回收期',
  kpi_payback_unrecoverable: '不可回收',
  kpi_payback_foot: (cost: string) => `初始投资 $${cost}`,
  kpi_annual: '年净节省',
  kpi_annual_foot: (trips: string) => `${trips} 航次/年 · 含碳价收益`,
  kpi_saving: '节油率',
  kpi_saving_foot: (t: string) => `单航次节油 ${t} t`,
  kpi_profit: '20年累计收益',
  kpi_profit_earning: (yr: string) => `第 ${yr} 年开始盈利`,
  kpi_profit_expect: (yr: string) => `预计第 ${yr} 年回本`,
  kpi_profit_none: '20年内未回本，建议调整参数',
  kpi_co2: '年 CO₂ 减排',
  kpi_co2_foot: (t: string) => `单航次 ${t} t`,
  kpi_cii: 'CII 跃迁',
  kpi_cii_foot: (pct: string) => `碳强度改善 ${pct}%`,
  // Cashflow
  cf_breakeven: (yr: string) => `✓ 第 ${yr} 年收回全部投资，此后持续盈利`,
  cf_note: (yr: number) => `· 含 8% 贴现 + 2% 年维护 · 展示至第 ${yr} 年`,
  cf_warn: '⚠ 当前参数下 40 年内未回本，建议提高海上作业比例或选择风力更优航线',
  // CII
  cii_improve: (pct: string) => `碳强度改善 ${pct}%`,
  cii_penalty: (k: string) => `避免约 $${k}K/年 合规附加成本`,
  // Sail compare
  sail_payback: '回收期',
  sail_saving: '节油率',
  sail_annual: '年净节省',
  // Sidebar
  sb_ship: '船型',
  sb_adv: '实船参数（高级，可选）',
  sb_override: '启用实船几何覆盖',
  sb_override_note: '（触发 live 物理重算）',
  sb_speed: '航速 (kn)',
  sb_speed_hint: (speeds: string) => `标准网格 ${speeds} kn 秒级取数，其余触发 live。`,
  sb_sail_type: '风帆技术类型',
  sb_sail_hint: (n: number) => `安装台数 ${n} 台（等面积归一化，公平对比）。`,
  sb_flettner_spec: 'Flettner 规格 (H×D)',
  sb_route: '航线',
  sb_season: '季节',
  sb_econ: '经济性参数',
  sb_fuel_type: '燃料类型',
  sb_fuel_price: '燃油价 (USD/kg)',
  sb_co2_price: '碳价 (EUR/tCO₂)',
  sb_unit_cost: '单台成本 (USD)',
  sb_sea_ratio: '海上作业比例',
  sb_sfoc: 'SFOC (g/kWh)',
  sb_sfoc_note: 'SFOC ≠ 180 或非网格航速将触发 live 实时物理重算。',
  sb_draft: '吃水 (m)',
  // App loading
  loading: '加载参数选项…',
  loading_live: '实时物理重算中（首次约数秒，缓存后瞬时）…',
  err_api: '无法连接后端 API',
  err_hint: '请先启动',
  err_scenario: '场景计算失败：',
  speed_note: (sp: string, used: string) => `航速 ${sp} kn 不在标准集，已取最近邻 ${used} kn 网格值。`,
  // 选项标签：中文无需映射，仅季节值需要
  labels: {
    'winter': '冬季',
    'spring': '春季',
    'summer': '夏季',
    'autumn': '秋季',
  },
  // Matrix
  matrix_saving: '节油率 %',
  matrix_annual: '年净节省 $',
  matrix_payback: '回收期 年',
  matrix_corner: '帆型 \\ 航速',
  matrix_loading: '加载效益矩阵…',
  matrix_err: (msg: string) => `矩阵加载失败：${msg}`,
  // Welcome
  welcome: '左侧面板可调节船型、航速等参数，所有图表实时联动',
}

export default zh
