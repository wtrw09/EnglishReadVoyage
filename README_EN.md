# EnglishReadVoyage

[中文版](README.md)

EnglishReadVoyage is a tool that helps English learners improve their English through **enhanced reading**. It supports adding and editing various English reading materials, instant dictionary lookup, and click-to-read functionality, making English learning more efficient and enjoyable.

## Features Overview

### Regular User Features

- **Online Reading**: Browse various English reading materials with pagination support. You can add your own markdown English books or import ready-made English reading materials.
- **Instant Lookup**: Long-press any word to instantly see its definition and pronunciation.
- **Text-to-Speech**: Click to read sentences aloud. Supports multiple TTS engines (Edge-TTS, Doubao, SiliconFlow, MiniMax, Azure, etc.) for reading selected text or entire books.
- **Audiobook Mode**: Supports background playback for hands-free learning.
- **Dictionary**: Supports both offline local dictionary and online dictionary lookup with definitions, example sentences, and pronunciations. Merriam-Webster requires ByteDance registration and API key configuration.
- **Word Bank**: Save new words and review them in one place.
- **Book Grouping**: Create your own categories to organize books.
- **Reading Progress**: Automatically records your reading position with cross-device sync.

### Admin Features

- All regular user features
- **Book Management**: Upload, edit, and delete books.
- **Translation**: Batch generate Chinese translations and Chinese audio for books.
- **User Management**: View user list and manage user status.
- **Settings Management**: Global TTS configuration, dictionary source configuration.
- **Dictionary API Configuration**: Configure API keys for online dictionaries like Merriam-Webster.
- **Voice Cache Management**: Generate and clean up voice caches.

## Build Local Image (Optional)

If you need to build the image yourself (e.g., to customize features), run:

```bash
# Windows (PowerShell recommended)
.\docker\all-in-one\build.ps1

# Linux/Mac
bash docker/all-in-one/build.sh
```

This will produce a `englishreadvoyage:latest` local image for direct use.

You can skip this step and pull a pre-built image directly (see below).

## Quick Start - Docker Deployment

This is the simplest deployment method with no need to install Python or Node.js.

### Prerequisites

- Install [Docker](https://www.docker.com/products/docker-desktop/) (Windows/Mac) or Docker Engine (Linux)
- Ensure Docker service is running

### Deployment Steps

```bash
# 1. Create a directory for config and data (any location, myapp used as example)
mkdir myapp && cd myapp

# 2. Download docker-compose.yml
# Copy docker-compose.yml from the project's docker/all-in-one/ directory

# 3. Modify image source (optional)
# Edit docker-compose.yml and change the image to the CNB registry address to pull from the cloud
# See the "Image Source" note below

# 4. Start service
docker-compose up -d
```

> **Note**: Newer Docker also supports `docker compose` (without hyphen). Both are equivalent.

> **Image Source**: The image name is set in the `image` field of `docker-compose.yml`. Modify it as needed:
> - **Local image**: `image: englishreadvoyage:latest` (build first via `build.ps1`)
> - **CNB image**: `image: registry.cnb.cool/wtrw09/englishreadvoyage:latest` (auto-pull on first run)
>
> Both methods use `docker-compose up -d` — just change one line in the yml file.

On container startup, the following operations are automatically performed:
- Creates data and cache directories
- Initializes database (data.db and auto table creation)
- Starts backend service and frontend Nginx

Data files will be saved in the `backend/` subdirectory of your working directory.

### Access the App

After startup, open browser to access: **http://localhost:8888**

Default admin account:
- Username: `admin`
- Password: `admin`

### Port Configuration

Default port is `8888`. To modify, edit the `docker-compose.yml` in your current directory, change `8888:80` to `your_desired_port:80`:

```yaml
ports:
  - "9999:80"   # Change frontend port to 9999
```

### Common Commands

```bash
# View logs
docker logs -f englishread

# Restart service
docker-compose restart

# Stop service
docker-compose down

# Update image and redeploy (keep data)
docker-compose pull && docker-compose up -d
```

## Offline Dictionary Configuration (Optional)

To enable local dictionary lookup (fast speed, no internet required), follow these steps:

1. Visit [ECDICT Project Release Page](https://github.com/skywind3000/ECDICT/releases), download `ecdict.db` file
2. Rename the downloaded file to `ecdict.db`
3. **First deployment**: Create `backend/data/` directory manually and place `ecdict.db` in it
   ```bash
   mkdir backend/data
   # Then place ecdict.db into the backend/data/ directory
   ```
   **Subsequent deployments**: The `backend/data/` directory already exists, just copy it in
4. Restart container: `docker-compose restart`

If this file is not placed, dictionary lookup will automatically use the online FreeDictionaryAPI, which does not affect other features.

## Android App Usage

### Build from Source

1. Open Android Studio and import `android/` directory
2. Build frontend in `frontend/` directory:

```bash
cd frontend
npm install
npm run build
```

3. Build output will automatically sync to the Android project. Use Android Studio to package the APK.

### Usage Instructions

- Android App loads the frontend page through Capacitor WebView
- Ensure the phone can access the Docker-deployed server address
- On first open, enter the server address and port on the login page to connect.

## HarmonyOS App Usage

### Build from Source

1. Open `harmony/` directory with DevEco Studio
2. Build frontend in `frontend/` directory:

```bash
cd frontend
npm install
npm run harmony:sync
```

3. Use DevEco Studio to package HAP or APP.

### Usage Instructions

- HarmonyOS App uses WebView to load the embedded frontend page (resources packaged in App)
- Supports background audio playback (audiobook mode)
- Audio playback bridging implemented through WebView JavaScript Bridge

## Server Address Configuration

Whether using the web version or mobile App, you can configure the server address and port on the login page (default `http://localhost:8888`). If you deploy Docker on another device, simply enter that device's IP address.

## Data Security

- All user data (reading progress, word bank, etc.) is stored in Docker's `backend/data/` mounted volume
- It is recommended to regularly back up database files in `backend/data/` directory
- For production deployment, it is recommended to set a strong password for `SECRET_KEY` in the `docker-compose.yml` environment

## Repository

The source code is hosted on the following platforms:

- **GitHub**: https://github.com/wtrw09/EnglishReadVoyage
- **Gitee**: https://gitee.com/wtrw09/EnglishReadVoyage
- **CNB.Cool**: https://cnb.cool/wtrw09/EnglishReadVoyage
