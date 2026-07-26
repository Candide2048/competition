# Shipping WASP

面向船东前期决策的风帆辅助推进（Wind-Assisted Ship Propulsion, WASP）效益筛选工具。系统把航线代表性风场、船舶阻力、三类风帆气动模型、燃油与碳成本、IMO CII 串成同一计算链，并通过 FastAPI + React 仪表盘展示结果。

## 能力范围

- 船型：VLCC、Kamsarmax、MR 成品油轮、集装箱船、PCTC。
- 帆型：Flettner 旋筒帆、刚性翼帆、吸力帆。
- 输出：单航次节油与减排、年化节省、回收期、10/20 年 NPV、CII 评级、帆型和航速矩阵。
- 两级计算：标准组合读取已提交的预计算网格；非标准航速、Flettner 规格、SFOC 或船舶几何参数使用 ERA5 做即时物理重算。
- 船型与帆型兼容因子在 CII 和经济性计算之前应用，所有主 KPI 使用同一口径。
- 页面先给出基于 20 年 NPV、回收期和实船区间的筛选结论，并明确显示天气样本与不确定性数据是否可用。
- 推荐接口会在其余用户参数完全一致时逐一计算所有兼容帆型；只有 20 年 NPV 为正且能在 20 年内回本的候选才会被推荐，否则报告明确给出“不建议安装”及相对最优候选。跨帆型比较采用各帆型配置的默认成本，避免当前点选帆型或其自定义单价影响推荐排序。

## 项目结构

```text
code/
  analytics/       CII、节油、经济性计算
  app/             FastAPI、数据访问和报告生成
  config/          船型、帆型、航线与经济参数
  core/            ERA5、输入校验、市场参考数据
  models/          气动、水动力、推进与推力平衡模型
  pipelines/       单航次和预计算矩阵管线
  results/         已提交的物理网格与图表
  tests/           Python 测试
web/frontend/      React + TypeScript + Vite 前端
data/              本地 ERA5 NetCDF 数据，不提交到 Git
```

## 本地运行

要求 Python 3.11 和 Node.js 20。PowerShell 示例：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

Set-Location web\frontend
npm ci
npm run build

Set-Location ..\..\code
python -m uvicorn app.api:app --reload --port 8600
```

打开 `http://127.0.0.1:8600`。前端开发模式可在 `web/frontend` 运行 `npm run dev`，Vite 会把 `/api` 转发到 8600 端口。

需要 ERA5 即时重算时，改用 `python -m pip install -r requirements-live.txt` 安装固定版本的 NetCDF 后端。

## 验证

```powershell
Set-Location code
python -m pytest tests -v

Set-Location ..\web\frontend
npm ci
npm run build
```

Python 依赖在 `requirements.txt` 固定版本，前端依赖由 `package-lock.json` 锁定。GitHub Actions 会运行无需本地 ERA5 的核心 Python 测试、TypeScript 检查和生产构建。

## 数据与部署

预计算网格位于 `code/results/precomputed/physics_grid.json`，因此不带 ERA5 的 Docker 部署仍可处理标准场景。即时重算需要将 NetCDF 文件放入 `data/`；API 会通过 `/api/options` 声明 `live_physics` 能力，前端据此隐藏不可用控件。缺少 ERA5 时，直接请求 live 场景会返回明确的 HTTP 503。

油价和碳价是可手动应用的参考输入。系统从 U.S. EIA 获取最新发布的 Brent 日度现货，从 Frankfurter/ECB 获取工作日 EUR/USD，并按浏览器 IANA 时区自动选择 Singapore、Rotterdam、Houston 或 Fujairah 报价中心。页面明确显示检测到的时区和实际采用的报价中心。日度数据标为 `DELAYED`，缓存标为 `CACHED`；EIA 不可用时才回退 `STATIC`。生产环境可设置 `EIA_API_KEY`，未设置时使用 EIA 的低限额 `DEMO_KEY`。

EEX/ICE 的 EUA 实时成交数据需要市场数据订阅，本项目不抓取或伪造该价格，因此 EU ETS 仍明确标为 `STATIC` 并由用户确认后应用。参考接口：[U.S. EIA Brent daily spot](https://www.eia.gov/dnav/pet/hist/RBRTED.htm)、[Frankfurter](https://frankfurter.dev/)、[EEX Market Data](https://www.eex.com/en/market-data/documentation)。

## 模型限制

- 这是前期技术经济筛选工具，不是气象航线优化器、船级审批工具或投资承诺。
- 当前 ERA5 只覆盖 2025 年，每季使用一个代表出发日。多年 ERA5 用于覆盖年际季风、异常天气和不同出发日，并生成 P10/P50/P90，而不是让单年四个日期决定投资结论；它不能替代船体或帆型参数校准。
- 预计算网格的 Flettner 物理规格固定为 `24x4`；其他规格必须使用 ERA5 即时重算。
- 理想化物理模型未包含横倾/侧向力、主机最低负荷、收帆和控制损失。主 KPI 因此使用 30% 实船筛选证据护栏；API 同时返回 `quality.raw_saving_rate_pct`、护栏前值和 `guardrail_applied`，不隐藏原始模型偏差。
- PCTC 参数和部分帆型成本来自公开资料估算；实际项目应使用船厂、供应商和船级社数据替换。
- CII 默认使用 2026 年降低因子，并允许在 API 支持范围内显式选择年份。

## 主要资料来源

- Copernicus Climate Data Store ERA5 风场。
- IMO MEPC.353(78) CII 参考线与评级边界。
- Guzelbulut (2024)、Song (2025) 等公开气动与经济性研究。
- Norsepower、Oceanbird、bound4blue 等公开案例和技术资料。

更细的参数来源与假设记录在 `code/config/`、研究材料和申报书中。
