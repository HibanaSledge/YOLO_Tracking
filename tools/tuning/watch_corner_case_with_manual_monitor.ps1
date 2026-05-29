param(
    [string]$SourceVideo = 'Q:\20260528-160426.mp4',
    [string]$RunId = 'corner_20260528_160426',
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
$ProjectName = "runs/lock_target_corner_cases/$RunId"
$LogDir = Join-Path $Root "runs/corner_case_tuning_logs/$RunId"
$LiveLog = Join-Path $LogDir 'corner_case_tuning_live.log'
$MonitorScript = Join-Path $Root 'tools/tuning/monitor_manual_offline_experiment.ps1'

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$experiments = @(
    [pscustomobject]@{ id = 'C0'; name = 'corner_baseline'; params = 'baseline full' },
    [pscustomobject]@{ id = 'C1'; name = 'corner_img1152'; params = '--imgsz 1152' },
    [pscustomobject]@{ id = 'C2'; name = 'corner_conf020'; params = '--conf 0.20' },
    [pscustomobject]@{ id = 'C3'; name = 'corner_face_scale103'; params = '--face-scale-factor 1.03' },
    [pscustomobject]@{ id = 'C4'; name = 'corner_face_conf025'; params = '--face-min-confidence 0.25' },
    [pscustomobject]@{ id = 'C5'; name = 'corner_reacq_loose'; params = '--min-appearance 0.30 --reacquire-thresh 0.40' },
    [pscustomobject]@{ id = 'C6'; name = 'corner_reacq_strict'; params = '--min-appearance 0.40 --reacquire-thresh 0.50' },
    [pscustomobject]@{ id = 'C7'; name = 'corner_control_stable'; params = '--control-alpha 0.82 --control-max-step 25' },
    [pscustomobject]@{ id = 'C8'; name = 'corner_mtcnn2'; params = '--mtcnn-interval 2' }
)

function Write-LiveLog {
    param([string]$Message)
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LiveLog -Value "[$stamp] $Message"
}

function Test-ExperimentComplete {
    param([pscustomobject]$Experiment)
    $runDir = Join-Path $Root (Join-Path $ProjectName $Experiment.name)
    $summary = Join-Path $runDir ($SourceStem + '_summary.json')
    $performance = Join-Path $runDir ($SourceStem + '_performance.json')
    $frameMetrics = Join-Path $runDir ($SourceStem + '_frame_metrics.json')
    return (Test-Path $summary) -and (Test-Path $performance) -and (Test-Path $frameMetrics)
}

function Find-ExperimentProcess {
    param([pscustomobject]$Experiment)
    $needleProject = "--project $ProjectName"
    $needleName = "--name $($Experiment.name)"
    $needleSource = "--source $SourceVideo"
    return Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object {
            $_.CommandLine -like "*$needleSource*" -and
            $_.CommandLine -like "*$needleProject*" -and
            $_.CommandLine -like "*$needleName*"
        } |
        Select-Object -First 1
}

Write-LiveLog "Manual monitor supervisor started for corner-case run_id=$RunId"

while ($true) {
    $completed = @($experiments | Where-Object { Test-ExperimentComplete -Experiment $_ })
    if ($completed.Count -eq $experiments.Count) {
        Write-LiveLog "Manual monitor supervisor finished: all C0-C8 outputs are complete."
        break
    }

    $attached = $false
    foreach ($exp in $experiments) {
        if (Test-ExperimentComplete -Experiment $exp) { continue }
        $proc = Find-ExperimentProcess -Experiment $exp
        if ($null -ne $proc) {
            Write-LiveLog "Manual monitor supervisor attaching $($exp.id) $($exp.name) pid=$($proc.ProcessId)"
            & $MonitorScript `
                -ProcessId ([int]$proc.ProcessId) `
                -ExperimentId $exp.id `
                -ExperimentName $exp.name `
                -ParamsText $exp.params `
                -PollSeconds $PollSeconds `
                -ExperimentSet corner `
                -SourceVideo $SourceVideo `
                -RunId $RunId
            $attached = $true
            break
        }
    }

    if (-not $attached) {
        Write-LiveLog "Manual monitor supervisor waiting for active corner-case python process; completed=$($completed.Count)/$($experiments.Count)"
        Start-Sleep -Seconds 10
    }
}
