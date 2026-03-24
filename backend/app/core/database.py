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

        # 迁移：添加硅基流动TTS字段（如果不存在）
        from sqlalchemy import text
        try:
            # 检查列是否存在
            result = await conn.execute(text("PRAGMA table_info(user_settings)"))
            columns = [row[1] for row in result.fetchall()]

            # 添加硅基流动字段
            if 'siliconflow_api_key' not in columns:
                await conn.execute(text("ALTER TABLE user_settings ADD COLUMN siliconflow_api_key VARCHAR"))
                print("Added column: siliconflow_api_key")
            if 'siliconflow_model' not in columns:
                await conn.execute(text("ALTER TABLE user_settings ADD COLUMN siliconflow_model VARCHAR"))
                print("Added column: siliconflow_model")
            if 'siliconflow_voice' not in columns:
                await conn.execute(text("ALTER TABLE user_settings ADD COLUMN siliconflow_voice VARCHAR"))
                print("Added column: siliconflow_voice")

            # 添加 Edge-TTS 字段
            if 'edge_tts_voice' not in columns:
                await conn.execute(text("ALTER TABLE user_settings ADD COLUMN edge_tts_voice VARCHAR"))
                print("Added column: edge_tts_voice")
            if 'edge_tts_speed' not in columns:
                await conn.execute(text("ALTER TABLE user_settings ADD COLUMN edge_tts_speed FLOAT"))
                print("Added column: edge_tts_speed")

            # 添加翻译设置字段
            if 'selected_translation_api_id' not in columns:
                await conn.execute(text("ALTER TABLE user_settings ADD COLUMN selected_translation_api_id INTEGER"))
                print("Added column: selected_translation_api_id")

            # 添加中文语音字段
            if 'kokoro_voice_zh' not in columns:
                await conn.execute(text("ALTER TABLE user_settings ADD COLUMN kokoro_voice_zh VARCHAR"))
                print("Added column: kokoro_voice_zh")

            # 添加豆包中文语音字段
            if 'doubao_voice_zh' not in columns:
                await conn.execute(text("ALTER TABLE user_settings ADD COLUMN doubao_voice_zh VARCHAR"))
                print("Added column: doubao_voice_zh")

            # 迁移：允许 book_category_rel 的 category_id 为 NULL（用于"未分组"功能）
            result = await conn.execute(text("PRAGMA table_info(book_category_rel)"))
            rel_columns = {row[1]: row for row in result.fetchall()}
            if 'category_id' in rel_columns:
                col_info = rel_columns['category_id']
                # col_info[4] 是 notnull 标志 (0=nullable, 1=not null)
                if col_info[4] == 1:  # 当前不允许 NULL，需要迁移
                    print("Starting migration: book_category_rel.category_id to allow NULL...")
                    # SQLite 不支持直接修改列，需要重建表
                    # 1. 创建新表（允许 NULL）
                    await conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS book_category_rel_new (
                            book_id VARCHAR NOT NULL,
                            category_id INTEGER,
                            user_id INTEGER NOT NULL,
                            FOREIGN KEY (book_id) REFERENCES books (id),
                            FOREIGN KEY (category_id) REFERENCES categories (id),
                            FOREIGN KEY (user_id) REFERENCES users (id),
                            UNIQUE (book_id, category_id, user_id)
                        )
                    """))
                    # 2. 复制数据
                    await conn.execute(text("""
                        INSERT INTO book_category_rel_new (book_id, category_id, user_id)
                        SELECT book_id, category_id, user_id FROM book_category_rel
                    """))
                    # 3. 删除旧表
                    await conn.execute(text("DROP TABLE book_category_rel"))
                    # 4. 重命名新表
                    await conn.execute(text("ALTER TABLE book_category_rel_new RENAME TO book_category_rel"))
                    print("Migration completed: book_category_rel.category_id now allows NULL")
                else:
                    print("Migration check: book_category_rel.category_id already allows NULL")
        except Exception as e:
            print(f"Migration warning (may be expected for new databases): {e}")
    
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