FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码（含 config/ + 预计算网格）
COPY code/ ./code/

# 复制前端构建产物
COPY web/frontend/dist/ ./web/frontend/dist/

# 暴露端口（Render/Zeabur 会自动检测 $PORT）
ENV PORT=8600
EXPOSE 8600

# api.py 位于 code/app/api.py，模块引用基于 code/
WORKDIR /app/code

# 启动命令：兼容 Render/Zeabur 的 $PORT 环境变量
CMD uvicorn app.api:app --host 0.0.0.0 --port ${PORT} --workers 1
