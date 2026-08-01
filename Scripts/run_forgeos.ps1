[CmdletBinding()]
param(
    [string]$Host = "0.0.0.0",
    [int]$Port = 8000,
    [string]$VenvPath = ".venv",
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root "$VenvPath\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Virtual environment not found. Run .\Scripts\install_forgeos.ps1 first." }

$arguments = @("-m", "uvicorn", "Backend.app.main:app", "--host", $Host, "--port", $Port)
if ($Reload) { $arguments += "--reload" }
& $python @arguments
