from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint, func, Boolean
from typing import List, Optional
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    invitation_code: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    invitation_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    categories: Mapped[List["Category"]] = relationship(back_populates="user")
    progresses: Mapped[List["ReadingProgress"]] = relationship(back_populates="user")

class Book(Base):
    __tablename__ = "books"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String)
    cover_path: Mapped[Optional[str]] = mapped_column(String)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    sync_hash: Mapped[Optional[str]] = mapped_column(String)
    last_sync: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    
    progresses: Mapped[List["ReadingProgress"]] = relationship(back_populates="book", cascade="all, delete-orphan")

class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String)  # 'system' or 'user'
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 分组排序顺序

    user: Mapped[Optional["User"]] = relationship(back_populates="categories")

class BookCategoryRel(Base):
    __tablename__ = "book_category_rel"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("book_id", "user_id", name="uq_book_user"),
    )

class ReadingProgress(Base):
    __tablename__ = "reading_progress"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), primary_key=True)
    current_page: Mapped[int] = mapped_column(Integer, default=1)
    last_read_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    is_completed: Mapped[int] = mapped_column(Integer, default=0)
    is_read: Mapped[int] = mapped_column(Integer, default=0)  # 0=未读, 1=已读

    user: Mapped["User"] = relationship(back_populates="progresses")
    book: Mapped["Book"] = relationship(back_populates="progresses")


class UserSettings(Base):
    """用户设置表，存储用户的个性化配置"""
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    # 词典设置：'local' 表示本地ECDICT，'api' 表示FreeDictionaryAPI
    dictionary_source: Mapped[str] = mapped_column(String, default="local", nullable=False)
    # 朗读服务名称
    tts_service_name: Mapped[Optional[str]] = mapped_column(String, default="kokoro-tts", nullable=True)

    # Kokoro TTS 设置（独立存储）
    kokoro_voice: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    kokoro_voice_zh: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    kokoro_speed: Mapped[Optional[float]] = mapped_column(default=1.0, nullable=True)
    kokoro_api_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # 豆包 TTS 设置（独立存储）
    doubao_voice: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    doubao_voice_zh: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # 中文语音
    doubao_speed: Mapped[Optional[float]] = mapped_column(default=1.0, nullable=True)
    doubao_app_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    doubao_access_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    doubao_resource_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # 硅基流动 TTS 设置（独立存储）
    siliconflow_api_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    siliconflow_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    siliconflow_voice: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    siliconflow_voice_zh: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # 中文语音

    # Edge-TTS 设置（独立存储）
    edge_tts_voice: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    edge_tts_voice_zh: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # 中文语音
    edge_tts_speed: Mapped[Optional[float]] = mapped_column(default=1.0, nullable=True)

    # MiniMax TTS 设置（独立存储）
    minimax_api_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    minimax_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    minimax_voice: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    minimax_voice_zh: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # 中文语音
    minimax_speed: Mapped[Optional[float]] = mapped_column(default=1.0, nullable=True)

    # 音标设置：'uk' 表示英式音标，'us' 表示美式音标
    phonetic_accent: Mapped[str] = mapped_column(String, default="uk", nullable=False)
    # UI设置：隐藏已读书籍状态（按分组存储，JSON格式）
    hide_read_books_map: Mapped[Optional[str]] = mapped_column(String, nullable=True, default="{}")
    # 翻译设置：选择使用的翻译API ID
    selected_translation_api_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 更新时间
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship()


class Vocabulary(Base):
    """生词本表，存储用户收藏的生词"""
    __tablename__ = "vocabulary"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    word: Mapped[str] = mapped_column(String, nullable=False)
    phonetic: Mapped[Optional[str]] = mapped_column(String)
    translation: Mapped[Optional[str]] = mapped_column(String)
    sentence: Mapped[Optional[str]] = mapped_column(String)
    book_name: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "word", "sentence", name="uq_user_word_sentence"),
    )


class AudiobookPlaylist(Base):
    """听书播放列表"""
    __tablename__ = "audiobook_playlists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False, default="默认播放列表")
    play_mode: Mapped[str] = mapped_column(String, default="sequential")  # sequential/random
    sleep_timer: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 分钟
    current_book_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship()
    items: Mapped[List["AudiobookPlaylistItem"]] = relationship(back_populates="playlist", cascade="all, delete-orphan", order_by="AudiobookPlaylistItem.sort_order")


class AudiobookPlaylistItem(Base):
    """播放列表项"""
    __tablename__ = "audiobook_playlist_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("audiobook_playlists.id"), nullable=False)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    playlist: Mapped["AudiobookPlaylist"] = relationship(back_populates="items")
    book: Mapped["Book"] = relationship()


class TranslationAPI(Base):
    """用户翻译API配置表"""
    __tablename__ = "translation_apis"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    app_id: Mapped[str] = mapped_column(String, nullable=False)
    app_key: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
