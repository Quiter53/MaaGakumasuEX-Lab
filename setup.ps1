param([string]$Python = "python")
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    git submodule update --init --recursive
    if ($LASTEXITCODE -ne 0) { throw "Source submodule download failed" }
    & $Python -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ required"'
    if ($LASTEXITCODE -ne 0) { throw "Use a full Python 3.12+ installation" }
    if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
        & $Python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed" }
    }
    & .\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
    & .\.venv\Scripts\python.exe lab.py prepare
    if ($LASTEXITCODE -ne 0) { throw "Fixture restore failed" }
} finally { Pop-Location }
