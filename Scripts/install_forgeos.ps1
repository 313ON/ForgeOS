[CmdletBinding()]
param(
    [string]$PythonCommand = "py",
    [string]$PythonVersion = "3.12",
    [string]$VenvPath = ".venv"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Require-Command([string]$Name, [string]$Hint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required. $Hint"
    }
}

Require-Command $PythonCommand "Install Python $PythonVersion from python.org and enable the system PATH option."
Require-Command "git" "Install Git for Windows and enable command-line usage."
& $PythonCommand "-$PythonVersion" "--version"
if ($LASTEXITCODE -ne 0) { throw "Python $PythonVersion was not found through '$PythonCommand'." }

$python = Join-Path $root "$VenvPath\Scripts\python.exe"
if (-not (Test-Path $python)) {
    & $PythonCommand "-$PythonVersion" "-m" "venv" $VenvPath
}
if (-not (Test-Path $python)) { throw "Unable to create virtual environment at $VenvPath." }

& $python "-m" "pip" "install" "--upgrade" "pip"
& $python "-m" "pip" "install" "-r" "requirements.txt"
& $python "-m" "compileall" "Backend" "forge" "Scripts"
if ($LASTEXITCODE -ne 0) { throw "Python compileall sanity check failed." }

Write-Host "ForgeOS installation completed."
Write-Host "Activate with: .\$VenvPath\Scripts\Activate.ps1"
Write-Host "Set FORGEOS_AUTH_SECRET and FORGEOS_ADMIN_PASSWORD before production use."
