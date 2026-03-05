"""数据库迁移脚本 - 添加 hide_read_books_map 字段到 user_settings 表"""
import sqlite3
import os
from pathlib import Path

def migrate_database():
    """执行数据库迁移"""
    # 数据库路径
    db_path = Path(__file__).parent / "data.db"
    
    if not db_path.exists():
        print(f"数据库文件不存在: {db_path}")
        print("新数据库将在首次启动时自动创建")
        return
    
    print(f"正在迁移数据库: {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(user_settings)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "hide_read_books_map" in columns:
            print("字段 hide_read_books_map 已存在，跳过迁移")
        else:
            # 添加新字段
            cursor.execute(
                "ALTER TABLE user_settings ADD COLUMN hide_read_books_map VARCHAR DEFAULT '{}'"
            )
            conn.commit()
            print("成功添加字段 hide_read_books_map")
        
        # 验证迁移结果
        cursor.execute("PRAGMA table_info(user_settings)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"\n当前 user_settings 表字段: {', '.join(columns)}")
        
    except sqlite3.Error as e:
        print(f"迁移失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
    
    print("\n数据库迁移完成！")

if __name__ == "__main__":
    migrate_database()
