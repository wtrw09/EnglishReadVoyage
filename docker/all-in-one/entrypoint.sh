#!/bin/bash
set -e

# EnglishReadVoyage 容器入口脚本
# 负责容器启动时的目录初始化和环境变量准备

# 确保挂载卷的子目录存�?
mkdir -p /app/data/word_audio
mkdir -p /app/Books
mkdir -p /app/.cache

# 若未设置 SECRET_KEY 则自动生�?
if [ -z "$SECRET_KEY" ]; then
    echo "[entrypoint] WARNING: SECRET_KEY not set, generating temporary key"
    export SECRET_KEY=$(openssl rand -hex 32)
fi

# 检�?ecdict.db 状态（用户放在 yml 目录�?backend/data/ 中，Docker 会自动挂载）
if [ -f "/app/data/ecdict.db" ] && [ -s "/app/data/ecdict.db" ]; then
    echo "[entrypoint]   - ecdict.db: ready ($(du -h /app/data/ecdict.db | cut -f1))"
else
    echo "[entrypoint]   - ecdict.db: not found (dictionary will fallback to online API)"
fi

# 打印启动信息
echo "[entrypoint] EnglishReadVoyage 容器启动"
echo "[entrypoint]   - Data dir: /app/data"
echo "[entrypoint]   - Books dir: /app/Books"
echo "[entrypoint]   - Cache dir: /app/.cache"
echo "[entrypoint]   - Debug: ${DEBUG:-False}"
echo "[entrypoint]   - Production: ${IS_PRODUCTION:-True}"

# 切换到主命令（supervisord�?
exec "$@"
