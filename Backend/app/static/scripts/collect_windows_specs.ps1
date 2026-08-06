<#
.SYNOPSIS
    ForgeOS Windows Spec Collector

.DESCRIPTION
    Creates a parser-ready ForgeOS report and supporting diagnostics in
    Desktop\ForgeOS-Specs. Nothing is uploaded automatically.

.PARAMETER NoPause
    Skip the final prompt when running from an existing automation workflow.
#>

param(
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
$script:Succeeded = 0
$script:Failed = 0

function Write-Report {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Content
    )

    $path = Join-Path $script:OutputDirectory $Name
    [IO.File]::WriteAllText($path, $Content.TrimEnd() + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    $script:Succeeded += 1
    Write-Host "  [OK] $Name" -ForegroundColor Green
}

function Invoke-Report {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )

    Write-Host "Collecting $Label..." -ForegroundColor Yellow
    try {
        $content = (& $Command 2>&1 | Out-String).Trim()
        if (-not $content) {
            throw "The command returned no data."
        }
        Write-Report -Name $Name -Content $content
    }
    catch {
        $script:Failed += 1
        Write-Host "  [FAILED] $Name - $($_.Exception.Message)" -ForegroundColor Red
    }
}

try {
    $desktop = [Environment]::GetFolderPath("Desktop")
    if (-not $desktop -or -not (Test-Path -LiteralPath $desktop)) {
        $desktop = $env:USERPROFILE
    }
    $script:OutputDirectory = Join-Path $desktop "ForgeOS-Specs"
    New-Item -ItemType Directory -Path $script:OutputDirectory -Force | Out-Null

    Write-Host ""
    Write-Host "ForgeOS Windows Spec Collector" -ForegroundColor Cyan
    Write-Host "Output: $script:OutputDirectory" -ForegroundColor DarkCyan
    Write-Host ""

    Write-Host "Building parser-ready report..." -ForegroundColor Yellow
    try {
        $computer = Get-CimInstance Win32_ComputerSystem
        $operatingSystem = Get-CimInstance Win32_OperatingSystem
        $processor = Get-CimInstance Win32_Processor | Select-Object -First 1
        $bios = Get-CimInstance Win32_BIOS
        $graphics = Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name
        $ipAddress = Get-CimInstance Win32_NetworkAdapterConfiguration |
            Where-Object { $_.IPEnabled -and $_.IPAddress } |
            ForEach-Object { $_.IPAddress } |
            Where-Object { $_ -match '^\d{1,3}(\.\d{1,3}){3}$' } |
            Select-Object -First 1
        $memoryMb = [math]::Round([double]$computer.TotalPhysicalMemory / 1MB)

        $primaryReport = @(
            "Host Name: $env:COMPUTERNAME"
            "OS Name: $($operatingSystem.Caption)"
            "OS Version: $($operatingSystem.Version) Build $($operatingSystem.BuildNumber)"
            "System Manufacturer: $($computer.Manufacturer)"
            "System Model: $($computer.Model)"
            "System Serial Number: $($bios.SerialNumber)"
            "Processor Name: $($processor.Name)"
            "Number of Cores: $($processor.NumberOfCores)"
            "Number of Logical Processors: $($processor.NumberOfLogicalProcessors)"
            "Total Physical Memory: $memoryMb MB"
            "BIOS Version: $($bios.SMBIOSBIOSVersion)"
            "GPU Name: $($graphics -join '; ')"
            "IP Address: $ipAddress"
        ) -join [Environment]::NewLine
        Write-Report -Name "forgeos_system_report.txt" -Content $primaryReport
    }
    catch {
        $script:Failed += 1
        Write-Host "  [FAILED] forgeos_system_report.txt - $($_.Exception.Message)" -ForegroundColor Red
    }

    Invoke-Report -Name "systeminfo.txt" -Label "Windows system information" -Command { systeminfo.exe /FO LIST }
    Invoke-Report -Name "ipconfig.txt" -Label "network configuration" -Command { ipconfig.exe /all }
    Invoke-Report -Name "storage.txt" -Label "storage inventory" -Command {
        Get-CimInstance Win32_DiskDrive |
            Select-Object Model, SerialNumber, MediaType, Size |
            Format-List
    }
    Invoke-Report -Name "memory.txt" -Label "memory inventory" -Command {
        Get-CimInstance Win32_PhysicalMemory |
            Select-Object Manufacturer, PartNumber, Speed, Capacity |
            Format-List
    }

    Write-Host "Collecting DxDiag..." -ForegroundColor Yellow
    try {
        $dxdiagPath = Join-Path $script:OutputDirectory "dxdiag.txt"
        Start-Process -FilePath "dxdiag.exe" -ArgumentList "/dontskip", "/t", "`"$dxdiagPath`"" -Wait -WindowStyle Hidden
        if (-not (Test-Path -LiteralPath $dxdiagPath) -or (Get-Item -LiteralPath $dxdiagPath).Length -eq 0) {
            throw "DxDiag did not create a report."
        }
        $script:Succeeded += 1
        Write-Host "  [OK] dxdiag.txt" -ForegroundColor Green
    }
    catch {
        $script:Failed += 1
        Write-Host "  [FAILED] dxdiag.txt - $($_.Exception.Message)" -ForegroundColor Red
    }
}
catch {
    $script:Failed += 1
    Write-Host ""
    Write-Host "Collector setup failed: $($_.Exception.Message)" -ForegroundColor Red
}
finally {
    Write-Host ""
    Write-Host "Collection complete: $script:Succeeded succeeded, $script:Failed failed." -ForegroundColor Cyan
    if ($script:OutputDirectory) {
        Write-Host "Upload forgeos_system_report.txt to ForgeOS." -ForegroundColor Cyan
        Write-Host "Reports folder: $script:OutputDirectory" -ForegroundColor DarkCyan
    }
    if (-not $NoPause -and [Environment]::UserInteractive) {
        [void](Read-Host "Press Enter to close")
    }
}
