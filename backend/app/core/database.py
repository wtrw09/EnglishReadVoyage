"""使用SQLAlchemy异步的数据库管理和初始化"""
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.core.config import get_settings
from app.models.database_models import Base, User
from app.core.security import hash_password

settings = get_settings()

# 确保数据库文件存在（避免Docker创建为目录）
def ensure_db_file_exists():
    """如果数据库文件不存在，创建空文件"""
    db_path = Path(settings.DATABASE_PATH)
    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.touch()
        print(f"Created empty database file: {db_path}")

# 在引擎创建前确保文件存在
ensure_db_file_exists()

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    future=True
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    """数据库会话的依赖项"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()



async def init_db():
    """使用表和默认管理员用户初始化数据库"""
    async with engine.begin() as conn:
        # 创建表
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        # 检查管理员是否存在
        result = await session.execute(select(User).where(User.username == "admin"))
        admin = result.scalars().first()
        
        if not admin:
            admin_pass = hash_password("admin")
            new_admin = User(
                username="admin",
                password_hash=admin_pass,
                role="admin",
                is_active=True
            )
            session.add(new_admin)
            await session.commit()
            print("Default admin user created. Username: admin, Password: admin")
    
    print(f"Database initialized at {settings.DATABASE_PATH}")