# WASP 交互仪表盘（React 前端 + 极薄 FastAPI）

面向演示与实时交互的高级前端，视觉对标 bound4blue 简约高级风，叠加真·数字滚动、
Hero 文字揭示、航线动态绘制、CII 评级跃迁、滚动叙事等动效。

**数值真源在 Python**：前端所有指标一律经极薄 FastAPI 调用现有 `app.data_access`
得到，与 Streamlit 专家工具 **100% 同源、零公式重写**。Streamlit 仪表盘原样保留
（`streamlit run app/dashboard.py`）。

```
web/
  run_dev.ps1          # 一键并行启动后端 + 前端（开发）
  frontend/            # Vite + React + TS
    src/
      api.ts           # fetch 封装 + 类型
      App.tsx          # 组装 + 首屏拉 options + useScenario
      components/      # Sidebar/Hero/KpiGrid/CiiBadge/BenchmarkBar/
                       #   RouteMap/MatrixHeatmap/ReportPanel/Background/...
      hooks/           # useScenario(debounce 250ms) / useReveal(滚动淡入)
      styles/          # theme.css(tokens) + app.css(组件)
```

后端在 `code/app/api.py`（接口 `/api/options`、`/api/scenario`、`/api/matrix`、`/api/health`）。

---

## 一、开发模式（推荐，热更新）

前端 vite 跑 5173，把 `/api` 代理到后端 8600；改前端秒级热更，改后端 uvicorn 自动 reload。

**一键启动**（PowerShell）：

```powershell
cd shipping_wasp\web
.\run_dev.ps1
```

脚本会：首次自动 `npm install` → 后台起 `uvicorn app.api:app --reload --port 8600`
→ 前台起 `npm run dev`（打开 http://localhost:5173 ）。在窗口按 `Ctrl+C` 一并停止。

**手动分步**（两个终端）：

```powershell
# 终端 1 —— 后端
cd shipping_wasp\code
python -m uvicorn app.api:app --reload --port 8600

# 终端 2 —— 前端
cd shipping_wasp\web\frontend
npm install        # 首次
npm run dev        # http://localhost:5173
```

---

## 二、演示模式（单端口单进程，最稳）

前端构建为静态产物 `dist/`，由 FastAPI `StaticFiles` 与 `/api` 同端口托管：

```powershell
# 1) 构建前端
cd shipping_wasp\web\frontend
npm install        # 首次
npm run build      # 产出 web/frontend/dist/

# 2) 单端口启动（同时供 /api 与前端页面）
cd ..\..\code
python -m uvicorn app.api:app --port 8600
```

打开 http://127.0.0.1:8600 即为完整前端；`/api/*` 同源，无需 CORS。

> `app/api.py` 启动时若检测到 `web/frontend/dist/` 存在，则自动挂载到 `/`；
> 开发模式该目录不存在，会静默跳过（走 vite proxy）。

---

## 三、依赖

- **后端**：`pip install -e ".[api]"`（在 `code/` 下），即 `fastapi` + `uvicorn[standard]` + `httpx`。
- **前端**：`react` `react-dom` + `react-countup`（数字滚动）+ `gsap`（文字揭示/stagger）；
  地图与热力图为**自研 Canvas/SVG + CSS**（全离线、无地图 token、构建可靠）。

## 四、端口约定

| 服务 | 端口 | 说明 |
|------|------|------|
| FastAPI 后端 | 8600 | `/api/*`；演示模式同时托管前端 dist |
| Vite 前端(dev) | 5173 | proxy `/api` → 8600 |
| Streamlit(保留) | 8503 | 专家深度工具，独立运行，不受影响 |

## 五、数值一致性校验

后端测试 `code/tests/test_api.py` 以 `da.pick_physics + da.postprocess` 为金标准，
逐字段核对 `/api/scenario` 返回值（`pytest.approx(rel=1e-9)`）：

```powershell
cd shipping_wasp\code
pytest tests/test_api.py -q
```

任取一组输入，本前端 KPI 数字与 Streamlit(8503) 应完全一致。
