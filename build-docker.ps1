# EnglishReadVoyage Docker 镜像构建脚本
# 支持 AMD64 和 ARM64 架构

# 设置错误时停止
$ErrorActionPreference = "Stop"

# 镜像名称
$FrontendImage = "englishread-frontend"
$BackendImage = "englishread-backend"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "EnglishReadVoyage Docker 镜像构建脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 交互式选择架构
Write-Host ""
Write-Host "请选择目标架构:" -ForegroundColor Green
Write-Host "  [1] AMD64 (x86_64) - 适用于 Intel/AMD 处理器的服务器/PC" -ForegroundColor White
Write-Host "  [2] ARM64 (aarch64) - 适用于 Apple Silicon Mac, ARM 服务器" -ForegroundColor White
Write-Host "  [3] 同时构建 AMD64 和 ARM64" -ForegroundColor White
Write-Host "  [0] 退出" -ForegroundColor Red

$archChoice = Read-Host "请输入选项 (0-3)"

$Architecture = "amd64"
if ($archChoice -eq "1") {
    $Architecture = "amd64"
} elseif ($archChoice -eq "2") {
    $Architecture = "arm64"
} elseif ($archChoice -eq "3") {
    $Architecture = "all"
} elseif ($archChoice -eq "0") {
    Write-Host "已退出" -ForegroundColor Red
    exit 0
} else {
    Write-Host "无效选项，默认使用 AMD64" -ForegroundColor Yellow
    $Architecture = "amd64"
}

# 交互式选择构建内容
Write-Host ""
Write-Host "请选择要构建的镜像:" -ForegroundColor Green
Write-Host "  [1] 前端 + 后端 (全部)" -ForegroundColor White
Write-Host "  [2] 仅前端" -ForegroundColor White
Write-Host "  [3] 仅后端" -ForegroundColor White

$buildChoice = Read-Host "请输入选项 (1-3)"

$BuildFrontend = $true
$BuildBackend = $true

if ($buildChoice -eq "1") {
    $BuildFrontend = $true
    $BuildBackend = $true
} elseif ($buildChoice -eq "2") {
    $BuildFrontend = $true
    $BuildBackend = $false
} elseif ($buildChoice -eq "3") {
    $BuildFrontend = $false
    $BuildBackend = $true
} else {
    Write-Host "无效选项，默认构建全部" -ForegroundColor Yellow
    $BuildFrontend = $true
    $BuildBackend = $true
}

# 交互式输入镜像标签
$defaultTag = "latest"
$TagInput = Read-Host "请输入镜像标签 (默认: $defaultTag)"
$Tag = if ($TagInput) { $TagInput } else { $defaultTag }

# 交互式输入仓库地址
Write-Host ""
Write-Host "是否推送到远程仓库?" -ForegroundColor Green
Write-Host "  [1] 仅构建本地镜像" -ForegroundColor White
Write-Host "  [2] 推送到 Docker Hub" -ForegroundColor White
Write-Host "  [3] 推送到其他仓库" -ForegroundColor White

$pushChoice = Read-Host "请输入选项 (1-3)"

$Push = $false
$Registry = ""

if ($pushChoice -eq "1") {
    $Push = $false
    Write-Host "将仅构建本地镜像" -ForegroundColor Gray
} elseif ($pushChoice -eq "2") {
    $Push = $true
    $dockerHubUser = Read-Host "请输入 Docker Hub 用户名"
    if ($dockerHubUser) {
        $Registry = $dockerHubUser
    } else {
        Write-Host "未输入用户名，将仅构建本地镜像" -ForegroundColor Yellow
        $Push = $false
    }
} elseif ($pushChoice -eq "3") {
    $Push = $true
    $customRegistry = Read-Host "请输入仓库地址 (如: registry.cn-hangzhou.aliyuncs.com/yourname)"
    if ($customRegistry) {
        $Registry = $customRegistry
    } else {
        Write-Host "未输入仓库地址，将仅构建本地镜像" -ForegroundColor Yellow
        $Push = $false
    }
} else {
    Write-Host "无效选项，默认仅构建本地镜像" -ForegroundColor Yellow
    $Push = $false
}

# 如果指定了仓库地址，添加前缀
if ($Registry) {
    $FrontendImage = "$Registry/$FrontendImage"
    $BackendImage = "$Registry/$BackendImage"
}

# 完整镜像标签
$FrontendTag = "${FrontendImage}:${Tag}"
$BackendTag = "${BackendImage}:${Tag}"

# 确认信息
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "构建配置确认:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "目标架构: $Architecture" -ForegroundColor Yellow
Write-Host "镜像标签: $Tag" -ForegroundColor Yellow
if ($Registry) {
    Write-Host "仓库地址: $Registry" -ForegroundColor Yellow
}
Write-Host "构建前端: $BuildFrontend" -ForegroundColor Yellow
Write-Host "构建后端: $BuildBackend" -ForegroundColor Yellow
Write-Host "推送镜像: $Push" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

$confirm = Read-Host "确认开始构建? (Y/n)"
if ($confirm -and $confirm.ToLower() -eq "n") {
    Write-Host "已取消构建" -ForegroundColor Red
    exit 0
}

# 检查 Docker 是否安装
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker 未安装或未添加到 PATH"
    exit 1
}

# 检查 Docker 是否运行
try {
    docker info | Out-Null
} catch {
    Write-Error "Docker 服务未运行，请启动 Docker Desktop"
    exit 1
}

# 设置平台参数
$platforms = "linux/amd64"
$useBuildx = $false
if ($Architecture -eq "amd64") {
    $platforms = "linux/amd64"
    $useBuildx = $false
    Write-Host ""
    Write-Host "[1/3] AMD64 构建 - 使用传统 docker build" -ForegroundColor Green
} elseif ($Architecture -eq "arm64") {
    $platforms = "linux/arm64"
    $useBuildx = $true
    Write-Host ""
    Write-Host "[1/3] ARM64 构建 - 使用 docker buildx" -ForegroundColor Green
    docker buildx use default 2>&1 | Out-Null
    Write-Host "使用 default 构建器（支持本地镜像缓存）" -ForegroundColor Gray
} elseif ($Architecture -eq "all") {
    $platforms = "linux/amd64,linux/arm64"
    $useBuildx = $true
    Write-Host ""
    Write-Host "[1/3] 多架构构建 - 使用 docker buildx" -ForegroundColor Green
    docker buildx use default 2>&1 | Out-Null
}

Write-Host "目标平台: $platforms" -ForegroundColor Gray

# 检查本地镜像是否存在
function Test-LocalImageExists {
    param([string]$ImageName)
    $result = docker images --format "{{.Repository}}:{{.Tag}}" | Select-String -Pattern "^$([regex]::Escape($ImageName))$"
    return $null -ne $result
}

# 根据架构获取本地镜像名称（直接使用官方镜像名称，检查本地是否存在）
function Get-LocalImages {
    param([string]$Arch)

    # 定义官方镜像名称
    $imageMap = if ($Arch -eq "arm64") {
        @{
            Python = "python:3.13-slim-arm64"
            Node = "node:22-alpine-arm64"
            Nginx = "nginx:alpine-arm64"
        }
    } else {
        @{
            Python = "python:3.13-slim-amd64"
            Node = "node:22-alpine-amd64"
            Nginx = "nginx:alpine-amd64"
        }
    }

    $result = @{}
    $allExists = $true

    foreach ($key in $imageMap.Keys) {
        $imageName = $imageMap[$key]

        if (Test-LocalImageExists -ImageName $imageName) {
            Write-Host "✓ 本地镜像存在: $imageName" -ForegroundColor Green
            $result[$key] = $imageName
        } else {
            Write-Host "✗ 本地镜像不存在: $imageName" -ForegroundColor Red
            $result[$key] = $imageName
            $allExists = $false
        }
    }

    if (-not $allExists) {
        Write-Host ""
        Write-Host "警告: 部分基础镜像不存在于本地，构建时可能会尝试从网络拉取。" -ForegroundColor Yellow
        Write-Host "如需离线构建，请先执行以下命令拉取镜像:" -ForegroundColor Yellow
        foreach ($key in $imageMap.Keys) {
            Write-Host "  docker pull $($imageMap[$key])" -ForegroundColor Gray
        }
        Write-Host ""
    }

    return $result
}

# 构建函数
function Build-Image {
    param(
        [string]$Context,
        [string]$ImageTag,
        [string]$Dockerfile = "Dockerfile",
        [hashtable]$LocalImages = @{}
    )

    Write-Host ""
    Write-Host "构建镜像: $ImageTag" -ForegroundColor Green
    Write-Host "上下文: $Context" -ForegroundColor Gray
    Write-Host "Dockerfile: $Dockerfile" -ForegroundColor Gray

    # 根据是否使用 buildx 选择构建方式
    if ($useBuildx) {
        # ARM64/多架构构建 - 使用 buildx
        $buildArgs = @(
            "buildx", "build",
            "--platform", $platforms,
            "--tag", $ImageTag,
            "--file", "$Context/$Dockerfile",
            "--pull=false",
            "--load"
        )
        Write-Host "使用 buildx 构建（跨平台）" -ForegroundColor Gray
    } else {
        # AMD64 构建 - 使用传统 docker build
        $buildArgs = @(
            "build",
            "--tag", $ImageTag,
            "--file", "$Context/$Dockerfile",
            "--pull=false"
        )
        Write-Host "使用传统 docker build" -ForegroundColor Gray
    }

    # 添加本地镜像 build-arg
    if ($LocalImages.Python) {
        $buildArgs += "--build-arg"
        $buildArgs += "PYTHON_IMAGE=$($LocalImages.Python)"
        Write-Host "使用 Python 镜像: $($LocalImages.Python)" -ForegroundColor Gray
    }
    if ($LocalImages.Node) {
        $buildArgs += "--build-arg"
        $buildArgs += "NODE_IMAGE=$($LocalImages.Node)"
        Write-Host "使用 Node 镜像: $($LocalImages.Node)" -ForegroundColor Gray
    }
    if ($LocalImages.Nginx) {
        $buildArgs += "--build-arg"
        $buildArgs += "NGINX_IMAGE=$($LocalImages.Nginx)"
        Write-Host "使用 Nginx 镜像: $($LocalImages.Nginx)" -ForegroundColor Gray
    }

    $buildArgs += $Context

    Write-Host "执行命令: docker $($buildArgs -join ' ')" -ForegroundColor DarkGray

    & docker @buildArgs

    if ($LASTEXITCODE -ne 0) {
        Write-Error "镜像构建失败: $ImageTag"
        exit 1
    }

    Write-Host "镜像构建成功: $ImageTag" -ForegroundColor Green
}

# 获取本地镜像配置
$localImages = Get-LocalImages -Arch $Architecture

# 构建后端镜像
if ($BuildBackend) {
    Write-Host ""
    Write-Host "[2/3] 构建后端镜像..." -ForegroundColor Green
    Build-Image -Context "backend" -ImageTag $BackendTag -LocalImages @{
        Python = $localImages.Python
    }
}

# 构建前端镜像
if ($BuildFrontend) {
    Write-Host ""
    Write-Host "[3/3] 构建前端镜像..." -ForegroundColor Green
    Build-Image -Context "frontend" -ImageTag $FrontendTag -LocalImages @{
        Node = $localImages.Node
        Nginx = $localImages.Nginx
    }
}

# 导出镜像功能
function Export-Image {
    param(
        [string]$ImageTag,
        [string]$OutputFile
    )

    Write-Host ""
    Write-Host "导出镜像: $ImageTag" -ForegroundColor Yellow

    docker save $ImageTag -o $OutputFile

    if ($LASTEXITCODE -eq 0) {
        $fileSize = (Get-Item $OutputFile).Length / 1MB
        Write-Host "✓ 导出成功！文件: $OutputFile, 大小: $([math]::Round($fileSize, 2)) MB" -ForegroundColor Green
        return $true
    } else {
        Write-Host "✗ 导出失败" -ForegroundColor Red
        return $false
    }
}

# 询问是否导出镜像
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "构建完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

if ($BuildBackend) {
    Write-Host "后端镜像: $BackendTag" -ForegroundColor Yellow
    docker images $BackendImage --format "table {{.Repository}}:{{.Tag}}`t{{.Size}}`t{{.CreatedAt}}" | Select-Object -First 2
}

if ($BuildFrontend) {
    Write-Host "前端镜像: $FrontendTag" -ForegroundColor Yellow
    docker images $FrontendImage --format "table {{.Repository}}:{{.Tag}}`t{{.Size}}`t{{.CreatedAt}}" | Select-Object -First 2
}

# 导出镜像选项
Write-Host ""
Write-Host "是否导出镜像到文件?" -ForegroundColor Green
Write-Host "  [1] 是，导出镜像" -ForegroundColor White
Write-Host "  [2] 否，跳过导出" -ForegroundColor White

$exportChoice = Read-Host "请输入选项 (1-2)"

if ($exportChoice -eq "1") {
    Write-Host ""
    Write-Host "=== 导出镜像 ===" -ForegroundColor Cyan

    if ($BuildBackend) {
        $backendOutput = "$BackendImage-$Architecture-$Tag.tar"
        Export-Image -ImageTag $BackendTag -OutputFile $backendOutput
    }

    if ($BuildFrontend) {
        $frontendOutput = "$FrontendImage-$Architecture-$Tag.tar"
        Export-Image -ImageTag $FrontendTag -OutputFile $frontendOutput
    }
}

if ($Push) {
    Write-Host ""
    Write-Host "镜像已推送到仓库" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "本地镜像列表:" -ForegroundColor Gray
    docker images | Select-String -Pattern "$FrontendImage|$BackendImage"

    Write-Host ""
    Write-Host "要推送镜像到仓库，请运行:" -ForegroundColor Cyan
    if ($BuildBackend) {
        Write-Host "  docker push $BackendTag" -ForegroundColor Gray
    }
    if ($BuildFrontend) {
        Write-Host "  docker push $FrontendTag" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "使用示例:" -ForegroundColor Cyan
Write-Host "  # 运行 AMD64 版本" -ForegroundColor Gray
Write-Host "  docker-compose up -d" -ForegroundColor Gray
Write-Host ""
Write-Host "  # 运行 ARM64 版本（如 Apple Silicon Mac）" -ForegroundColor Gray
Write-Host "  docker-compose up -d" -ForegroundColor Gray
