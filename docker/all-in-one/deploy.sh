#!/bin/bash

# EnglishReadVoyage Docker 部署脚本
# 使用方法: chmod +x deploy.sh && ./deploy.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 部署目录（脚本所在目录）
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  EnglishReadVoyage Docker 部署脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查是否以 root 或具有 sudo 权限运行
check_permissions() {
    if [ "$EUID" -ne 0 ]; then
        if ! sudo -n true 2>/dev/null; then
            echo -e "${YELLOW}⚠ 当前非 root 用户，部分权限操作可能需要 sudo${NC}"
        fi
    fi
}
check_permissions

# 检查 Docker 和 Docker Compose 是否安装
if ! command -v docker &> /dev/null1; then
    echo -e "${RED}错误: Docker 未安装${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}错误: Docker Compose 未安装${NC}"
    exit 1
fi

# 检查 Docker 服务是否运行
if ! docker info &> /dev/null; then
    echo -e "${RED}错误: Docker 服务未运行，请先启动 Docker${NC}"
    echo -e "  启动命令: ${YELLOW}sudo systemctl start docker${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker 环境检查通过${NC}"

# 创建必要的目录结构
echo ""
echo -e "${BLUE}[1/4] 创建目录结构...${NC}"

mkdir -p "${DEPLOY_DIR}/backend/Books"
mkdir -p "${DEPLOY_DIR}/backend/data"
mkdir -p "${DEPLOY_DIR}/backend/data/word_audio"

echo -e "${GREEN}✓ 目录创建完成${NC}"

# 设置目录权限
echo ""
echo -e "${BLUE}[2/4] 设置目录权限...${NC}"

# 设置目录权限为 755
chmod 755 "${DEPLOY_DIR}/backend"
chmod 755 "${DEPLOY_DIR}/backend/Books"
chmod 755 "${DEPLOY_DIR}/backend/data"
chmod 755 "${DEPLOY_DIR}/backend/data/word_audio"

# 确保当前用户对挂载目录有完整读写权限
# Docker 容器内通常以 root(uid=0) 运行，宿主机目录需对其可写
if [ "$EUID" -ne 0 ]; then
    # 非 root 用户：设置目录为组可写，并将当前用户加入 docker 组提示
    chmod 775 "${DEPLOY_DIR}/backend/Books"
    chmod 775 "${DEPLOY_DIR}/backend/data"
    chmod 775 "${DEPLOY_DIR}/backend/data/word_audio"
    if ! groups "$USER" | grep -q docker; then
        echo -e "${YELLOW}⚠ 当前用户 '$USER' 不在 docker 组中${NC}"
        echo -e "  建议执行: ${YELLOW}sudo usermod -aG docker $USER${NC} 后重新登录"
    fi
fi

echo -e "${GREEN}✓ 权限设置完成${NC}"

# 复制数据库文件
echo ""
echo -e "${BLUE}[3/4] 复制数据库文件...${NC}"
echo ""

# 定义所需的数据库文件列表
DB_DIR="${DEPLOY_DIR}/backend/data"
REQUIRED_DBS=("data.db" "ecdict.db" "merriam_webster_cache.db")

# 检查并处理主数据库 data.db
if [ -f "${DEPLOY_DIR}/data.db" ]; then
    if [ -f "${DB_DIR}/data.db" ]; then
        echo -e "${YELLOW}⚠ backend/data/data.db 已存在，跳过复制${NC}"
    else
        cp "${DEPLOY_DIR}/data.db" "${DB_DIR}/data.db"
        chmod 644 "${DB_DIR}/data.db"
        echo -e "${GREEN}✓ data.db 已复制到 backend/data/data.db${NC}"
    fi
fi

# 复制 ecdict.db
if [ -f "${DEPLOY_DIR}/ecdict.db" ]; then
    if [ -f "${DB_DIR}/ecdict.db" ]; then
        echo -e "${YELLOW}⚠ backend/data/ecdict.db 已存在，跳过复制${NC}"
    else
        cp "${DEPLOY_DIR}/ecdict.db" "${DB_DIR}/ecdict.db"
        chmod 644 "${DB_DIR}/ecdict.db"
        echo -e "${GREEN}✓ ecdict.db 已复制到 backend/data/ecdict.db${NC}"
    fi
fi

# 复制 merriam_webster_cache.db
if [ -f "${DEPLOY_DIR}/merriam_webster_cache.db" ]; then
    if [ -f "${DB_DIR}/merriam_webster_cache.db" ]; then
        echo -e "${YELLOW}⚠ backend/data/merriam_webster_cache.db 已存在，跳过复制${NC}"
    else
        cp "${DEPLOY_DIR}/merriam_webster_cache.db" "${DB_DIR}/merriam_webster_cache.db"
        chmod 644 "${DB_DIR}/merriam_webster_cache.db"
        echo -e "${GREEN}✓ merriam_webster_cache.db 已复制到 backend/data/merriam_webster_cache.db${NC}"
    fi
fi

# 检查数据库文件完整性
echo ""
echo -e "${BLUE}检查数据库文件完整性...${NC}"

MISSING_DBS=()
for db in "${REQUIRED_DBS[@]}"; do
    if [ ! -f "${DB_DIR}/${db}" ]; then
        MISSING_DBS+=("$db")
    fi
done

if [ ${#MISSING_DBS[@]} -gt 0 ]; then
    echo -e "${YELLOW}⚠ 以下数据库文件缺失:${NC}"
    for db in "${MISSING_DBS[@]}"; do
        echo -e "  - ${db}"
    done
    echo -e "${BLUE}正在创建空的数据库文件...${NC}"
    
    for db in "${MISSING_DBS[@]}"; do
        touch "${DB_DIR}/${db}"
        chmod 644 "${DB_DIR}/${db}"
        echo -e "  ${GREEN}✓${NC} 已创建 ${db}"
    done
    
    echo -e "${YELLOW}注意: data.db 将在首次启动时自动初始化表结构${NC}"
    echo -e "${YELLOW}注意: ecdict.db 需要从词典数据包获取，词典功能暂不可用${NC}"
    echo -e "${YELLOW}注意: merriam_webster_cache.db 将在查询时自动创建表结构${NC}"
else
    echo -e "${GREEN}✓ 所有数据库文件齐全${NC}"
    
    # 显示数据库文件大小
    echo ""
    echo "数据库文件状态:"
    for db in "${REQUIRED_DBS[@]}"; do
        size=$(du -h "${DB_DIR}/${db}" | cut -f1)
        echo -e "  - ${db}: ${size}"
    done
fi

# 启动 Docker 容器
echo ""
echo -e "${BLUE}[4/4] 启动 Docker 容器...${NC}"

if [ ! -f "${DEPLOY_DIR}/docker-compose.yml" ]; then
    echo -e "${RED}错误: 未找到 docker-compose.yml 文件${NC}"
    exit 1
fi

# 检查镜像是否存在
echo "检查 Docker 镜像..."

if ! docker images | grep -q "englishread-all-in-one"; then
    echo -e "${YELLOW}⚠ 未找到 englishread-all-in-one 镜像${NC}"
    echo "  请先构建镜像或加载镜像文件"
    echo "  构建: docker build -t englishread-all-in-one:latest -f Dockerfile ../.."
    echo "  加载: docker load -i englishread-all-in-one-latest.tar"
    exit 1
fi

echo -e "${GREEN}✓ 镜像检查通过${NC}"

# 如果容器已在运行，先停止旧容器
if docker ps -q --filter "name=englishread" | grep -q .; then
    echo "停止旧容器..."
    cd "${DEPLOY_DIR}"
    if docker compose version &> /dev/null; then
        docker compose down
    else
        docker-compose down
    fi
fi

# 启动服务
echo "启动服务..."
cd "${DEPLOY_DIR}"
if docker compose version &> /dev/null; then
    docker compose up -d
else
    docker-compose up -d
fi

# 等待服务启动并验证
echo "等待服务启动..."
sleep 3

if docker ps | grep -q "englishread"; then
    echo -e "${GREEN}✓ 服务启动成功${NC}"
else
    echo -e "${RED}✗ 服务启动可能失败，请检查日志${NC}"
    echo -e "  查看日志: ${YELLOW}docker logs englishread${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "服务访问地址:"
echo -e "  - 前端: ${YELLOW}http://$(hostname -I | awk '{print $1}'):8888${NC}"
echo ""
echo -e "常用命令:"
echo -e "  查看日志:     ${YELLOW}docker logs -f englishread${NC}"
echo -e "  停止服务:     ${YELLOW}docker compose down${NC}"
echo -e "  重启服务:     ${YELLOW}docker compose restart${NC}"
echo -e "  查看容器状态: ${YELLOW}docker ps${NC}"
echo ""
