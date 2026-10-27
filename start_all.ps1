# ==============================================================================
# VeriPulse Windows PowerShell Autonomous Launcher
# Single-Click Startup for VeriPulse Cyber-Physical Edge & Cloud Pipeline
# ==============================================================================

[CmdletBinding()]
param (
    [ValidateSet("DRY_RUN", "LIVE")]
    [string]$Mode = "DRY_RUN",

    [double]$Fps = 120.0,

    [switch]$WithDashboard,

    [switch]$NoStreamer,

    [switch]$NoEdge,

    [switch]$NoPlc,

    [switch]$NoCool,

    [switch]$NoGateway,

    [switch]$NoAgent,

    [double]$TimeoutSec = 0
)

$ErrorActionPreference = "Stop"

# Resolve paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "         VERIPULSE CYBER-PHYSICAL EDGE & CLOUD INSPECTION SUITE" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " * Mode              : $Mode" -ForegroundColor White
Write-Host " * Target Framerate  : $Fps FPS (8.33 ms frame budget)" -ForegroundColor White
Write-Host " * Workspace Root    : $ScriptDir" -ForegroundColor White
Write-Host " * Start Time        : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor White
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Pre-flight Check: Python
Write-Host "[PRE-FLIGHT] Checking Python environment..." -ForegroundColor Yellow
try {
    $pyVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    Write-Host "[PRE-FLIGHT] Detected Python $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python 3.10+ is required but was not found in PATH." -ForegroundColor Red
    exit 1
}

# 2. Pre-flight Check: Required Python packages
Write-Host "[PRE-FLIGHT] Verifying critical modules (cv2, pymodbus, fastapi, websockets, numpy)..." -ForegroundColor Yellow
$checkModules = python -c "
mods = ['cv2', 'numpy', 'pymodbus', 'fastapi', 'uvicorn', 'websockets']
missing = []
for m in mods:
    try:
        __import__(m)
    except ImportError:
        missing.append(m)
if missing:
    print('MISSING:' + ','.join(missing))
else:
    print('OK')
"

if ($checkModules -like "MISSING:*") {
    $missingList = $checkModules.Substring(8)
    Write-Host "[WARNING] Missing Python packages: $missingList" -ForegroundColor Yellow
    Write-Host "[PRE-FLIGHT] Installing missing packages from requirements.txt..." -ForegroundColor Cyan
    python -m pip install -r requirements.txt
} else {
    Write-Host "[PRE-FLIGHT] All critical Python packages are installed." -ForegroundColor Green
}

# 3. Environment Variables
$env:PYTHONPATH = "$ScriptDir;$env:PYTHONPATH"
$env:VERIPULSE_MODE = $Mode
$env:AWS_DEFAULT_REGION = $(if ($env:AWS_DEFAULT_REGION) { $env:AWS_DEFAULT_REGION } else { "us-east-1" })

# 4. Launch Next.js Dashboard in background if requested
$dashboardProc = $null
if ($WithDashboard) {
    $dashboardDir = Join-Path $ScriptDir "dashboard"
    if (Test-Path $dashboardDir) {
        Write-Host "[DASHBOARD] Starting Next.js 14 WebGL Digital Twin on http://localhost:3000..." -ForegroundColor Magenta
        $dashboardProc = Start-Process -FilePath "npm" -ArgumentList "run dev" -WorkingDirectory $dashboardDir -PassThru -NoNewWindow
    }
}

# 5. Build Orchestrator Command Arguments
$orchArgs = @("run_veripulse.py", "--mode", $Mode, "--fps", "$Fps")

if ($NoStreamer) { $orchArgs += "--no-streamer" }
if ($NoEdge)     { $orchArgs += "--no-edge" }
if ($NoPlc)      { $orchArgs += "--no-plc" }
if ($NoCool)     { $orchArgs += "--no-cool" }
if ($NoGateway)  { $orchArgs += "--no-gateway" }
if ($NoAgent)    { $orchArgs += "--no-agent" }
if ($TimeoutSec -gt 0) { $orchArgs += @("--timeout", "$TimeoutSec") }

# 6. Execute Orchestrator
Write-Host "[LAUNCH] Executing VeriPulse Orchestrator..." -ForegroundColor Green
try {
    & python $orchArgs
} finally {
    if ($dashboardProc -and -not $dashboardProc.HasExited) {
        Write-Host "[CLEANUP] Stopping Next.js dashboard process (PID: $($dashboardProc.Id))..." -ForegroundColor Yellow
        Stop-Process -Id $dashboardProc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "[EXIT] VeriPulse launcher exited cleanly." -ForegroundColor Green
}
