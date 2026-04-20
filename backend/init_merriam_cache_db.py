#!/usr/bin/env python3
"""初始化韦氏词典离线缓存数据库"""

import sys
import os

# 添加 backend 目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.merriam_webster_cache_service import get_cache_service, CACHE_DB_PATH


def init_cache_db():
    """初始化缓存数据库"""
    print("=" * 50)
    print("韦氏词典离线缓存数据库初始化")
    print("=" * 50)

    cache_service = get_cache_service()

    print(f"\n数据库路径: {CACHE_DB_PATH}")

    # 初始化表
    cache_service._init_db()
    print("数据库表初始化完成!")

    # 检查表是否存在
    import sqlite3
    conn = cache_service._get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='merriam_webster_cache'")
        result = cursor.fetchone()
        if result:
            print(f"表 '{result[0]}' 已存在")

            # 统计缓存数量
            cursor.execute("SELECT COUNT(*) FROM merriam_webster_cache")
            count = cursor.fetchone()[0]
            print(f"当前缓存单词数: {count}")

            # 显示表结构
            cursor.execute("PRAGMA table_info(merriam_webster_cache)")
            columns = cursor.fetchall()
            print("\n表结构:")
            for col in columns:
                print(f"  - {col[1]}: {col[2]}")
        else:
            print("表创建失败!")
    finally:
        conn.close()

    print("\n" + "=" * 50)
    print("初始化完成!")
    print("=" * 50)


if __name__ == "__main__":
    init_cache_db()
