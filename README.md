# EnglishReadVoyage

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English Version](README_EN.md)

EnglishReadVoyage 是一个帮助英语学习者通过**加强阅读**提升英语水平的工具。它提供支持添加、编辑各类英语读物，支持即点即查的词典，原文点读，让英语学习更高效、更有趣。

## 功能概览

### 普通用户功能

- **在线阅读**：浏览各类英文读物，支持分页阅读，需要你自己添加md英语读物，或者导入别人做好的英语读物
- **即点即查**：长按文中任意单词，立即显示释义和音标
- **语音朗读**：通过点击，朗读对应句子。支持多种 TTS 引擎（Edge-TTS、豆包、硅基流动、MiniMax、Azure 等），可朗读选中文本或全文
- **听书模式**：支持后台播放，边听边学
- **词典查询**：支持本地离线词典和在线词典，查询单词释义、例句、音标。韦伯词典，需要字节注册并配置api key.
- **生词本**：收藏生词，集中复习
- **Anki导出**：将生词导出为 `.apkg` 格式，可直接导入 Anki 记忆卡进行学习。卡片正面为单词所在句子（目标单词加粗标红），背面为句子翻译和单词释义
- **书籍分组**：自主创建分类，整理书籍
- **阅读进度**：自动记录阅读位置，跨设备同步

### 管理员功能

- 普通用户的所有功能
- **书籍管理**：上传、编辑、删除书籍
- **翻译补充**：批量生成书籍的中文翻译和中文语音
- **用户管理**：查看用户列表、管理用户状态
- **设置管理**：全局 TTS 配置、词典源配置
- **词典 API 配置**：配置韦氏词典等在线词典的 API Key
- **语音缓存管理**：生成和清理语音缓存

## 书籍导入格式要求

系统支持两种书籍导入方式：**Markdown/ZIP 导入**和 **MP3+LRC 导入**。

### 常规导入（Markdown/ZIP）

支持上传 `.md` 文件或包含完整书籍结构的 `.zip` 包。ZIP 包目录结构示例：

```
All_About_Coyotes.zip
└── All_About_Coyotes/
    ├── All_About_Coyotes.md        # 书籍内容（Markdown格式）
    ├── assets/                     # 图片资源
    │   ├── cover.jpg               # 封面图
    │   └── image_01.jpg
    └── audio/                      # 语音文件
        ├── sentences.json          # 句子映射
        └── a1b2c3d4...mp3
```

### MP3+LRC 书籍导入

适用于已有英语教材配套音频和字幕（如新概念英语、英语听力教材等）。

#### 文件要求

- 将 **MP3 音频**和 **LRC 双语歌词** 打包为 `.zip` 文件上传
- MP3 和 LRC 必须**同名配对**（仅扩展名不同）
- 每个配对 = 1 本书
- 一个 ZIP 可包含多个配对（批量导入）

#### ZIP 目录示例

```
my_books.zip
├── Lesson_01.mp3
├── Lesson_01.lrc
├── Lesson_02.mp3
├── Lesson_02.lrc
└── Lesson_03.mp3
   （Lesson_03.lrc 缺失，此配对无效）
```

#### LRC 格式要求（严格）

LRC 文件每行格式必须为：

```
[mm:ss.xx]English sentence|中文翻译
```

**⚠ 关键规则：**

- 使用 **`|`（竖线）** 分隔英文和中文，**不能用** `/`、`\t`（Tab）或其他符号
- 竖线**左边**必须是英文原文
- 竖线**右边**是对应的中文翻译
- 每行时间戳格式为 `[mm:ss.xx]`（分:秒.百分秒）

**正确示例**（来自新概念英语 NCE1）：

```
[00:05.61]Excuse me!|打扰一下！
[00:10.80]Whose handbag is it?|这是谁的手提包？
[00:15.11]Excuse me!|打扰一下！
[00:16.66]Yes?|什么事？
[00:18.26]Is this your handbag?|这是你的手提包吗？
[00:21.44]Pardon?|什么？请再说一遍。
[00:23.17]Is this your handbag?|这是你的手提包吗？
[00:26.73]Yes it is.|是的，它是。
[00:29.49]Thank you very much.|非常感谢您。
```

**错误示例**：

```lrc
[00:05.61]Excuse me!/打扰一下！       # ❌ 不能使用 / 分隔
[00:10.80]Excuse me!\t打扰一下！        # ❌ 不能使用 Tab 分隔
[00:15.11]Excuse me!                     # ⚠ 无|分隔符，中文翻译会缺失
```

#### 导入后说明

- 仅英文音频会被切割保存，中文翻译从 LRC 提取后存入 `sentences.json` 的 `translation` 字段
- 中文语音默认为空，导入完成后会提示用户通过「补充中文语音」功能生成
- MP3 内嵌封面图（APIC 帧）会自动提取作为书籍封面

## 安装部署服务后端

本项目提供 Docker 镜像部署方式，无需安装 Python 或 Node.js。

### Docker 镜像获取

#### 本地构建镜像（可选）

如果你需要自行构建镜像（如自定义功能），可以运行以下命令构建本地镜像：

```bash
# Windows（推荐使用 PowerShell）
.\docker\all-in-one\build.ps1

# Linux/Mac
bash docker/all-in-one/build.sh
```

构建完成后会生成 `englishreadvoyage:latest` 本地镜像，后续可直接使用。

也可以跳过此步骤，直接从网上拉取已构建好的镜像（见下文）。
#### 从CNB拉取镜像

如果不想本地构建，可以直接从 CNB（cnb.cool）拉取已构建好的镜像：

```bash
# 拉取最新镜像
docker pull docker.cnb.cool/wtrw09/englishreadvoyage:latest
```

镜像拉取完成后，参照下方[Docker 部署启动](#docker-部署启动)步骤启动即可。

### Docker 部署启动

这是最简单的部署方式，无需安装 Python 或 Node.js。

### 前置条件

- 安装 [Docker](https://www.docker.com/products/docker-desktop/)（Windows/Mac）或 Docker Engine（Linux）
- 确保 Docker 服务正常运行

### 部署步骤

```bash
# 1. 创建一个目录存放配置和数据（位置随意，以 myapp 为例）
mkdir myapp && cd myapp

# 2. 下载 docker-compose.yml
# 从项目 docker/all-in-one/ 目录复制 docker-compose.yml 到当前目录

# 3. 修改镜像来源（可选）
# 编辑 docker-compose.yml，将 image 改为 CNB 镜像地址即可从网上拉取
# 详见下方的「镜像来源说明」

# 4. 启动服务
docker-compose up -d
```

> **注意**：新版 Docker 也支持不带短横线的 `docker compose` 命令，两者等价，任选其一。

> **镜像来源说明**：镜像名在 `docker-compose.yml` 的 `image` 字段设置，可根据实际需要修改：
> - 使用**本地镜像**：`image: englishreadvoyage:latest`（需先通过 `build.ps1` 构建）
> - 使用**CNB 镜像**：`image: registry.cnb.cool/wtrw09/englishreadvoyage:latest`（首次自动拉取）
>
> 两种方式都是用 `docker-compose up -d` 启动，只需修改 yml 中的一行即可。

容器启动后会自动完成以下操作：
- 创建数据目录和缓存目录
- 初始化数据库（data.db 和自动建表）
- 启动后端服务和前端 Nginx

数据文件将保存在运行目录下的 `backend/` 子目录中。

#### 端口配置

默认端口为 `8888`。如需修改，编辑当前目录下的 `docker-compose.yml`，将 `8888:80` 改为 `你想要的端口:80`：

```yaml
ports:
  - "9999:80"   # 将前端端口改为 9999
```

#### 常用命令

```bash
# 查看日志
docker logs -f englishread

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 更新镜像后重新部署（保留数据）
docker-compose pull && docker-compose up -d
```

## 客户端访问

### 网页访问

启动后打开浏览器访问：**http://localhost:8888**

默认管理员账号：
- 用户名：`admin`
- 密码：`admin`

### App 客户端

#### Android App 使用

从源码构建：

1. 打开 Android Studio，导入 `android/` 目录
2. 在 `frontend/` 目录下构建前端产物：

```bash
cd frontend
npm install
npm run build
```

3. 构建产物会自动同步到 Android 项目，用 Android Studio 打包 APK 即可

使用说明：

- Android App 通过 Capacitor WebView 加载前端页面
- 确保手机上可以访问 Docker 部署的服务器地址
- 首次打开 App 后，在登录页面输入服务器地址和端口即可连接

#### 鸿蒙 App 使用

从源码构建：

1. 使用 DevEco Studio 打开 `harmony/` 目录
2. 在 `frontend/` 目录下构建前端产物：

```bash
cd frontend
npm install
npm run harmony:sync
```

3. 使用 DevEco Studio 打包 HAP 或 APP 即可

使用说明：

- 鸿蒙 App 使用 WebView 加载内嵌的前端页面（资源打包在 App 内）
- 支持后台音频播放（听书模式）
- 通过 WebView JavaScript Bridge 实现音频播放桥接
## 必要配置
### 百度翻译api
主要用于把英文翻译成中文，是免费机器翻译，个人使用额度足够。目前没有找到其他更好的免费翻译，只配置这个了。
## 可选配置
### 韦氏词典配置（可选）

韦氏词典（Merriam-Webster）提供更权威、更详细的英文释义。如需启用：

1. **获取 API Key**：访问 [Merriam-Webster Developer Portal](https://www.dictionaryapi.com/register/index)，注册账号后申请以下两个 API Key（完全免费）：
   - **Learner's Dictionary API Key**：主词典，提供详细释义和例句
   - **Thesaurus API Key**：同义词词典，提供同义词/反义词（可选）
2. **配置位置**：在管理员界面的「词典设置」中分别填入两个 API Key
3. **配置优势**：相比默认的 FreeDictionaryAPI，韦氏词典提供：
   - 更权威的英文释义
   - 更丰富的例句
   - 详细的词源信息
   - 准确的同义词/反义词（需 Thesaurus API Key）

### 离线词典配置（可选）

如需本地词典查询（速度快、无需联网），可按以下步骤配置：

1. 访问 [ECDICT 项目发布页](https://github.com/skywind3000/ECDICT/releases)，下载 `ecdict.db` 文件
2. 将下载的文件重命名为 `ecdict.db`
3. **首次部署**：需手动创建 `backend/data/` 目录，将 `ecdict.db` 放入其中
   ```bash
   mkdir backend/data
   # 然后将 ecdict.db 放入 backend/data/ 目录
   ```
   **非首次部署**：`backend/data/` 目录已存在，直接复制进去即可
4. 重启容器：`docker compose restart`

如果没有放置该文件，词典查询会自动使用在线 FreeDictionaryAPI，不影响其他功能。

### 语音服务配置（可选）

项目默认使用微软 [Edge-TTS](https://github.com/rany2/edge-tts)，完全免费且朗读标准，是开箱即用的最佳选择。

如需更高质量或更多音色，可配置以下付费语音服务：

| 服务 | 类型 | 特点 |
|------|------|------|
| **Azure TTS** | 微软 Neural | 高质量神经网络语音，音色丰富 |
| **豆包 TTS** | 字节在线 | 中文语音自然，支持情感 |
| **MiniMax TTS** | 国内在线 | 多语言支持，有免费额度 |
| **硅基流动 TTS** | 国内在线 | 多款模型可选 |
| **Kokoro TTS** | 本地模型 | 需本地部署，音质优秀 |

配置方式：在管理员界面的「语音设置」中选择服务并填入对应 API Key。

## 服务器地址配置

无论是网页端还是手机 App，登录页面都可以配置服务器地址和端口（默认 `http://localhost:8888`）。如果你将 Docker 部署在另一台设备上，输入该设备的 IP 地址即可。

## 数据安全

- 所有用户数据（阅读进度、生词本等）存储在 Docker 的 `backend/data/` 挂载卷中
- 建议定期备份 `backend/data/` 目录下的数据库文件
- 生产环境部署时，建议在 `docker-compose.yml` 的 environment 中设置 `SECRET_KEY` 为强密码

## 代码仓库

本项目代码托管在以下平台，可按需访问：

- **GitHub**：https://github.com/wtrw09/EnglishReadVoyage
- **Gitee**：https://gitee.com/wtrw09/EnglishReadVoyage
- **CNB.Cool**：https://cnb.cool/wtrw09/EnglishReadVoyage
