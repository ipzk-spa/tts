#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "Спочатку запустіть install.ps1 або start_voice_studio.ps1 (створить .venv)." -ForegroundColor Red
    exit 1
}
& $Python -m pytest voice_studio\tests\ -v
