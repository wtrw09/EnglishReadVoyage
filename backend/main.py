"""英语分级阅读系统后端 - 主应用程序入口点"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.core.constants import API_V1_PREFIX, AUDIO_CACHE_MOUNT
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

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件用于音频缓存
app.mount(AUDIO_CACHE_MOUNT, StaticFiles(directory=settings.CACHE_DIR), name="audio")

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
