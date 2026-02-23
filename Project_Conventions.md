# 英语分级阅读系统：项目命名与内容规范手册

本手册旨在定义书籍资源的目录结构、文件命名及 Markdown 内部标记规则，确保后端解析器能够准确处理。

## 1. 目录层级规范
所有书籍资源统一存放在根目录的 `Books/` 文件夹下。建议采用以下三级结构：

```text
Books/
└── Level_[A-Z]/           # 第一层：阅读等级（如 Level_E, Level_F）
    └── [book_name]/       # 第二层：书籍名称（使用英文/下划线）
        ├── [index]_[name].md  # 第三层：Markdown 正文文件
        └── assets/        # 可选：存放该书的本地图片、音频资源
```

### 示例路径：
`Books/Level_E/all_about_coyotes/001_all_about_coyotes.md`

## 2. 文件命名规范
- **文件夹名**：使用小写英文，单词间用下划线 `_` 连接（例如：`all_about_coyotes`）。
- **Markdown 文件名**：`[编号]_[书名].md`。
    - 编号必须是三位数字（如 `001`），确保排序正确。
    - 示例：`001_all_about_coyotes.md`

## 3. Markdown 内容标记规范

### 3.1 分页标识
- 使用标准 Markdown 水平分割线 `---` 进行物理分页。
- **注意**：`---` 前后需各保留一行空行。

### 3.2 朗读控制（黑白名单）
- **默认朗读范围**：后端默认解析并朗读所有 `<p>`（段落）、`<li>`（列表项）以及 `<h1>` 至 `<h6>`（标题）。
- **显式忽略标记**：使用 HTML 注释成对包裹不需要朗读的块。
    - **开始标记**：`<!-- ignore -->`
    - **结束标记**：`<!-- /ignore -->`
- **示例用法**：
    ```markdown
    <!-- ignore -->
    # Photo Credits
    Front cover: © Tom & Pat Leeson
    <!-- /ignore -->
    ```

## 4. 资源引用规范
- **外部图片**：直接使用 Markdown 链接。
- **本地图片**：存放在该书目录下的 `assets/` 文件夹中，Markdown 中使用相对路径引用。
    - 示例：`![image](./assets/cover.jpg)`

---
