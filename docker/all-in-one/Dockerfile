# ============================================
# 前后端合并 Dockerfile - 单镜像部署方案（优化版）
# 使用 python-slim 作为基础，体积更小
# ============================================
ARG PYTHON_IMAGE=python:3.13-slim-amd64
ARG NODE_IMAGE=node:22-alpine-amd64

# ==================== 前端构建阶段 ====================
FROM ${NODE_IMAGE} AS frontend-builder

WORKDIR /app/frontend

# 配置 npm 国内镜像源
RUN npm config set registry https://registry.npmmirror.com

# 复制前端依赖文件
COPY frontend/package*.json ./

# 安装依赖
RUN npm ci

# 复制前端源代码并构建
COPY frontend/ ./
RUN npm run build && \
    # 构建完成后删除 node_modules 减小体积
    rm -rf node_modules package-lock.json

# ==================== Python 依赖构建阶段 ====================
FROM ${PYTHON_IMAGE} AS python-builder

WORKDIR /app

# 配置国内 apt 镜像源（单次）
RUN echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-backports main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list

# 安装编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 配置 pip 国内镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# 复制并安装 Python 依赖
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

# ==================== 最终运行阶段 ====================
FROM ${PYTHON_IMAGE}

WORKDIR /app

# 配置国内 apt 镜像源（复用 python-builder 的配置）
COPY --from=python-builder /etc/apt/sources.list /etc/apt/sources.list

# 安装运行时依赖：nginx + supervisor + curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    libsqlite3-0 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    # 删除 nginx 默认站点配置，避免覆盖我们的配置
    && rm -f /etc/nginx/sites-enabled/default

# 从构建阶段复制 Python 依赖
COPY --from=python-builder /root/.local /root/.local

# 复制 spaCy 英语模型（从构建上下文）
COPY docker/all-in-one/model/en_core_web_sm /root/.local/lib/python3.13/site-packages/en_core_web_sm

# 设置 Python 环境变量
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/root/.local/lib/python3.13/site-packages:$PYTHONPATH

# 环境变量默认值（与 docker-compose.yml 保持一致）
ENV DEBUG=False
ENV HOST=0.0.0.0
ENV PORT=8000
ENV CORS_ORIGINS=["*"]
ENV SECRET_KEY=your-secret-key-change-in-production
ENV ACCESS_TOKEN_EXPIRE_MINUTES=3000
ENV KOKORO_API_URL=http://localhost:8880/v1/audio/speech
ENV KOKORO_DEFAULT_VOICE=bf_v0isabella
ENV KOKORO_DEFAULT_SPEED=1.0

# 复制后端代码
COPY backend/ /app/

# 复制前端构建产物到 Nginx 目录
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html

# 复制合并后的 Nginx 配置（本地代理到后端）
COPY docker/all-in-one/nginx.conf /etc/nginx/conf.d/default.conf

# 复制 Supervisor 配置
COPY docker/all-in-one/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 创建必要的目录
RUN mkdir -p /app/voices /app/Books /app/data /var/log/supervisor

# 暴露端口（只暴露 Nginx 端口）
EXPOSE 80

# 使用 Supervisor 启动多个服务
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
