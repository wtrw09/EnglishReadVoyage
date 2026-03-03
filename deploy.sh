#!/bin/bash

# EnglishReadVoyage Docker 部署脚本
# 使用方法: chmod +x deploy.sh && ./deploy.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 部署目录（脚本所在目录）
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  EnglishReadVoyage Docker 部署脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查 Docker 和 Docker Compose 是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker 未安装${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}错误: Docker Compose 未安装${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker 环境检查通过${NC}"

# 创建必要的目录结构
echo ""
echo -e "${YELLOW}[1/4] 创建目录结构...${NC}"

# 创建后端目录
mkdir -p "${DEPLOY_DIR}/backend/Books"
mkdir -p "${DEPLOY_DIR}/backend/data"

# 创建前端目录（如果需要）
mkdir -p "${DEPLOY_DIR}/frontend"

echo -e "${GREEN}✓ 目录创建完成${NC}"

# 设置目录权限
echo ""
echo -e "${YELLOW}[2/4] 设置目录权限...${NC}"

# 设置权限为 755（所有者可读写执行，其他用户可读执行）
chmod 755 "${DEPLOY_DIR}/backend"
chmod 755 "${DEPLOY_DIR}/backend/Books"
chmod 755 "${DEPLOY_DIR}/backend/data"

# 确保 Docker 容器可以写入这些目录
# 通常 Docker 容器以 root 运行，所以不需要特别设置所有者
# 但如果需要特定用户权限，可以取消下面的注释并修改
# chown -R 1000:1000 "${DEPLOY_DIR}/backend/Books"
# chown -R 1000:1000 "${DEPLOY_DIR}/backend/data"

echo -e "${GREEN}✓ 权限设置完成${NC}"

# 复制数据库文件
echo ""
echo -e "${YELLOW}[3/4] 复制数据库文件...${NC}"

# 检查源文件是否存在
if [ -f "${DEPLOY_DIR}/data.db" ]; then
    # 如果目标文件已存在，跳过复制
    if [ -f "${DEPLOY_DIR}/backend/data.db" ]; then
        echo -e "${YELLOW}⚠ backend/data.db 已存在，跳过复制${NC}"
    else
        cp "${DEPLOY_DIR}/data.db" "${DEPLOY_DIR}/backend/data.db"
        chmod 644 "${DEPLOY_DIR}/backend/data.db"
        echo -e "${GREEN}✓ data.db 已复制到 backend/data.db${NC}"
    fi
else
    # 如果目标文件不存在，创建新的
    if [ ! -f "${DEPLOY_DIR}/backend/data.db" ]; then
        echo -e "${YELLOW}⚠ 未找到 data.db，将创建新的数据库文件${NC}"
        touch "${DEPLOY_DIR}/backend/data.db"
        chmod 644 "${DEPLOY_DIR}/backend/data.db"
    else
        echo -e "${YELLOW}⚠ backend/data.db 已存在${NC}"
    fi
fi

if [ -f "${DEPLOY_DIR}/ecdict.db" ]; then
    # 如果目标文件已存在，跳过复制
    if [ -f "${DEPLOY_DIR}/backend/data/ecdict.db" ]; then
        echo -e "${YELLOW}⚠ backend/data/ecdict.db 已存在，跳过复制${NC}"
    else
        cp "${DEPLOY_DIR}/ecdict.db" "${DEPLOY_DIR}/backend/data/ecdict.db"
        chmod 644 "${DEPLOY_DIR}/backend/data/ecdict.db"
        echo -e "${GREEN}✓ ecdict.db 已复制到 backend/data/ecdict.db${NC}"
    fi
else
    echo -e "${YELLOW}⚠ 未找到 ecdict.db，词典功能可能无法使用${NC}"
fi

# 启动 Docker 容器
echo ""
echo -e "${YELLOW}[4/4] 启动 Docker 容器...${NC}"

# 检查 docker-compose.yml 是否存在
if [ ! -f "${DEPLOY_DIR}/docker-compose.yml" ]; then
    echo -e "${RED}错误: 未找到 docker-compose.yml 文件${NC}"
    exit 1
fi

# 检查镜像是否存在
echo "检查 Docker 镜像..."
if ! docker images | grep -q "englishread-backend"; then
    echo -e "${YELLOW}⚠ 未找到 englishread-backend 镜像${NC}"
    echo "请先加载镜像: docker load -i englishread-backend-amd64-latest.tar"
fi

if ! docker images | grep -q "englishread-frontend"; then
    echo -e "${YELLOW}⚠ 未找到 englishread-frontend 镜像${NC}"
    echo "请先加载镜像: docker load -i englishread-frontend-amd64-latest.tar"
fi

# 启动服务
echo "启动服务..."
cd "${DEPLOY_DIR}"

# 使用 docker compose 或 docker-compose
if docker compose version &> /dev/null; then
    docker compose up -d
else
    docker-compose up -d
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "服务访问地址:"
echo -e "  - 前端: ${YELLOW}http://<服务器IP>${NC}"
echo ""
echo -e "常用命令:"
echo -e "  查看日志: ${YELLOW}docker logs -f englishread-backend${NC}"
echo -e "  停止服务: ${YELLOW}docker-compose down${NC}"
echo -e "  重启服务: ${YELLOW}docker-compose restart${NC}"
echo ""
