# Windows PowerShell 5.1 requires a UTF-8 BOM to decode the Chinese messages below.
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "尚未初始化本地环境，请先运行 .\setup-local.ps1"
}
if (-not (Test-Path -LiteralPath ".env")) {
    throw "缺少 .env，请先运行 .\setup-local.ps1 并填写 QQ 凭证"
}

& $venvPython -m ournotes_bot.main bot
