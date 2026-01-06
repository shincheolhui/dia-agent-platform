# scripts/bootstrap.ps1
# 목적: 어느 위치에서 실행하든 repo root에서 설치/실행되게 강제

$ErrorActionPreference = "Stop"

# repo root로 이동
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

# venv 권장 (이미 있다면 그대로 사용)
if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

# activate
. .\.venv\Scripts\Activate.ps1

python -m pip install -U pip

# lock 기반 설치 (파일명이 requirements.lock.txt 라면 아래 수정)
if (Test-Path "requirements.lock.txt") {
  python -m pip install -r requirements.lock.txt
} elseif (Test-Path "requirements.lock.txt.txt") {
  python -m pip install -r requirements.lock.txt.txt
} elseif (Test-Path "requirements.lock.txt") {
  python -m pip install -r requirements.lock.txt
} elseif (Test-Path "requirements.txt") {
  python -m pip install -r requirements.txt
}

# 핵심: editable install
python -m pip install -e .

Write-Host "[OK] editable install done. Try: chainlit run apps/chainlit_app/app.py"
