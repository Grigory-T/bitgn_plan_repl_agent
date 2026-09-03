[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$UvPath = ""
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Resolve-UvExecutable {
    param([string]$RequestedPath)

    if ($RequestedPath) {
        if (-not (Test-Path -LiteralPath $RequestedPath -PathType Leaf)) {
            throw "uv executable was not found at: $RequestedPath"
        }
        return (Resolve-Path -LiteralPath $RequestedPath).Path
    }

    # Ask specifically for an application. A PowerShell alias or function named
    # "uv" has no executable Source path and cannot be passed to the call operator.
    $UvCommand = Get-Command uv.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $UvCommand) {
        $UvCommand = Get-Command uv -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
    }
    if ($UvCommand -and $UvCommand.Path) {
        return [string]$UvCommand.Path
    }

    $UvFile = Get-ChildItem `
        (Join-Path $env:APPDATA "Python\Python*\Scripts\uv.exe") `
        -File `
        -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if ($UvFile) {
        return [string]$UvFile.FullName
    }

    throw "uv was not found on PATH or below the current user's AppData folder"
}

$UvExecutable = Resolve-UvExecutable -RequestedPath $UvPath
Write-Host "Using uv: $UvExecutable"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $UvExecutable venv --python $Python .venv
    if ($LASTEXITCODE -ne 0) {
        throw "uv venv failed with exit code $LASTEXITCODE"
    }
}

& $UvExecutable pip install --python ".venv\Scripts\python.exe" -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    throw "dependency installation failed with exit code $LASTEXITCODE"
}

& ".venv\Scripts\python.exe" -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) {
    throw "tests failed with exit code $LASTEXITCODE"
}

if (-not (Test-Path "llm_config.txt")) {
    Copy-Item "llm_config.example.txt" "llm_config.txt"
    Write-Host "Created $Root\llm_config.txt"
}

Write-Host "Setup complete. Edit llm_config.txt, then run llm_preflight.py."
