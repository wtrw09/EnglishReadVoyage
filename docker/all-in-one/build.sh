#!/bin/bash
# EnglishReadVoyage 单镜像合并构建脚本
# 支持 AMD64 和 ARM64 架构
# 将前后端合并到一个 Docker 镜像中，简化部署

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 切换到项目根目录
cd "$PROJECT_ROOT"
echo "项目根目录: $PROJECT_ROOT"

# 镜像名称
IMAGE_NAME="englishreadvoyage"

echo "========================================"
echo "EnglishReadVoyage 单镜像合并构建脚本"
echo "========================================"
echo "此脚本将前后端合并到一个 Docker 镜像中"
echo ""

# 交互式选择架构
echo "请选择目标架构:"
echo "  [1] AMD64 (x86_64) - 适用于 Intel/AMD 处理器的服务器/PC"
echo "  [2] ARM64 (aarch64) - 适用于 Apple Silicon Mac, ARM 服务器"
echo "  [3] 同时构建 AMD64 和 ARM64"
echo "  [0] 退出"

read -p "请输入选项 (0-3): " arch_choice

ARCHITECTURE="amd64"
case "$arch_choice" in
    1) ARCHITECTURE="amd64" ;;
    2) ARCHITECTURE="arm64" ;;
    3) ARCHITECTURE="all" ;;
    0) echo "已退出"; exit 0 ;;
    *) echo "无效选项，默认使用 AMD64"; ARCHITECTURE="amd64" ;;
esac

# 交互式输入镜像标签
read -p "请输入镜像标签 (默认: latest): " tag_input
TAG="${tag_input:-latest}"

# 完整镜像标签
IMAGE_TAG="${IMAGE_NAME}:${TAG}"
PUSH=false

# 确认信息
echo ""
echo "========================================"
echo "构建配置确认:"
echo "========================================"
echo "目标架构: $ARCHITECTURE"
echo "镜像名称: $IMAGE_NAME"
echo "镜像标签: $TAG"
echo "完整镜像名: $IMAGE_TAG"
echo "========================================"

read -p "确认开始构建? (Y/n): " confirm
if [[ "$confirm" == "n" || "$confirm" == "N" ]]; then
    echo "已取消构建"
    exit 0
fi

# 检查 Docker 是否安装
if ! command -v docker &>/dev/null; then
    echo "错误: Docker 未安装或未添加到 PATH" >&2
    exit 1
fi

# 检查 Docker 是否运行
if ! docker info &>/dev/null; then
    echo "错误: Docker 服务未运行，请启动 Docker" >&2
    exit 1
fi

# 设置平台参数
use_buildx=false
if [ "$ARCHITECTURE" = "amd64" ]; then
    platforms="linux/amd64"
    use_buildx=false
    echo ""
    echo "[1/2] AMD64 构建 - 使用传统 docker build"
elif [ "$ARCHITECTURE" = "arm64" ]; then
    platforms="linux/arm64"
    use_buildx=true
    echo ""
    echo "[1/2] ARM64 构建 - 使用 docker buildx"
    echo "使用 desktop-linux 构建器"
elif [ "$ARCHITECTURE" = "all" ]; then
    platforms="linux/amd64,linux/arm64"
    use_buildx=true
    echo ""
    echo "[1/2] 多架构构建 - 使用 docker buildx"
    echo "使用 desktop-linux 构建器"
fi

echo "目标平台: $platforms"

# 检查本地镜像是否存在
check_local_image() {
    local image_name="$1"
    if docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${image_name}$"; then
        return 0
    else
        return 1
    fi
}

# 导出镜像功能
export_image() {
    local image_tag="$1"
    local output_file="$2"
    echo ""
    echo "导出镜像: $image_tag"
    docker save "$image_tag" -o "$output_file"
    if [ $? -eq 0 ]; then
        local file_size=$(du -h "$output_file" | cut -f1)
        echo "✓ 导出成功！文件: $output_file, 大小: $file_size"
        return 0
    else
        echo "✗ 导出失败" >&2
        return 1
    fi
}

# 根据架构获取本地镜像信息
get_local_images() {
    local arch="$1"
    if [ "$arch" = "arm64" ]; then
        PYTHON_IMAGE="python:3.13-slim-arm64"
        NODE_IMAGE="node:22-alpine-arm64"
        NGINX_IMAGE="nginx:alpine-arm64"
    else
        PYTHON_IMAGE="python:3.13-slim-amd64"
        NODE_IMAGE="node:22-alpine-amd64"
        NGINX_IMAGE="nginx:alpine-amd64"
    fi

    all_exists=true
    for img in "$PYTHON_IMAGE" "$NODE_IMAGE" "$NGINX_IMAGE"; do
        if check_local_image "$img"; then
            echo "✓ 本地镜像存在: $img"
        else
            echo "✗ 本地镜像不存在: $img"
            all_exists=false
        fi
    done

    if [ "$all_exists" = false ]; then
        echo ""
        echo "警告: 部分基础镜像不存在于本地，构建时可能会尝试从网络拉取。"
        echo "如需离线构建，请先执行以下命令拉取镜像:"
        echo "  docker pull $PYTHON_IMAGE"
        echo "  docker pull $NODE_IMAGE"
        echo "  docker pull $NGINX_IMAGE"
        echo ""
    fi
}

# 获取本地镜像配置
get_local_images "$ARCHITECTURE"

# 构建镜像
echo ""
echo "[2/2] 构建合并镜像..."

# 处理 "all" 架构：分别构建两个架构，加载到本地（buildx --load 不支持多架构清单）
if [ "$ARCHITECTURE" = "all" ]; then
    TAG="latest"
    echo "多架构本地模式：分别构建两个架构镜像"

    # 先构建 AMD64
    echo ""
    echo "=== 构建 AMD64 镜像 ==="
    amd64_args=(
        "buildx" "build"
        "--platform" "linux/amd64"
        "--tag" "englishreadvoyage:latest"
        "--file" "docker/all-in-one/Dockerfile"
        "--pull=false"
        "--load"
        "."
    )
    # 添加 build-arg
    if [ -n "$PYTHON_IMAGE" ]; then amd64_args+=("--build-arg" "PYTHON_IMAGE=$PYTHON_IMAGE"); fi
    if [ -n "$NODE_IMAGE" ]; then amd64_args+=("--build-arg" "NODE_IMAGE=$NODE_IMAGE"); fi
    if [ -n "$NGINX_IMAGE" ]; then amd64_args+=("--build-arg" "NGINX_IMAGE=$NGINX_IMAGE"); fi

    echo "执行: docker ${amd64_args[*]}"
    docker "${amd64_args[@]}"
    echo "✓ AMD64 镜像构建成功: englishreadvoyage:latest"

    # 再构建 ARM64
    echo ""
    echo "=== 构建 ARM64 镜像 ==="
    arm64_args=(
        "buildx" "build"
        "--platform" "linux/arm64"
        "--tag" "englishreadvoyage:latest"
        "--file" "docker/all-in-one/Dockerfile"
        "--pull=false"
        "--load"
        "."
        "--build-arg" "PYTHON_IMAGE=python:3.13-slim-arm64"
        "--build-arg" "NODE_IMAGE=node:22-alpine-arm64"
        "--build-arg" "NGINX_IMAGE=nginx:alpine-arm64"
    )

    echo "执行: docker ${arm64_args[*]}"
    docker "${arm64_args[@]}"
    echo "✓ ARM64 镜像构建成功: englishreadvoyage:latest"

    # 输出结果
    echo ""
    echo "========================================"
    echo "构建完成！"
    echo "========================================"
    echo "镜像列表:"
    docker images englishreadvoyage --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}"

    # 询问是否导出
    echo ""
    echo "是否导出镜像? [1] AMD64 [2] ARM64 [3] 两者 [N] 跳过"
    read -p "请输入选项: " export_choice
    case "$export_choice" in
        1) export_image "englishreadvoyage:latest" "englishreadvoyage-amd64-latest.tar" ;;
        2) export_image "englishreadvoyage:latest" "englishreadvoyage-arm64-latest.tar" ;;
        3)
            export_image "englishreadvoyage:latest" "englishreadvoyage-amd64-latest.tar"
            export_image "englishreadvoyage:latest" "englishreadvoyage-arm64-latest.tar"
            ;;
    esac

    exit 0
fi

# 单架构构建
echo "镜像: englishreadvoyage:latest"
echo "Dockerfile: docker/all-in-one/Dockerfile"
echo "构建上下文: 项目根目录"

# 准备构建参数
build_args=()

if [ "$use_buildx" = true ]; then
    # ARM64/多架构构建 - 使用 buildx
    build_args=(
        "buildx" "build"
        "--platform" "$platforms"
        "--tag" "$IMAGE_TAG"
        "--file" "docker/all-in-one/Dockerfile"
        "--pull=false"
    )
    # 仅在单架构时使用 --load
    if [ "$ARCHITECTURE" != "all" ]; then
        build_args+=("--load")
    fi
    echo "使用 buildx 构建"
else
    # AMD64 构建 - 使用传统 docker build
    build_args=(
        "build"
        "--tag" "$IMAGE_TAG"
        "--file" "docker/all-in-one/Dockerfile"
        "--pull=false"
    )
    echo "使用传统 docker build"
fi

# 添加本地镜像 build-arg
if [ -n "$PYTHON_IMAGE" ]; then
    build_args+=("--build-arg" "PYTHON_IMAGE=$PYTHON_IMAGE")
    echo "使用 Python 镜像: $PYTHON_IMAGE"
fi
if [ -n "$NODE_IMAGE" ]; then
    build_args+=("--build-arg" "NODE_IMAGE=$NODE_IMAGE")
    echo "使用 Node 镜像: $NODE_IMAGE"
fi
if [ -n "$NGINX_IMAGE" ]; then
    build_args+=("--build-arg" "NGINX_IMAGE=$NGINX_IMAGE")
    echo "使用 Nginx 镜像: $NGINX_IMAGE"
fi

# 添加上下文路径（项目根目录）
build_args+=(".")

echo "执行命令: docker ${build_args[*]}"
echo ""

docker "${build_args[@]}"

if [ $? -ne 0 ]; then
    echo "错误: 镜像构建失败: $IMAGE_TAG" >&2
    exit 1
fi

echo ""
echo "✓ 镜像构建成功: $IMAGE_TAG"

# 构建完成信息
echo ""
echo "========================================"
echo "构建完成！"
echo "========================================"
echo "镜像: $IMAGE_TAG"
docker images englishreadvoyage --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | head -2

# 导出镜像选项
echo ""
echo "是否导出镜像到文件?"
echo "  [1] 是，导出镜像"
echo "  [2] 否，跳过导出"

read -p "请输入选项 (1-2): " export_choice

if [ "$export_choice" = "1" ]; then
    echo ""
    echo "=== 导出镜像 ==="
    output_file="englishreadvoyage-${ARCHITECTURE}-${TAG}.tar"
    export_image "englishreadvoyage:latest" "$output_file"
fi

# 使用说明
echo ""
echo "========================================"
echo "使用说明"
echo "========================================"
echo ""
echo "1. 使用 docker-compose 运行:"
echo "   cd docker/all-in-one"
echo "   docker compose up -d"
echo ""
echo "2. 直接使用 docker 运行:"
echo '   docker run -d \'
echo '     -p 8888:80 \'
echo '     -v ${PWD}/backend/data:/app/data \'
echo '     -v ${PWD}/backend/Books:/app/Books \'
echo '     --name englishread \'
echo '     -e IS_PRODUCTION=True \'
echo '     englishreadvoyage:latest'
echo ""
echo "3. 访问应用:"
echo "   打开浏览器访问 http://localhost:8888"
echo ""
echo "========================================"
