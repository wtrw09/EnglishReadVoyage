"""英语分级阅读系统后端 - 主应用程序入口点"""
import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from app.core.config import get_settings
from app.core.constants import API_V1_PREFIX
from app.core.database import init_db
from app.api.v1.router import api_router

# 获取配置设置
settings = get_settings()

# 预加载 spaCy 模型（同步方式，在应用启动前加载）
try:
    from app.utils.sentence_splitter import get_nlp_model
    get_nlp_model()
    print("spaCy 模型预加载完成")
except Exception as e:
    print(f"spaCy 模型预加载失败: {e}")


def setup_logging():
    """配置应用程序日志"""
    # 【重要】在 basicConfig 之前先禁用 SQLAlchemy 日志
    for logger_name in ['sqlalchemy', 'sqlalchemy.engine', 'sqlalchemy.engine.Engine', 
                        'sqlalchemy.pool', 'sqlalchemy.dialects', 'aiosqlite']:
        _logger = logging.getLogger(logger_name)
        _logger.setLevel(logging.WARNING)
        _logger.propagate = False  # 阻止传播到父logger
        _logger.handlers = []

    # 根据环境设置日志级别
    if settings.DEBUG:
        log_level = logging.DEBUG
    elif settings.IS_PRODUCTION:
        log_level = logging.WARNING
    else:
        log_level = logging.INFO

    # 配置根日志记录器
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)  # 输出到标准输出
        ]
    )

    # 设置第三方库日志级别，减少噪音
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    # 再次确保 SQLAlchemy 日志被禁用
    for logger_name in ['sqlalchemy', 'sqlalchemy.engine', 'sqlalchemy.engine.Engine', 
                        'sqlalchemy.pool', 'sqlalchemy.dialects', 'aiosqlite']:
        _logger = logging.getLogger(logger_name)
        _logger.setLevel(logging.WARNING)
        _logger.propagate = False
        _logger.handlers = []

    return logging.getLogger(__name__)

logger = setup_logging()

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
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置 Gzip 压缩（响应大于 1KB 时自动压缩）
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 挂载静态文件用于书籍图片
# 优先使用环境变量或配置中的路径，否则使用默认路径
if settings.BOOKS_DIR:
    BOOKS_DIR = Path(settings.BOOKS_DIR)
else:
    # 默认使用项目目录下的 Books 文件夹
    BOOKS_DIR = Path(__file__).parent / "Books"

if BOOKS_DIR.exists():
    app.mount("/books", StaticFiles(directory=str(BOOKS_DIR)), name="books")
    logger.info(f"Static files mounted: {BOOKS_DIR}")
else:
    logger.warning(f"Books directory not found at {BOOKS_DIR}")

# 挂载单词发音缓存音频目录（放在 data 目录下）
WORD_AUDIO_DIR = Path(settings.BASE_DIR) / "data" / "word_audio"
WORD_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/audio/data/word_audio", StaticFiles(directory=str(WORD_AUDIO_DIR)), name="word_audio")
logger.info(f"Word audio cache mounted: {WORD_AUDIO_DIR}")

# 包含API路由器
app.include_router(api_router, prefix=API_V1_PREFIX)

# 添加请求体验证异常处理器，用于调试 422 错误
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """捕获并记录 Pydantic 验证错误，返回详细错误信息"""
    errors = []
    for error in exc.errors():
        error_info = {
            "loc": error.get("loc"),
            "msg": error.get("msg"),
            "type": error.get("type"),
            "input": error.get("input")
        }
        errors.append(error_info)
    
    logger.error(f"[Validation Error] URL: {request.url.path}")
    logger.error(f"[Validation Error] Errors: {errors}")
    logger.error(f"[Validation Error] Body: {await request.body()}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation Error",
            "errors": errors
        }
    )


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
