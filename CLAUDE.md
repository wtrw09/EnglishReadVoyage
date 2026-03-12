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
