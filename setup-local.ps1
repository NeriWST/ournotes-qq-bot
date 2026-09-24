# Windows PowerShell 5.1 requires a UTF-8 BOM to decode the Chinese messages below.
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "[1/4] 创建 Python 虚拟环境..."
    py -3 -m venv .venv
}

Write-Host "[2/4] 安装项目和 QQ SDK..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -e .

if (-not (Test-Path -LiteralPath ".env")) {
    Write-Host "[3/4] 创建本地配置 .env..."
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
} else {
    Write-Host "[3/4] 保留已有 .env 配置。"
}

Write-Host "[4/4] 同步 Ournotes 数据..."
& $venvPython -m ournotes_bot.main sync

Write-Host ""
Write-Host "本地环境准备完成。"
Write-Host "请用记事本打开 .env，填写 QQ_APP_ID 和 QQ_APP_SECRET。"
Write-Host "填写后运行：.\start-bot.ps1"
