// 中文翻译（默认语言）

export interface I18nKeys {
  brand_sub: string
  hero_eyebrow: string
  hero_verdict: (ship: string, n: number, sail: string, saving: string, ciiFrom: string, ciiTo: string, payback: string) => string
  hero_rec_install: (ship: string, n: number, sail: string, saving: string, payback: string, npv: string) => string
  hero_rec_no_install: (ship: string, sail: string) => string
  hero_rec_loading: (ship: string) => string
  hero_compared: (count: number) => string
  decision_state_positive: string
  decision_state_conditional: string
  decision_state_negative: string
  decision_npv_negative: (value: string) => string
  decision_payback_long: (year: string | null) => string
  decision_cii_same: (grade: string, pct: string) => string
  decision_guardrail: string
  decision_outside_benchmark: string
  decision_positive_reason: string
  quality_weather_basis: (years: string, samples: number) => string
  quality_interval_unavailable: string
  chip_live: string
  chip_cache: string
  sec_kpi: string
  sec_kpi_title: string
  sec_detail: string
  sec_detail_title: string
  detail_context: string
  detail_units: string
  detail_hint: string
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
  vs_eyebrow: string
  vs_fuel: string
  vs_money: string
  vs_rate: string
  vs_note: (trips: string, annual: string) => string
  kpi_profit: string
  kpi_profit_earning: (yr: string) => string
  kpi_profit_expect: (yr: string) => string
  kpi_profit_none: string
  kpi_co2: string
  kpi_co2_foot: (t: string) => string
  kpi_cii_status: string
  kpi_cii_change: string
  kpi_cii_same: (grade: string) => string
  kpi_cii_foot: (pct: string) => string
  cf_breakeven: (yr: string) => string
  cf_note: (yr: number) => string
  cf_warn: string
  cii_improve: (pct: string) => string
  cii_penalty: (k: string) => string
  sail_payback: string
  sail_saving: string
  sail_annual: string
  sail_npv20: string
  rec_loading: string
  rec_error: (message: string) => string
  rec_install: (sail: string, payback: string, npv: string) => string
  rec_no_install: (sail: string, npv: string) => string
  rec_no_candidate: string
  rec_basis: string
  rec_recommended: string
  rec_best_available: string
  sail_view_detail: string
  sail_detail_selected: string
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
  sb_show_params: string
  sb_hide_params: string
  sb_view_results: string
  loading: string
  loading_live: string
  err_api: string
  err_hint: string
  err_hint_suffix: string
  err_scenario: string
  err_boot_fallback: string
  retry: string
  speed_note: (sp: string, used: string) => string
  guardrail_note: (raw: string, cap: string) => string
  sec_unc: string
  sec_unc_title: string
  unc_loading: string
  unc_unavailable: string
  unc_err: (msg: string) => string
  unc_metric_saving: string
  unc_metric_annual: string
  unc_metric_npv: string
  unc_payback_label: string
  unc_payback_cases: (p10: string, p50: string, p90: string) => string
  unc_risk_fuel: string
  unc_risk_npv: string
  unc_risk_bench: string
  unc_basis: (years: string, n: number, block: number) => string
  sec_pareto: string
  sec_pareto_title: string
  pareto_loading: string
  pareto_err: (msg: string) => string
  pareto_front: string
  pareto_rank: string
  pareto_npv: string
  pareto_robust_npv: string
  pareto_co2: string
  pareto_payback: string
  pareto_cost: string
  pareto_selected: string
  pareto_dominated: (n: number) => string
  pareto_note: string
  sec_audit: string
  sec_audit_title: string
  audit_loading: string
  audit_expand: string
  audit_err: (msg: string) => string
  audit_records: string
  audit_weather_years: string
  audit_scope: string
  audit_insights: string
  audit_tests: string
  audit_seed: string
  audit_model_chain: string
  audit_guardrails: string
  audit_cap: string
  audit_limitations: string
  audit_repro: string
  audit_docker: string
  sec_wind: string
  sec_wind_title: string
  wind_loading: string
  wind_err: (msg: string) => string
  wind_unavailable: string
  wind_fit_good: string
  wind_fit_medium: string
  wind_fit_poor: string
  wind_reason_low_wind: string
  wind_reason_beam: string
  wind_reason_head: string
  wind_reason_tail: string
  wind_mean_true: string
  wind_mean_apparent: string
  wind_net_saving_hours: string
  wind_low_wind: string
  wind_speed_dist: string
  wind_angle_dist: string
  wind_basis: (years: string) => string
  labels: Record<string, string>
  // Benchmark
  bench_range: string
  // Matrix
  matrix_saving: string
  matrix_annual: string
  matrix_payback: string
  matrix_corner: string
  matrix_loading: string
  matrix_err: (msg: string) => string
  // Welcome
  welcome: string
  // Market Prices
  mp_title: string
  mp_refresh: string
  mp_fuel: string
  mp_co2: string
  mp_fx: string
  mp_apply: string
  mp_updated: string
  mp_region_asia: string
  mp_region_eu: string
  mp_region_am: string
  mp_region_me: string
  mp_display_timezone: string
}

const zh: I18nKeys = {
  // Brand
  brand_sub: '风帆辅助推进 · 效益决策',
  // Hero
  hero_eyebrow: 'Wind-Assisted Ship Propulsion · 效益决策',
  hero_verdict: (ship: string, n: number, sail: string, saving: string, ciiFrom: string, ciiTo: string, payback: string) =>
    `为 ${ship} 加装 ${n} 台${sail}，节油 ${saving}%，${ciiFrom === ciiTo ? `CII 维持 ${ciiTo}` : `CII ${ciiFrom}→${ciiTo}`}，回收 ${payback}。`,
  hero_rec_install: (ship: string, n: number, sail: string, saving: string, payback: string, npv: string) =>
    `建议为 ${ship} 安装 ${n} 台${sail}：预计节油 ${saving}%，回收期 ${payback}，20 年净现值 ${npv}。`,
  hero_rec_no_install: (ship: string, sail: string) =>
    `当前假设下，暂不建议为 ${ship} 安装${sail}；请先复核成本、航线与运营约束。`,
  hero_rec_loading: (ship: string) => `正在生成 ${ship} 的改装建议…`,
  hero_compared: (count: number) => `已比较 ${count} 种兼容帆型`,
  decision_state_positive: '建议进入方案深化',
  decision_state_conditional: '有条件可行，需进一步验证',
  decision_state_negative: '当前经济假设下不建议投资',
  decision_npv_negative: (value: string) => `20 年净现值为 ${value}`,
  decision_payback_long: (year: string | null) => year ? `预计回收期 ${year} 年，超过 20 年评估期` : '评估期内无法回收投资',
  decision_cii_same: (grade: string, pct: string) => `CII 维持 ${grade}，碳强度改善 ${pct}%`,
  decision_guardrail: '节油率已触发实船证据护栏，需用海试数据复核',
  decision_outside_benchmark: '结果位于当前公开实船参考区间之外',
  decision_positive_reason: '20 年净现值为正，且节油率位于公开实船参考区间内',
  quality_weather_basis: (years: string, samples: number) => `天气 ${years} · 每季 ${samples} 个代表日`,
  quality_interval_unavailable: '暂未生成 P10/P50/P90',
  chip_live: '实时物理重算 (live)',
  chip_cache: '预计算网格 (缓存)',
  // Section headers
  sec_kpi: '核心效益',
  sec_kpi_title: '投资回收与节能指标',
  sec_detail: '详细场景',
  sec_detail_title: '当前帆型的投资回收与节能指标',
  detail_context: '当前查看的单帆型详情',
  detail_units: '台',
  detail_hint: '用于查看该帆型的现金流、CII 和实船基准；不会改变上方跨帆型推荐的排序规则。',
  sec_cashflow: '投资回报',
  sec_cashflow_title: '累计净现金流（含贴现）',
  sec_cii: 'IMO合规',
  sec_cii_title: 'CII 评级跃迁 · 降低合规风险',
  sec_sail: '方案推荐',
  sec_sail_title: '同参数帆型推荐与经济性对比',
  sec_bench: '案例对照',
  sec_bench_title: '节油率 vs 公开报道区间',
  sec_matrix: '全景矩阵',
  sec_matrix_title: '帆型 × 航速 效益热力图',
  sec_route: '航线',
  sec_report: '报告',
  sec_report_title: '自动生成方案推荐报告',
  // KPI
  kpi_payback: '投资回收期',
  kpi_payback_unrecoverable: '不可回收',
  kpi_payback_foot: (cost: string) => `初始投资 $${cost}`,
  kpi_annual: '年净节省',
  kpi_annual_foot: (trips: string) => `${trips} 航次/年 · 含影子碳价收益`,
  kpi_saving: '节油率',
  kpi_saving_foot: (t: string) => `单航次节油 ${t} t`,
  vs_eyebrow: '单航次直观收益',
  vs_fuel: '本航次节油',
  vs_money: '单航次净节省（燃油+碳）',
  vs_rate: '节油率',
  vs_note: (trips: string, annual: string) => `按 ${trips} 航次/年 换算 → 年净节省 ${annual}`,
  kpi_profit: '20年净现值',
  kpi_profit_earning: (yr: string) => `第 ${yr} 年开始盈利`,
  kpi_profit_expect: (yr: string) => `预计第 ${yr} 年回本`,
  kpi_profit_none: '20年内未回本，建议调整参数',
  kpi_co2: '年 CO₂ 减排',
  kpi_co2_foot: (t: string) => `单航次 ${t} t`,
  kpi_cii_status: 'CII 状态',
  kpi_cii_change: 'CII 等级变化',
  kpi_cii_same: (grade: string) => `维持 ${grade}`,
  kpi_cii_foot: (pct: string) => `碳强度改善 ${pct}%`,
  // Cashflow
  cf_breakeven: (yr: string) => `✓ 第 ${yr} 年收回全部投资，此后持续盈利`,
  cf_note: (yr: number) => `· 含 8% 贴现 + 2% 年维护 · 展示至第 ${yr} 年`,
  cf_warn: '⚠ 当前参数下 40 年内未回本，建议提高海上作业比例或选择风力更优航线',
  // CII
  cii_improve: (pct: string) => `碳强度改善 ${pct}%`,
  cii_penalty: (k: string) => `降低约 $${k}K/年 合规成本风险（影子碳价估算）`,
  // Sail compare
  sail_payback: '回收期',
  sail_saving: '节油率',
  sail_annual: '年净节省',
  sail_npv20: '20 年净现值',
  rec_loading: '正在按全部用户参数比较兼容帆型…',
  rec_error: (message: string) => `帆型推荐计算失败：${message}`,
  rec_install: (sail: string, payback: string, npv: string) =>
    `建议优先评估 ${sail}：回收期 ${payback}，20 年净现值 ${npv}`,
  rec_no_install: (sail: string, npv: string) =>
    `当前参数下不建议安装；相对最优候选为 ${sail}，但 20 年净现值仍为 ${npv}`,
  rec_no_candidate: '当前船型没有可用的兼容帆型',
  rec_basis: '全部候选保持船型、航线、航速、天气和经济参数一致，并采用各帆型默认配置成本。',
  rec_recommended: '推荐',
  rec_best_available: '相对最优',
  sail_view_detail: '查看该帆型详情',
  sail_detail_selected: '正在查看',
  // Sidebar
  sb_ship: '船型',
  sb_adv: '实船参数（高级，可选）',
  sb_override: '启用实船几何覆盖',
  sb_override_note: '（触发 live 物理重算）',
  sb_speed: '航速 (kn)',
  sb_speed_hint: (speeds: string) => `标准网格 ${speeds} kn 秒级取数，其余触发 live。`,
  sb_sail_type: '单帆型详情',
  sb_sail_hint: (n: number) => `查看 ${n} 台配置的详细结果；系统推荐仍会独立比较全部兼容帆型。`,
  sb_flettner_spec: 'Flettner 规格 (H×D)',
  sb_route: '航线',
  sb_season: '季节',
  sb_econ: '经济性参数',
  sb_fuel_type: '燃料类型',
  sb_fuel_price: '燃油价 (USD/kg)',
  sb_co2_price: '影子碳价 (EUR/tCO₂)',
  sb_unit_cost: '单台成本 (USD)',
  sb_sea_ratio: '海上作业比例',
  sb_sfoc: 'SFOC (g/kWh)',
  sb_sfoc_note: 'SFOC 线性缩放油耗与省钱，实时生效（不触发重算）。',
  sb_draft: '吃水 (m)',
  sb_show_params: '调整方案参数',
  sb_hide_params: '收起方案参数',
  sb_view_results: '查看更新后的结果',
  // App loading
  loading: '加载参数选项…',
  loading_live: '实时物理重算中（首次约数秒，缓存后瞬时）…',
  err_api: '无法连接后端 API',
  err_hint: '请先启动',
  err_hint_suffix: '。',
  err_scenario: '场景计算失败：',
  err_boot_fallback: '选项加载失败',
  retry: '重新连接',
  speed_note: (sp: string, used: string) => `航速 ${sp} kn 不在标准集，已取最近邻 ${used} kn 网格值。`,
  guardrail_note: (raw: string, cap: string) =>
    `理想物理结果为 ${raw}%，已按实船筛选证据上限 ${cap}% 保守校准；原值保留在 API 质量字段中。`,
  // 选项标签：中文无需映射，仅季节值需要
  labels: {
    // 帆型稳定键（后端 benchmark_ranges key）
    'flettner': 'Flettner 旋筒帆',
    'rigid_wing': '刚性翼帆',
    'suction_wing': '吸力帆',
    'winter': '冬季',
    'spring': '春季',
    'summer': '夏季',
    'autumn': '秋季',
  },
  // Uncertainty band
  sec_unc: '风险区间',
  sec_unc_title: '节油与收益的 P10 / P50 / P90 置信区间',
  unc_loading: '正在计算不确定性区间…',
  unc_unavailable: '当前场景暂无预计算不确定性区间（live 重算或产物未覆盖），主 KPI 不受影响。',
  unc_err: (msg: string) => `不确定性区间加载失败：${msg}`,
  unc_metric_saving: '节油率',
  unc_metric_annual: '年净节省',
  unc_metric_npv: '20 年净现值',
  unc_payback_label: '回收期三情形',
  unc_payback_cases: (p10: string, p50: string, p90: string) =>
    `保守 ${p10} · 中位 ${p50} · 乐观 ${p90}`,
  unc_risk_fuel: '节油为正概率',
  unc_risk_npv: '20 年 NPV 为正概率',
  unc_risk_bench: '落于公开案例区间概率',
  unc_basis: (years: string, n: number, block: number) =>
    `方法：ERA5 ${years} 逐小时风场 · ${block}h 环块自助法 ${n} 次重采样 · 经济性随油价/碳价滑杆实时联动，与主 KPI 同口径`,
  // Pareto 决策前沿
  sec_pareto: '决策前沿',
  sec_pareto_title: '帆型 × 航速多目标 Pareto 前沿',
  pareto_loading: '正在计算 Pareto 前沿…',
  pareto_err: (msg: string) => `Pareto 前沿加载失败：${msg}`,
  pareto_front: 'Pareto 前沿',
  pareto_rank: '层级',
  pareto_npv: '20 年 NPV',
  pareto_robust_npv: 'P10 稳健 NPV',
  pareto_co2: '年 CO₂ 减排',
  pareto_payback: '回收期',
  pareto_cost: '初始投资',
  pareto_selected: '当前方案',
  pareto_dominated: (n: number) => `被 ${n} 个候选支配`,
  pareto_note: '六目标非支配排序（NSGA-II 风格）：20 年 NPV、P10 稳健 NPV、年 CO₂ 减排、CII 改善率越大越好；回收期、初始投资越小越好。绿色前沿候选互不支配——任何目标的改进都要以牺牲其他目标为代价；灰色候选存在全面更优的替代。随油价/碳价/在航率滑杆实时更新。',
  // 模型审计
  sec_audit: '模型审计',
  sec_audit_title: '打开黑箱：模型链路、护栏与已知限制',
  audit_loading: '正在加载审计信息…',
  audit_expand: '模型方法、护栏与复现信息（点击展开）',
  audit_err: (msg: string) => `审计信息加载失败：${msg}`,
  audit_records: '物理网格记录',
  audit_weather_years: 'ERA5 天气年份',
  audit_scope: '船型 × 航线 × 季节',
  audit_insights: '不确定性情景',
  audit_tests: '自动化测试',
  audit_seed: 'bootstrap 随机种子',
  audit_model_chain: '模型链路：数据源 → KPI 逐级可溯源',
  audit_guardrails: '护栏与公开案例对照',
  audit_cap: '节油率筛查上限',
  audit_limitations: '已知限制（诚实呈现）',
  audit_repro: '可复现性',
  audit_docker: 'Docker 容器化部署，云端与本地环境一致',
  // 风资源适配
  sec_wind: '风资源',
  sec_wind_title: '这条航线的风，适合这款帆吗？',
  wind_loading: '正在读取风资源统计…',
  wind_err: (msg: string) => `风资源统计加载失败：${msg}`,
  wind_unavailable: '当前场景暂无预计算风资源统计（live 重算或产物未覆盖），主 KPI 不受影响。',
  wind_fit_good: '适配良好',
  wind_fit_medium: '中等适配',
  wind_fit_poor: '适配欠佳',
  wind_reason_low_wind: '低风时段占比高，帆推力受限',
  wind_reason_beam: '横风占主导，正处升力型帆的高效区间',
  wind_reason_head: '顶风占比高，可用推力窗口收窄',
  wind_reason_tail: '顺风占主导，推力窗口充足',
  wind_mean_true: '平均真风速',
  wind_mean_apparent: '平均视风速',
  wind_net_saving_hours: '净节油贡献小时占比（>2%）',
  wind_low_wind: '低风（<3 m/s）占比',
  wind_speed_dist: '真风速分布',
  wind_angle_dist: '相对风角分布（0°=顶风 · 180°=顺风）',
  wind_basis: (years: string) =>
    `统计基础：ERA5 ${years} 逐小时风场 · 与节油物理同一次航次模拟采样，口径一致；净节油贡献 = 逐时净节油率＞2% 的小时占比（已扣除转子电耗）`,
  // Benchmark
  bench_range: '公开案例参考范围',
  // Matrix
  matrix_saving: '节油率 %',
  matrix_annual: '年净节省 $',
  matrix_payback: '回收期 年',
  matrix_corner: '帆型 \\ 航速',
  matrix_loading: '加载效益矩阵…',
  matrix_err: (msg: string) => `矩阵加载失败：${msg}`,
  // Welcome
  welcome: '左侧面板可调节船型、航速等参数，所有图表实时联动',
  // Market Prices
  mp_title: '燃油报价中心',
  mp_refresh: '刷新行情',
  mp_fuel: 'VLSFO 油价',
  mp_co2: '碳排放配额',
  mp_fx: 'EUR/USD 汇率',
  mp_apply: '应用市场价格',
  mp_updated: '更新时间',
  mp_region_asia: '亚太区',
  mp_region_eu: '欧洲区',
  mp_region_am: '美洲区',
  mp_region_me: '中东区',
  mp_display_timezone: '显示时区',
}

export default zh
