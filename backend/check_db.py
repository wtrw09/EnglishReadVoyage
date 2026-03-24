import sqlite3
conn = sqlite3.connect('data.db')
cursor = conn.cursor()

# 查找所有分类
cursor.execute('SELECT id, name, user_id FROM categories')
print('All Categories:')
for c in cursor.fetchall():
    print(f'ID: {c[0]}, Name: {c[1]}, UserID: {c[2]}')

# 查看 User 2 的分组
cursor.execute('SELECT id, name, user_id FROM categories WHERE user_id = 2')
print('\nUser 2 Categories:')
cats = cursor.fetchall()
if cats:
    for c in cats:
        print(f'ID: {c[0]}, Name: {c[1]}, UserID: {c[2]}')
else:
    print('User 2 has NO categories')

# 查看 User 2 的书籍关联
cursor.execute('SELECT id, book_id, category_id FROM book_category_rel WHERE user_id = 2')
print('\nUser 2 Book Relations:')
rels = cursor.fetchall()
if rels:
    for r in rels:
        print(f'ID: {r[0]}, BookID: {r[1][:30]}..., CategoryID: {r[2]}')
else:
    print('User 2 has NO book relations')

conn.close()
