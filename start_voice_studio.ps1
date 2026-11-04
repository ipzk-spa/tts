#Requires -Version 5.1
<#
  Запуск Spag Voice Studio (SVS+).
  Створює .venv за потреби, ставить залежності і відкриває браузер.
#>
$ErrorActionPreference = "Stop"

# UTF-8 консоль (інакше "Перевірка" → "Перев?рка" у cmd.exe)
try {
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [Console]::OutputEncoding = $utf8
    [Console]::InputEncoding = $utf8
    $OutputEncoding = $utf8
    if ($Host.UI -and $Host.UI.RawUI) {
        try { $Host.UI.RawUI.WindowTitle = 'Spag Voice Studio - SVS+' } catch {}
    }
} catch {}

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:PYTHONLEGACYWINDOWSSTDIO = "0"

$Root = $PSScriptRoot
Set-Location $Root

function Write-LogLine {
    param([string]$Message, [string]$Level = "CONSOLE")
    $logsDir = Join-Path $Root "logs"
    if (-not (Test-Path $logsDir)) {
        New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
    }
    $logFile = Join-Path $logsDir "errors.txt"
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logFile -Value "[$stamp] $Level | $Message" -Encoding UTF8
}

function Write-Utf8 {
    param([string]$Message, [ConsoleColor]$Color = [ConsoleColor]::Cyan)
    Write-LogLine -Message $Message -Level "CONSOLE"
    $prev = [Console]::ForegroundColor
    try {
        [Console]::ForegroundColor = $Color
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Message + [Environment]::NewLine)
        $stdout = [Console]::OpenStandardOutput()
        $stdout.Write($bytes, 0, $bytes.Length)
        $stdout.Flush()
    } catch {
        Write-Host $Message -ForegroundColor $Color
    } finally {
        [Console]::ForegroundColor = $prev
    }
}

function Write-StartupError {
    param([string]$Message, [System.Management.Automation.ErrorRecord]$ErrorRecord = $null)
    Write-LogLine -Message $Message -Level "ERROR"
    if ($null -ne $ErrorRecord) {
        Write-LogLine -Message $ErrorRecord.ToString() -Level "ERROR"
        if ($ErrorRecord.ScriptStackTrace) {
            Write-LogLine -Message $ErrorRecord.ScriptStackTrace -Level "ERROR"
        }
    }
    Write-Utf8 -Message $Message -Color Red
    Write-Utf8 -Message ("Detali v: " + (Join-Path $Root "logs\errors.txt")) -Color Yellow
}

try {
    if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw "Python не знайдено. Встановіть Python 3.10+ (рекомендовано 3.11) і додайте в PATH."
    }

    if (-not (Test-Path ".venv")) {
        Write-Utf8 -Message "Створення віртуального середовища..." -Color Cyan
        if (Get-Command py -ErrorAction SilentlyContinue) {
            py -3.11 -m venv .venv
            if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
                python -m venv .venv
            }
        } else {
            python -m venv .venv
        }
    }

    $Python = ".\.venv\Scripts\python.exe"
    if (-not (Test-Path $Python)) {
        throw "Не знайдено $Python — віртуальне середовище не створилось."
    }

    Write-Utf8 -Message "Перевірка залежностей Spag Voice Studio (SVS+)..." -Color Cyan
    & $Python -m pip install --upgrade pip --quiet
    & $Python -m pip install -r voice_studio\requirements.txt --quiet

    Write-Utf8 -Message "" -Color Green
    Write-Utf8 -Message "Запуск Spag Voice Studio (SVS+)..." -Color Green
    & $Python voice_studio\api_server.py
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        throw "Процес Python завершився з кодом $LASTEXITCODE."
    }
}
catch {
    Write-StartupError -Message $_.Exception.Message -ErrorRecord $_
    exit 1
}
