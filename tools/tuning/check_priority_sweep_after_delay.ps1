param(
    [string]$SourceVideo = 'Q:\20260528-160426.mp4',
    [string]$RunId = 'priority_sweep_20260529',
    [int]$DelaySeconds = 10800,
    [int]$PollSeconds = 30
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = $ScriptDir
while (-not (Test-Path (Join-Path $Root 'lock_target.py'))) {
    $Parent = Split-Path -Parent $Root
    if ([string]::IsNullOrWhiteSpace($Parent) -or $Parent -eq $Root) {
        throw "Failed to locate repository root from $ScriptDir"
    }
    $Root = $Parent
}

$SourceStem = [System.IO.Path]::GetFileNameWithoutExtension($SourceVideo)
$ProjectName = "runs/lock_target_priority_sweep/$RunId"
$LogDir = Join-Path $Root "runs/priority_sweep_logs/$RunId"
$LiveLog = Join-Path $LogDir 'priority_sweep_live.log'
$RunScript = Join-Path $Root 'tools/tuning/run_priority_sweep_tuning.ps1'
$AnalyzeScript = Join-Path $Root 'tools/tuning/analyze_priority_sweep_results.ps1'

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$experiments = @(
    'priority_baseline',
    'priority_reid_interval4',
    'priority_reid_interval6',
    'priority_reid_interval8',
    'priority_reid_interval10',
    'priority_face_scale102',
    'priority_face_scale103',
    'priority_face_scale104',
    'priority_face_conf025',
    'priority_face_conf028',
    'priority_detector_yolo26l',
    'priority_reid_yolo26n'
)

function Write-LiveLog {
    param([string]$Message)
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LiveLog -Value "[$stamp] $Message"
}

function Test-ExperimentComplete {
    param([string]$Name)
    $runDir = Join-Path $Root (Join-Path $ProjectName $Name)
    $summary = Join-Path $runDir ($SourceStem + '_summary.json')
    $performance = Join-Path $runDir ($SourceStem + '_performance.json')
    $frameMetrics = Join-Path $runDir ($SourceStem + '_frame_metrics.json')
    return (Test-Path $summary) -and (Test-Path $performance) -and (Test-Path $frameMetrics)
}

function Get-ActivePriorityProcesses {
    return @(Get-CimInstance Win32_Process |
        Where-Object {
            ($_.Name -match 'powershell|pwsh|python') -and
            ($_.CommandLine -match 'run_priority_sweep_tuning|lock_target.py') -and
            ($_.CommandLine -match [regex]::Escape($RunId))
        })
}

Write-LiveLog "Delayed priority sweep check scheduled delay_seconds=$DelaySeconds"
Start-Sleep -Seconds $DelaySeconds

$missing = @($experiments | Where-Object { -not (Test-ExperimentComplete -Name $_) })
if ($missing.Count -eq 0) {
    Write-LiveLog 'Delayed check: P0-P11 complete; starting priority sweep analysis.'
    & $AnalyzeScript -SourceVideo $SourceVideo -RunId $RunId
    exit $LASTEXITCODE
}

$active = Get-ActivePriorityProcesses
$missingText = ($missing -join ', ')
if ($active.Count -gt 0) {
    $activeText = (($active | Select-Object -ExpandProperty ProcessId) -join ', ')
    Write-LiveLog "Delayed check: experiments still running; missing=$missingText active_pids=$activeText"
    exit 0
}

Write-LiveLog "Delayed check: incomplete and no active process; missing=$missingText. Restarting supervisor."
$args = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', $RunScript,
    '-SourceVideo', $SourceVideo,
    '-RunId', $RunId,
    '-PollSeconds', [string]$PollSeconds
)
$proc = Start-Process -FilePath 'powershell.exe' -ArgumentList $args -WorkingDirectory $Root -WindowStyle Minimized -PassThru
Write-LiveLog "Delayed check restarted supervisor pid=$($proc.Id)"