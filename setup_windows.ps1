[CmdletBinding()]
param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

$UvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($UvCommand) {
    $Uv = $UvCommand.Source
} else {
    $Uv = Get-ChildItem (Join-Path $env:APPDATA "Python\Python*\Scripts\uv.exe") `
        -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1 -ExpandProperty FullName
    if (-not $Uv) {
        throw "uv was not found on PATH or below the current user's AppData folder"
    }
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $Uv venv --python $Python .venv
    if ($LASTEXITCODE -ne 0) {
        throw "uv venv failed with exit code $LASTEXITCODE"
    }
}

& $Uv pip install --python ".venv\Scripts\python.exe" -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    throw "dependency installation failed with exit code $LASTEXITCODE"
}

& ".venv\Scripts\python.exe" -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) {
    throw "tests failed with exit code $LASTEXITCODE"
}

Write-Host "Setup complete. Configure the LLM_* environment variables, then run llm_preflight.py."
