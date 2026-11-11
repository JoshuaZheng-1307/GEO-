# ============================================================================
#  GEO 监测量化模拟系统 - 一键启动脚本（Windows / PowerShell）
#  作用：自检 + 拉取便携版 PostgreSQL/Redis + 启动 FastAPI/Celery/Vue
#  使用：双击 start.bat，或 PowerShell 中 .\start.ps1
#  免管理员 / 免安装服务：PostgreSQL 来自 zonky Maven，Redis 来自 GitHub
# ============================================================================

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# ----------------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------------
function Test-Command { param($Name) $null -ne (Get-Command $Name -ErrorAction SilentlyContinue) }
function Write-Step   { param($Msg) Write-Host "`n==> $Msg" -ForegroundColor Cyan }
function Write-Ok     { param($Msg) Write-Host "    [OK] $Msg" -ForegroundColor Green }
function Write-Warn   { param($Msg) Write-Host "    [WARN] $Msg" -ForegroundColor Yellow }
function Write-Err    { param($Msg) Write-Host "    [ERR] $Msg" -ForegroundColor Red }

function Test-Port {
    param([int]$Port)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(800, $false)
        if ($ok -and $client.Connected) { $client.Close(); return $true }
        $client.Close()
    } catch {}
    return $false
}

function Wait-Port {
    param([int]$Port, [int]$TimeoutSec = 20)
    for ($i = 0; $i -lt $TimeoutSec; $i++) {
        if (Test-Port $Port) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Download-File {
    param([string]$Url, [string]$Dest)
    if (Test-Path $Dest) { return }
    Write-Host "    下载 $Url" -ForegroundColor DarkGray
    Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing -TimeoutSec 120
}

# 原生命令包装：避免 stderr 输出在 $ErrorActionPreference=Stop 下中断脚本
function Invoke-Native {
    param([scriptblock]$Cmd, [switch]$Capture)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($Capture) { return (& $Cmd 2>$null) }
        else { (& $Cmd 2>&1 | ForEach-Object { "$_" }) | Out-Null }
    } finally { $ErrorActionPreference = $prev }
}

# ----------------------------------------------------------------------------
# 1. Python / Node 检查
# ----------------------------------------------------------------------------
Write-Step "检查基础工具"

if (-not (Test-Command python)) {
    Write-Err "未检测到 Python，请安装 Python 3.10+ 并勾选 Add to PATH"
    Read-Host "按回车键退出"; exit 1
}
Write-Ok "Python: $(& python --version)"

if (-not (Test-Command node)) {
    Write-Err "未检测到 Node.js，请安装 Node 18+"
    Read-Host "按回车键退出"; exit 1
}
Write-Ok "Node.js: $(& node --version)"

# ----------------------------------------------------------------------------
# 2. PostgreSQL 便携版（zonky 预编译，托管在 Maven Central）
#    注意：PG 对含中文的路径支持极差（initdb 会报 invalid byte sequence），
#    因此把二进制与数据目录放在纯 ASCII 路径 %LOCALAPPDATA%\geo-monitor 下。
# ----------------------------------------------------------------------------
Write-Step "准备 PostgreSQL（便携版，免安装）"
$pgRoot  = Join-Path $env:LOCALAPPDATA "geo-monitor\postgres"
$pgBin   = Join-Path $pgRoot "bin"
$pgData  = Join-Path $env:LOCALAPPDATA "geo-monitor\pgdata"
$pgLog   = Join-Path $env:LOCALAPPDATA "geo-monitor\pg.log"
$postgresExe = Join-Path $pgBin "postgres.exe"

# 迁移：旧版本解压在项目 tools\postgres（中文路径）下，挪到 ASCII 路径
$oldPgBin = Join-Path $ProjectRoot "tools\postgres\bin"
if ((-not (Test-Path $postgresExe)) -and (Test-Path (Join-Path $oldPgBin "postgres.exe"))) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $pgRoot) | Out-Null
    Move-Item (Join-Path $ProjectRoot "tools\postgres") $pgRoot -Force
    Write-Ok "已迁移 PostgreSQL 到 ASCII 路径: $pgRoot"
}

if (-not (Test-Path $postgresExe)) {
    Write-Warn "下载便携 PostgreSQL（zonky 预编译，约 70MB）"
    $jarPath = Join-Path $env:TEMP "pg-bin.jar"
    $jarUrl  = "https://repo1.maven.org/maven2/io/zonky/test/postgres/embedded-postgres-binaries-windows-amd64/16.6.0/embedded-postgres-binaries-windows-amd64-16.6.0.jar"
    try {
        Download-File $jarUrl $jarPath
        # Expand-Archive 只认 .zip 扩展名，把 jar 复制为 zip 再解压（jar 本质就是 zip）
        $zipPath = Join-Path $env:TEMP "pg-bin.zip"
        Copy-Item $jarPath $zipPath -Force
        $stageDir = Join-Path $env:TEMP "pg-stage"
        if (Test-Path $stageDir) { Remove-Item -Recurse -Force $stageDir }
        Expand-Archive -Path $zipPath -DestinationPath $stageDir -Force
        $txz = Get-ChildItem -Path $stageDir -Recurse -Include "*.txz","*.tar.xz" |
               Select-Object -First 1
        if (-not $txz) { throw "未在 jar 中找到 PostgreSQL tar.xz 文件" }
        New-Item -ItemType Directory -Force -Path $pgRoot | Out-Null
        & tar -xJf $txz.FullName -C $pgRoot
        Remove-Item -Recurse -Force $jarPath, $stageDir
        Write-Ok "PostgreSQL 已解压: $pgRoot"
    } catch {
        Write-Err "PostgreSQL 下载/解压失败: $($_.Exception.Message)"
        Write-Host "    请检查是否能访问 https://repo1.maven.org/"
        Read-Host "按回车键退出"; exit 1
    }
} else { Write-Ok "PostgreSQL 已就绪: $pgBin" }

# 初始化数据目录
if (-not (Test-Path (Join-Path $pgData "PG_VERSION"))) {
    Write-Step "初始化 PostgreSQL 数据目录"
    # 上次 initdb 失败可能残留非空目录，先清掉（initdb 要求空目录）
    if (Test-Path $pgData) { Remove-Item -Recurse -Force $pgData }
    New-Item -ItemType Directory -Force -Path $pgData | Out-Null
    # --locale=C：预编译版不含中文 locale 的文本搜索配置，用 C locale 避免 initdb 报错
    Invoke-Native { & (Join-Path $pgBin "initdb.exe") -D $pgData -U postgres `
        --locale=C -E UTF8 --auth-local=trust --auth-host=trust }
    if ($LASTEXITCODE -ne 0) { Write-Err "initdb 失败，请查看上方输出"; Read-Host "回车退出"; exit 1 }
    Write-Ok "数据目录初始化完成"
} else { Write-Ok "数据目录已存在" }

# 启动 PostgreSQL
if (-not (Test-Port 5432)) {
    Write-Step "启动 PostgreSQL"
    # 清理上次异常退出残留的 postmaster.pid（否则 pg_ctl 报 another server might be running）
    $pidFile = Join-Path $pgData "postmaster.pid"
    if ((Test-Path $pidFile) -and -not (Test-Port 5432)) {
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    # 关键：绝不用 -Wait / 管道等 pg_ctl（postgres.exe 是其子进程且永不退出，
    # 会导致 PowerShell 永久挂起）。改为后台启动 + 轮询端口。
    $pgCtl = Join-Path $pgBin "pg_ctl.exe"
    Start-Process -FilePath $pgCtl `
        -ArgumentList @('-D', $pgData, '-l', $pgLog, '-w', '-t', '30', 'start') `
        -WindowStyle Hidden
    if (Wait-Port 5432 40) { Write-Ok "PostgreSQL :5432 就绪" }
    else { Write-Err "PostgreSQL 启动失败，查看日志: $pgLog"; Read-Host "回车退出"; exit 1 }
} else { Write-Ok "PostgreSQL :5432 已在运行" }

# 说明：zonky 便携版不含 psql.exe 客户端，建用户/建库改用后端 Python + psycopg2
# （见下方第 4 节，需先安装 Python 依赖）。

# ----------------------------------------------------------------------------
# 3. Redis 便携版（GitHub，tporadowski 移植版）
# ----------------------------------------------------------------------------
Write-Step "准备 Redis（便携版，免安装）"
$redisDir = Join-Path $ProjectRoot "tools\redis"
$redisExe = Join-Path $redisDir "redis-server.exe"

if (-not (Test-Path $redisExe)) {
    Write-Warn "下载便携 Redis 到 tools\redis（多源轮询，自动校验完整性）"
    New-Item -ItemType Directory -Force -Path $redisDir | Out-Null
    $zipPath = Join-Path $env:TEMP "redis-portable.zip"
    # 关键：先删除可能残留的损坏 zip（上次下载中断的半成品）
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force -ErrorAction SilentlyContinue }

    $redisUrls = @(
        "https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip",
        "https://ghproxy.net/https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip",
        "https://ghfast.top/https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip",
        "https://gh-proxy.com/https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip"
    )
    $downloaded = $false
    foreach ($u in $redisUrls) {
        try {
            Write-Host "    尝试下载源: $u" -ForegroundColor DarkGray
            Invoke-WebRequest -Uri $u -OutFile $zipPath -UseBasicParsing -TimeoutSec 180
            # zip 完整性校验：能打开且至少 1 个条目才算成功
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
            $entryCount = $zip.Entries.Count
            $zip.Dispose()
            if ($entryCount -gt 0) {
                $downloaded = $true
                Write-Ok "下载成功（$entryCount 个文件）"
                break
            }
            Write-Warn "zip 校验失败（0 个条目），换下一个源"
        } catch {
            Write-Warn "该源失败: $($_.Exception.Message)"
        }
        if (Test-Path $zipPath) { Remove-Item $zipPath -Force -ErrorAction SilentlyContinue }
    }
    if (-not $downloaded) {
        Write-Err "所有下载源均失败。请手动下载 Redis-x64-5.0.14.1.zip 解压到 $redisDir"
        Write-Host "  https://github.com/tporadowski/redis/releases （v5.0.14.1）"
        Read-Host "回车退出"; exit 1
    }
    Expand-Archive -Path $zipPath -DestinationPath $redisDir -Force
    Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
    Write-Ok "Redis 已解压: $redisDir"
} else { Write-Ok "Redis 已就绪: $redisExe" }

if (-not (Test-Port 6379)) {
    Start-Process -FilePath $redisExe -ArgumentList "--port 6379" -WindowStyle Hidden -WorkingDirectory $redisDir
    if (Wait-Port 6379 10) { Write-Ok "Redis :6379 就绪" }
    else { Write-Warn "Redis :6379 未就绪" }
} else { Write-Ok "Redis :6379 已在运行" }

# ----------------------------------------------------------------------------
# 4. 后端：虚拟环境 + 依赖 + Playwright
# ----------------------------------------------------------------------------
$backendDir = Join-Path $ProjectRoot "backend"
$venvDir    = Join-Path $backendDir ".venv"
$venvPy     = Join-Path $venvDir "Scripts\python.exe"

Set-Location $backendDir
Write-Step "准备 Python 虚拟环境 (.venv)"
if (-not (Test-Path $venvPy)) {
    & python -m venv $venvDir
    Write-Ok "已创建虚拟环境"
} else { Write-Ok "虚拟环境已存在" }

Write-Step "安装后端 Python 依赖（首次约 3-10 分钟，属正常，请勿关闭）"
Write-Host "    正在升级 pip ..." -ForegroundColor DarkGray
& $venvPy -m pip install --upgrade pip --quiet
Write-Host "    正在安装 requirements.txt（pandas/playwright 等较大，耐心等待）..." -ForegroundColor DarkGray
& $venvPy -m pip install -r (Join-Path $backendDir "requirements.txt")
if ($LASTEXITCODE -ne 0) { Write-Err "pip 安装失败"; Read-Host "回车退出"; exit 1 }
Write-Ok "Python 依赖安装完成"

# ----------------------------------------------------------------------------
# 5. 创建用户与数据库（用 psycopg2，zonky 版 PG 无 psql 客户端）
# ----------------------------------------------------------------------------
Write-Step "确保数据库 geo_monitor 与用户 geo 存在"
$initPy = @'
import sys
import psycopg2

try:
    conn = psycopg2.connect(dbname="postgres", user="postgres",
                            host="127.0.0.1", port=5432, connect_timeout=5)
    conn.autocommit = True
except Exception as exc:
    print("CONNECT_FAIL:" + str(exc))
    sys.exit(1)

cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_roles WHERE rolname='geo'")
if not cur.fetchone():
    cur.execute("CREATE USER geo WITH PASSWORD 'geo123'")
    print("user geo created")
else:
    print("user geo exists")

cur.execute("SELECT 1 FROM pg_database WHERE datname='geo_monitor'")
if not cur.fetchone():
    cur.execute("CREATE DATABASE geo_monitor OWNER geo")
    print("database geo_monitor created")
else:
    print("database geo_monitor exists")
cur.close()
conn.close()
'@
$initOut = $initPy | & $venvPy -
if ("$initOut" -match "CONNECT_FAIL") {
    Write-Err "连接 PostgreSQL 失败: $initOut"
} else {
    Write-Ok ($initOut -join "; ")
}

Write-Step "检查 Playwright Chromium"
$chromeDir = Join-Path $env:LOCALAPPDATA "ms-playwright"
$hasChromium = (Test-Path $chromeDir) -and (Get-ChildItem $chromeDir -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "chromium" })
if (-not $hasChromium) {
    Write-Host "    正在下载 Chromium（约 120MB）..." -ForegroundColor DarkGray
    & $venvPy -m playwright install chromium
    Write-Ok "Playwright Chromium 安装完成"
} else { Write-Ok "Playwright Chromium 已就绪" }

# ----------------------------------------------------------------------------
# 5. 前端：npm 依赖
# ----------------------------------------------------------------------------
$frontendDir = Join-Path $ProjectRoot "frontend"
Set-Location $frontendDir
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Step "安装前端依赖 (npm install，首次约 1-3 分钟)"
    npm install --no-fund --no-audit
    Write-Ok "前端依赖安装完成"
} else { Write-Ok "前端依赖已就绪" }

# ----------------------------------------------------------------------------
# 6. 启动 FastAPI / Celery / Vue 三个服务窗口
#    注意：绝不在命令行里拼中文路径 -WorkingDirectory 通过 Windows API 设置，
#    命令字符串全部用相对路径（基于 -WorkingDirectory），彻底避开 GBK 解析问题。
# ----------------------------------------------------------------------------
Set-Location $ProjectRoot
Write-Step "启动 FastAPI / Celery / Vue 三个服务"

# FastAPI
Start-Process -FilePath "cmd.exe" `
    -ArgumentList @('/k', ".venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000") `
    -WorkingDirectory $backendDir -WindowStyle Normal | Out-Null
Write-Ok "FastAPI 启动中 (http://localhost:8000)"

# Celery Worker（Windows 必须 -P solo）
Start-Process -FilePath "cmd.exe" `
    -ArgumentList @('/k', ".venv\Scripts\python.exe -m celery -A app.tasks.celery_app worker --loglevel=info -P solo") `
    -WorkingDirectory $backendDir -WindowStyle Normal | Out-Null
Write-Ok "Celery Worker 启动中"

# Vue 前端
Start-Process -FilePath "cmd.exe" `
    -ArgumentList @('/k', "npm run dev") `
    -WorkingDirectory $frontendDir -WindowStyle Normal | Out-Null
Write-Ok "Vue 前端启动中 (http://localhost:5173)"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  全部服务已启动！" -ForegroundColor Green
Write-Host "  前端 UI  : http://localhost:5173" -ForegroundColor Green
Write-Host "  API 文档 : http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  PostgreSQL: tools\postgres  (数据在 tools\postgres\data)" -ForegroundColor DarkGreen
Write-Host "  Redis    : tools\redis      (隐藏进程，任务管理器搜 redis-server 可结束)" -ForegroundColor DarkGreen
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Read-Host "按回车键退出此窗口（不会关闭已启动的服务）"
