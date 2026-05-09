"""
书籍ID迁移脚本：将book_id计算方式从"基于文件路径"改为"基于书名"
并将file_path统一为相对路径格式

迁移后：
- book_id = hashlib.md5(book.title.encode()).hexdigest()
- file_path = Books/{title}/{title}.md

使用方法：
  cd backend
  python _migrate_book_ids.py
"""

import hashlib
import shutil
import sqlite3
import sys
from pathlib import Path


def main():
    db_path = Path("data/data.db")
    if not db_path.exists():
        print(f"错误: 数据库文件不存在: {db_path}")
        sys.exit(1)

    # 备份数据库
    backup_path = db_path.with_suffix(".db.backup")
    shutil.copy2(str(db_path), str(backup_path))
    print(f"数据库已备份到: {backup_path}")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # ===== 1. 读取所有书籍 =====
        cursor.execute("SELECT id, title, file_path FROM books ORDER BY title")
        books = cursor.fetchall()
        print(f"\n共找到 {len(books)} 本书籍")

        # ===== 2. 检查同名书籍冲突 =====
        title_counts = {}
        for book_id, title, file_path in books:
            new_id = hashlib.md5(title.encode()).hexdigest()
            if title in title_counts:
                title_counts[title].append((book_id, new_id))
            else:
                title_counts[title] = [(book_id, new_id)]

        conflicts = {k: v for k, v in title_counts.items() if len(v) > 1}
        if conflicts:
            print("\n!!! 发现同名书籍冲突，需要手动处理: !!!")
            for title, entries in conflicts.items():
                print(f"  书名: '{title}'")
                for old_id, new_id in entries:
                    print(f"    - 旧ID: {old_id}, 新ID: {new_id}")
            print("\n同名书籍会产生相同的 book_id，无法自动迁移。")
            print("请手动重命名冲突的书籍后再运行此脚本。")
            conn.close()
            sys.exit(1)

        # ===== 3. 开始迁移（事务） =====
        cursor.execute("BEGIN TRANSACTION")

        migration_map = {}  # old_id -> new_id
        new_id_conflicts = set()

        for book_id, title, file_path in books:
            new_id = hashlib.md5(title.encode()).hexdigest()

            # 检查新ID是否已存在（多个旧ID映射到同一个新ID）
            if new_id in migration_map.values():
                # 检查是否由不同标题导致
                for old_id, old_title in [(b[0], b[1]) for b in books if b[0] == book_id]:
                    pass

            # 检查新ID是否已被其他书籍使用（数据库中已有该ID的记录）
            cursor.execute("SELECT id, title FROM books WHERE id = ?", (new_id,))
            existing = cursor.fetchone()
            if existing and existing[0] != book_id:
                print(f"  警告: 新ID '{new_id[:8]}...' 已被书籍 '{existing[1]}' 使用，冲突: '{title}'")
                new_id_conflicts.add(book_id)
                continue

            migration_map[book_id] = {
                "new_id": new_id,
                "title": title,
                "old_file_path": file_path,
                "new_file_path": f"Books/{title}/{title}.md"
            }

        if new_id_conflicts:
            print(f"\n有 {len(new_id_conflicts)} 本书籍无法迁移（新ID冲突），请手动处理")
            conn.rollback()
            conn.close()
            sys.exit(1)

        print(f"\n准备迁移 {len(migration_map)} 本书籍...")

        # ===== 4. 更新 books 表 =====
        print("\n--- 更新 books 表 ---")
        for old_id, info in migration_map.items():
            new_id = info["new_id"]
            new_path = info["new_file_path"]

            cursor.execute(
                "UPDATE books SET id = ?, file_path = ? WHERE id = ?",
                (new_id, new_path, old_id)
            )
            print(f"  {info['title']}: {old_id[:8]}... -> {new_id[:8]}...  file_path -> {new_path}")
            print(f"    影响行数: {cursor.rowcount}")

        # ===== 5. 更新 book_category_rel 表 =====
        print("\n--- 更新 book_category_rel 表 ---")
        cursor.execute("SELECT COUNT(*) FROM book_category_rel")
        total_rel = cursor.fetchone()[0]
        updated_rel = 0
        for old_id, info in migration_map.items():
            cursor.execute(
                "UPDATE book_category_rel SET book_id = ? WHERE book_id = ?",
                (info["new_id"], old_id)
            )
            updated_rel += cursor.rowcount
        print(f"  更新了 {updated_rel}/{total_rel} 条关联记录")

        # ===== 6. 更新 reading_progress 表 =====
        print("\n--- 更新 reading_progress 表 ---")
        cursor.execute("SELECT COUNT(*) FROM reading_progress")
        total_rp = cursor.fetchone()[0]
        updated_rp = 0
        for old_id, info in migration_map.items():
            cursor.execute(
                "UPDATE reading_progress SET book_id = ? WHERE book_id = ?",
                (info["new_id"], old_id)
            )
            updated_rp += cursor.rowcount
        print(f"  更新了 {updated_rp}/{total_rp} 条阅读进度记录")

        # ===== 7. 更新 audiobook_playlist_items 表 =====
        print("\n--- 更新 audiobook_playlist_items 表 ---")
        cursor.execute("SELECT COUNT(*) FROM audiobook_playlist_items")
        total_api = cursor.fetchone()[0]
        updated_api = 0
        for old_id, info in migration_map.items():
            cursor.execute(
                "UPDATE audiobook_playlist_items SET book_id = ? WHERE book_id = ?",
                (info["new_id"], old_id)
            )
            updated_api += cursor.rowcount
        print(f"  更新了 {updated_api}/{total_api} 条播放列表记录")

        # ===== 8. 删除旧的预编译缓存 =====
        cache_dir = Path(".cache") / "compiled"
        print(f"\n--- 删除旧预编译缓存 ---")
        if cache_dir.exists():
            deleted_count = 0
            for old_id in migration_map:
                old_cache = cache_dir / old_id
                if old_cache.exists():
                    shutil.rmtree(str(old_cache))
                    deleted_count += 1
            print(f"  已删除 {deleted_count} 个旧缓存目录")
        else:
            print(f"  缓存目录不存在: {cache_dir}")

        # ===== 9. 提交事务 =====
        conn.commit()
        print(f"\n✅ 迁移完成！共迁移 {len(migration_map)} 本书籍")
        print(f"   备份文件: {backup_path}")
        print("\n请重启后端服务使新 book_id 生效。")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 迁移失败: {e}")
        print("   已回滚所有更改")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
