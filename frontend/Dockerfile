# 前端 Dockerfile - 多阶段构建
ARG NODE_IMAGE=node:22-alpine-amd64
ARG NGINX_IMAGE=nginx:alpine-amd64

# 构建阶段
FROM ${NODE_IMAGE} AS builder

WORKDIR /app

# 配置 npm 国内镜像源，加速依赖安装
RUN npm config set registry https://registry.npmmirror.com

# 复制 package.json 和 package-lock.json
COPY package*.json ./

# 安装依赖
RUN npm ci

# 复制源代码
COPY . .

# 构建应用
RUN npm run build

# 生产阶段 - 使用 Nginx 服务静态文件
FROM ${NGINX_IMAGE}

# 复制构建产物到 Nginx 目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制自定义 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 启动 Nginx
CMD ["nginx", "-g", "daemon off;"]
