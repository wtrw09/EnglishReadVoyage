# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EnglishReadVoyage is a full-stack English graded reading application with:
- **Backend**: FastAPI (Python) - handles authentication, book management, TTS
- **Frontend**: Vue 3 + TypeScript + Vite - user interface
- **Database**: SQLite with SQLAlchemy ORM
- **TTS**: Kokoro text-to-speech service

## Running the Application

### Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
# or: uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at `http://localhost:8000/docs`

Default admin credentials: `admin` / `admin`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173` with API proxy to backend.

### Kokoro TTS Service

TTS requires Kokoro service running on port 8880. Configure via `KOKORO_API_URL` in `.env`.

### Docker Deployment

```bash
# Build and run all-in-one container
cd docker/all-in-one
docker-compose up -d

# Access at http://localhost:8888
```

#### Docker 部署重要注意事项

**1. 镜像构建后需要重新部署**
- 每次修改 Dockerfile、docker-compose.yml、supervisord.conf 等配置文件后，需要重新构建镜像并部署

**2. 服务启动顺序（重要！）**
- supervisord 管理的服务启动顺序由 `priority` 参数控制
- backend 需要先启动（priority=100），nginx 后启动（priority=200）
- 否则 nginx 会因为后端未就绪而返回 502 Bad Gateway

**3. 健康检查配置**
- docker-compose.yml 中配置了 healthcheck
- 使用 `/api/v1/dictionary/status` 作为健康检查端点
- 检查间隔 10s，超时 5s，重试 5 次

**4. 日志查看**
```bash
# 查看后端日志
docker exec <容器名> cat /var/log/supervisor/backend.log

# 实时查看日志
docker exec -it <容器名> tail -f /var/log/supervisor/backend.log
```

## 部署问题排查总结

### 极空间部署常见问题

**1. Edge-TTS 中文音频生成失败**
- 原因：临时文件名使用 `hash(text)`，并发时文件名冲突
- 解决：改用 UUID 生成唯一临时文件名

**2. 翻译服务响应慢**
- 原因：每次请求都创建新的 HTTP 连接
- 解决：使用连接池复用 httpx.AsyncClient

**3. 导出下载速度慢**
- 原因：StreamingResponse 未设置 chunk_size
- 解决：添加 `chunk_size=1024*1024` (1MB)

**4. 翻译失败直接中断**
- 原因：翻译失败时直接 raise Exception
- 解决：添加重试逻辑（5次，每次间隔5秒），失败后跳过该句

**5. Docker 启动后 502 错误**
- 原因：nginx 比 backend 先启动
- 解决：在 supervisord.conf 中设置 priority，backend=100, nginx=200

**6. python-docx 设置表格垂直居中报错**
- 原因：`cell.vertical_alignment = 'center'` 使用了字符串，应该使用枚举值
- 解决：使用 `from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT`，然后用 `cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER`

## Architecture

### Backend Structure (app/)
- `api/v1/endpoints/` - API route handlers (auth, books, tts, audiobook, categories, vocabulary, dictionary, settings)
- `core/` - Configuration, database, security
- `models/` - SQLAlchemy ORM models
- `repositories/` - Data access layer
- `schemas/` - Pydantic request/response models
- `services/` - Business logic (auth, book, tts, audiobook, sync, category, dictionary)

### Database Models
- `users` - User accounts with roles (admin/user)
- `books` - Book metadata cache
- `categories` - Book categorization
- `reading_progress` - Per-user reading progress

### API Endpoints
- `/api/v1/auth/*` - Authentication (login, user management)
- `/api/v1/books/*` - Book listing and details
- `/api/v1/tts/?text=...&voice=...` - Text-to-speech generation
- `/api/v1/categories/*` - Category management
- `/api/v1/vocabulary/*` - Vocabulary/word learning
- `/api/v1/dictionary/*` - Dictionary lookup
- `/api/v1/audiobook/*` - Audiobook playback
- `/api/v1/settings/*` - User settings

## Book Content Structure

Books stored in `Books/Level_[A-Z]/[book_name]/` with markdown files numbered `001_*.md`.

Page breaks: `---` with blank lines before/after

Exclude from TTS: `<!-- ignore -->...<!-- /ignore -->`

## Key Configuration

- Backend: `.env` (SECRET_KEY, KOKORO_API_URL, etc.)
- Frontend: `vite.config.ts` (API proxy setup)

# 程序修改总结或提醒尽量用中文反馈给用户

# Python 库要安装到虚拟环境中

# 前端修改完记得编译一下，看看有没有问题
前端点击展开的菜单列表，支持未选择菜单项点击其他区域时收起

# 编程过程中如果有多种解决方案，不要自行选择，让用户选择

# 如果有什么用户没有表达清楚或则存在歧义的地方，问清楚再执行

# 使用 edge_tts的QPS（每秒请求量）不能超过 1

# 使用 百度翻译api的QPS（每秒请求量）不能超过10