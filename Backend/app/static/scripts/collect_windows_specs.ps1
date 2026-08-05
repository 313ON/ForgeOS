<#>
.SYNOPSIS
    ForgeOS Windows Spec Collector
    Generates plain-text hardware reports compatible with ForgeOS extraction parser.

.DESCRIPTION
    This script creates a 'Specs' folder on the user's Desktop and writes
    multiple plain-text reports that the ForgeOS backend parser can ingest:
      - systeminfo.txt     (systeminfo.exe output)
      - dxdiag.txt         (dxdiag /t output)
      - hostname.txt       (hostname)
      - ipconfig.txt       (ipconfig /all)
      - disks.txt          (wmic diskdrive get ...)

    The reports are NOT sent anywhere; you upload them manually via the
    ForgeOS "Extract Asset Details" modal (Multiple Files input).

.NOTES
    - Run in PowerShell (no admin required for most commands; dxdiag may prompt).
    - Output encoding is UTF-8.
    - Only plain-text formats already supported by the parser are generated.
#>

$ErrorActionPreference = "Stop"

# Determine output directory: Desktop\Specs (fallback to $env:USERPROFILE\Specs)
$desktop = [Environment]::GetFolderPath("Desktop")
if (-not $desktop -or -not (Test-Path $desktop)) {
    $desktop = $env:USERPROFILE
}
$outDir = Join-Path $desktop "Specs"
if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}
Write-Host "Writing reports to: $outDir" -ForegroundColor Cyan

# Helper to write UTF-8 text file
function Write-Report($name, $content) {
    $path = Join-Path $outDir $name
    [IO.File]::WriteAllText($path, $content, [Text.Encoding]::UTF8)
    Write-Host "  ✓ $name" -ForegroundColor Green
}

# 1) systeminfo.txt
Write-Host "Running systeminfo.exe..." -ForegroundColor Yellow
$sysInfo = systeminfo.exe /FO LIST 2>&1
Write-Report "systeminfo.txt" $sysInfo

# 2) dxdiag.txt (run dxdiag /t to export to temp file, then read)
Write-Host "Running dxdiag /t..." -ForegroundColor Yellow
$dxdiagTemp = [IO.Path]::GetTempFileName()
$dxdiagTempTxt = $dxdiagTemp + ".txt"
# dxdiag /t writes to a file in the current directory with a specific name pattern
# We'll run it and capture output from the generated file
$dxdiagOut = Join-Path $outDir "dxdiag_raw.txt"
Start-Process "dxdiag.exe" -ArgumentList "/t $dxdiagOut" -Wait -NoNewWindow
if (Test-Path $dxdiagOut) {
    $dxdiagContent = Get-Content $dxdiagOut -Raw -Encoding UTF8
    Write-Report "dxdiag.txt" $dxdiagContent
    Remove-Item $dxdiagOut -Force -ErrorAction SilentlyContinue
} else {
    Write-Warning "dxdiag output not found; dxdiag may have been skipped or requires interactive session."
}

# 3) hostname.txt
Write-Report "hostname.txt" $env:COMPUTERNAME

# 4) ipconfig.txt
Write-Host "Running ipconfig /all..." -ForegroundColor Yellow
$ipconfig = ipconfig.exe /all 2>&1
Write-Report "ipconfig.txt" $ipconfig

# 5) disks.txt (wmic diskdrive)
Write-Host "Running wmic diskdrive..." -ForegroundColor Yellow
$disks = wmic diskdrive get Model,Size,MediaType,SerialNumber /format:list 2>&1
Write-Report "disks.txt" $disks

# 6) memory.txt (wmic memorychip)
Write-Host "Running wmic memorychip..." -ForegroundColor Yellow
$memory = wmic memorychip get Capacity,Speed,Manufacturer,PartNumber /format:list 2>&1
Write-Report "memory.txt" $memory

# 7) cpu.txt (wmic cpu)
Write-Host "Running wmic cpu..." -ForegroundColor Yellow
$cpu = wmic cpu get Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,L2CacheSize,L3CacheSize /format:list 2>&1
Write-Report "cpu.txt" $cpu

# 8) os.txt (wmic os)
Write-Host "Running wmic os..." -ForegroundColor Yellow
$os = wmic os get Caption,Version,BuildNumber,OSArchitecture,InstallDate /format:list 2>&1
Write-Report "os.txt" $os

# 9) bios.txt (wmic bios)
Write-Host "Running wmic bios..." -ForegroundColor Yellow
$bios = wmic bios get Manufacturer,SMBIOSBIOSVersion,ReleaseDate /format:list 2>&1
Write-Report "bios.txt" $bios

# 10) gpu.txt (wmic path win32_VideoController)
Write-Host "Running wmic path win32_VideoController..." -ForegroundColor Yellow
$gpu = wmic path win32_VideoController get Name,AdapterRAM,DriverVersion,VideoProcessor /format:list 2>&1
Write-Report "gpu.txt" $gpu

Write-Host "`nDone. Reports written to: $outDir" -ForegroundColor Cyan
Write-Host "Upload ALL .txt files from this folder via ForgeOS 'Extract Asset Details' modal." -ForegroundColor Cyan