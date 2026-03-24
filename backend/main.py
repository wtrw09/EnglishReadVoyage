"""英语分级阅读系统后端 - 主应用程序入口点"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.core.constants import API_V1_PREFIX
from app.core.database import init_db
from app.api.v1.router import api_router

# 获取配置设置
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用程序生命周期事件"""
    # 启动时：初始化数据库
    await init_db()
    yield
    # 关闭逻辑（如有）可以放在这里

# 创建FastAPI应用程序
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    description="支持TTS的英语分级阅读系统后端API",
    lifespan=lifespan,
    redirect_slashes=False  # 禁用 trailing slash 重定向
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置 Gzip 压缩（响应大于 1KB 时自动压缩）
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 挂载静态文件用于书籍图片
from pathlib import Path
import os

# 优先使用环境变量或配置中的路径，否则使用默认路径
settings = get_settings()
if settings.BOOKS_DIR:
    BOOKS_DIR = Path(settings.BOOKS_DIR)
else:
    # 默认使用项目目录下的 Books 文件夹
    BOOKS_DIR = Path(__file__).parent / "Books"

if BOOKS_DIR.exists():
    app.mount("/books", StaticFiles(directory=str(BOOKS_DIR)), name="books")
    print(f"Static files mounted: {BOOKS_DIR}")
else:
    print(f"Warning: Books directory not found at {BOOKS_DIR}")

# 包含API路由器
app.include_router(api_router, prefix=API_V1_PREFIX)


@app.get("/", tags=["root"])
async def root():
    """根端点 - API健康检查"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
