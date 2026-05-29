param(
    [Parameter(Mandatory = $true)]
    [int]$ProcessId,

    [Parameter(Mandatory = $true)]
    [string]$ExperimentId,

    [Parameter(Mandatory = $true)]
    [string]$ExperimentName,

    [Parameter(Mandatory = $true)]
    [string]$ParamsText,

    [int]$PollSeconds = 30,

    [ValidateSet('offline', 'corner')]
    [string]$ExperimentSet = 'offline',

    [string]$SourceVideo = '',

    [string]$ProjectName = '',

    [string]$ProgressFileName = '',

    [string]$ResultsFileName = '',

    [string]$LogDirRelative = '',

    [string]$LiveLogFileName = '',

    [string]$RunId = ''
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
$Python = 'C:/Users/Stuart.Cai/AppData/Local/Programs/Python/Python310/python.exe'
if ([string]::IsNullOrWhiteSpace($SourceVideo)) {
    if ($ExperimentSet -eq 'corner') { $SourceVideo = 'Q:\20260528-160426.mp4' }
    else { $SourceVideo = 'Q:\20260521-120258.mp4' }
}
if ([string]::IsNullOrWhiteSpace($RunId) -and $ExperimentSet -eq 'corner') { $RunId = 'corner_20260528_160426' }
if ([string]::IsNullOrWhiteSpace($ProjectName)) {
    if ($ExperimentSet -eq 'corner') { $ProjectName = "runs/lock_target_corner_cases/$RunId" }
    else { $ProjectName = 'runs/lock_target_tuning' }
}
if ([string]::IsNullOrWhiteSpace($ProgressFileName)) {
    if ($ExperimentSet -eq 'corner') { $ProgressFileName = "corner_case_tuning_progress_$RunId.md" }
    else { $ProgressFileName = 'offline_tuning_progress.md' }
}
if ([string]::IsNullOrWhiteSpace($ResultsFileName)) {
    if ($ExperimentSet -eq 'corner') { $ResultsFileName = "corner_case_tuning_results_$RunId.md" }
    else { $ResultsFileName = 'offline_tuning_results.md' }
}
if ([string]::IsNullOrWhiteSpace($LogDirRelative)) {
    if ($ExperimentSet -eq 'corner') { $LogDirRelative = "runs/corner_case_tuning_logs/$RunId" }
    else { $LogDirRelative = 'runs/offline_tuning_logs' }
}
if ([string]::IsNullOrWhiteSpace($LiveLogFileName)) {
    if ($ExperimentSet -eq 'corner') { $LiveLogFileName = 'corner_case_tuning_live.log' }
    else { $LiveLogFileName = 'offline_tuning_live.log' }
}
$SourceStem = [System.IO.Path]::GetFileNameWithoutExtension($SourceVideo)
$DocsTuningDir = Join-Path $Root 'docs/tuning'
$ProgressFile = Join-Path $DocsTuningDir $ProgressFileName
$ResultsFile = Join-Path $DocsTuningDir $ResultsFileName
$LogDir = Join-Path $Root $LogDirRelative
$LiveLog = Join-Path $LogDir $LiveLogFileName

New-Item -ItemType Directory -Path $DocsTuningDir -Force | Out-Null
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

if ($ExperimentSet -eq 'corner') {
    $experiments = @(
        [pscustomobject]@{ id = 'C0'; name = 'corner_baseline'; params = 'baseline full'; note = 'Same-source baseline' },
        [pscustomobject]@{ id = 'C1'; name = 'corner_img1152'; params = '--imgsz 1152'; note = 'Detect upsize' },
        [pscustomobject]@{ id = 'C2'; name = 'corner_conf020'; params = '--conf 0.20'; note = 'Weak-detection recall' },
        [pscustomobject]@{ id = 'C3'; name = 'corner_face_scale103'; params = '--face-scale-factor 1.03'; note = 'Classical face recall' },
        [pscustomobject]@{ id = 'C4'; name = 'corner_face_conf025'; params = '--face-min-confidence 0.25'; note = 'MTCNN face recall' },
        [pscustomobject]@{ id = 'C5'; name = 'corner_reacq_loose'; params = '--min-appearance 0.30 --reacquire-thresh 0.40'; note = 'Looser reacquire' },
        [pscustomobject]@{ id = 'C6'; name = 'corner_reacq_strict'; params = '--min-appearance 0.40 --reacquire-thresh 0.50'; note = 'Stricter reacquire' },
        [pscustomobject]@{ id = 'C7'; name = 'corner_control_stable'; params = '--control-alpha 0.82 --control-max-step 25'; note = 'Stable control center' },
        [pscustomobject]@{ id = 'C8'; name = 'corner_mtcnn2'; params = '--mtcnn-interval 2'; note = 'MTCNN interval boundary' }
    )
}
else {
    $experiments = @(
        [pscustomobject]@{ id = 'G1'; name = 'detect_img1152'; params = '--imgsz 1152'; note = 'Detect upsize' },
        [pscustomobject]@{ id = 'G2'; name = 'face_recall_boost'; params = '--face-scale-factor 1.03 --face-min-confidence 0.25'; note = 'Face recall boost' },
        [pscustomobject]@{ id = 'G3'; name = 'reacquire_loose'; params = '--min-appearance 0.32 --reacquire-thresh 0.42'; note = 'Looser reacquire' },
        [pscustomobject]@{ id = 'G4'; name = 'reacquire_strict'; params = '--min-appearance 0.38 --reacquire-thresh 0.48'; note = 'Stricter reacquire' },
        [pscustomobject]@{ id = 'G5'; name = 'reid_interval_8'; params = '--reid-interval 8'; note = 'Lower ReID refresh' },
        [pscustomobject]@{ id = 'G6'; name = 'mtcnn_interval_3'; params = '--mtcnn-interval 3'; note = 'Lower MTCNN refresh' },
        [pscustomobject]@{ id = 'G7'; name = 'light_balanced'; params = '--reid-interval 4 --mtcnn-interval 2'; note = 'Balanced light preset' }
    )
}

function Write-LiveLog {
    param([string]$Message)
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LiveLog -Value "[$stamp] $Message"
}

function Get-LockModeCounts {
    param([string]$FrameMetricsPath)

    $items = Get-Content $FrameMetricsPath -Raw | ConvertFrom-Json
    $counts = @{ FACE_LOCK = 0; HEAD_PROXY = 0; LOST = 0 }
    foreach ($item in $items) {
        if ($null -ne $item.lock_mode -and $counts.ContainsKey([string]$item.lock_mode)) {
            $counts[[string]$item.lock_mode] += 1
        }
    }
    return $counts
}

function Load-RunMetrics {
    param(
        [string]$SummaryPath,
        [string]$PerformancePath,
        [string]$FrameMetricsPath,
        [string]$Id,
        [string]$Name,
        [string]$Params
    )

    $summary = Get-Content $SummaryPath -Raw | ConvertFrom-Json
    $performance = Get-Content $PerformancePath -Raw | ConvertFrom-Json
    $lockCounts = Get-LockModeCounts -FrameMetricsPath $FrameMetricsPath

    return [ordered]@{
        id = $Id
        name = $Name
        params = $Params
        runtime_sec = [double]$summary.runtime_sec
        fps = [double]$summary.effective_fps
        face_lock = [int]$lockCounts['FACE_LOCK']
        head_proxy = [int]$lockCounts['HEAD_PROXY']
        lost = [int]$lockCounts['LOST']
        tracker_switches = [int]$summary.tracker_switches
        reacquired = [int]$summary.reacquired_count
        face_detected = [int]$summary.face_detected_frames
        face_misses = [int]$summary.total_face_misses
        embedding_calls = [int]$performance.counts.embedding_calls.total
        mtcnn_calls = [int]$performance.counts.face_detect_mtcnn_calls.total
    }
}

function Compare-Quality {
    param($baseline, $row)

    $parts = @()
    if ($row.face_lock -gt $baseline.face_lock) { $parts += "FACE_LOCK +$($row.face_lock - $baseline.face_lock)" }
    elseif ($row.face_lock -lt $baseline.face_lock) { $parts += "FACE_LOCK $($row.face_lock - $baseline.face_lock)" }
    else { $parts += 'FACE_LOCK =0' }

    if ($row.head_proxy -gt $baseline.head_proxy) { $parts += "HEAD_PROXY +$($row.head_proxy - $baseline.head_proxy)" }
    elseif ($row.head_proxy -lt $baseline.head_proxy) { $parts += "HEAD_PROXY $($row.head_proxy - $baseline.head_proxy)" }
    else { $parts += 'HEAD_PROXY =0' }

    if ($row.tracker_switches -gt $baseline.tracker_switches) { $parts += "switch +$($row.tracker_switches - $baseline.tracker_switches)" }
    elseif ($row.tracker_switches -lt $baseline.tracker_switches) { $parts += "switch $($row.tracker_switches - $baseline.tracker_switches)" }
    else { $parts += 'switch =0' }

    return ($parts -join '; ')
}

function Compare-Speed {
    param($baseline, $row)

    $fpsDelta = [math]::Round(($row.fps - $baseline.fps), 3)
    $runtimeDelta = [math]::Round(($row.runtime_sec - $baseline.runtime_sec), 3)
    return "fps $fpsDelta; runtime $runtimeDelta sec"
}

function Write-ResultsTable {
    param(
        $baselineFull,
        $baselineLight,
        [array]$rows
    )

    if ($ExperimentSet -eq 'corner') {
        $baseline = $rows | Where-Object { $_.id -eq 'C0' } | Select-Object -First 1
        $lines = @(
            '# Corner Case Tuning Results',
            '',
            "- Source video: $SourceVideo",
            "- Run ID: $RunId",
            "- Project: $ProjectName",
            "- Live log: $LogDirRelative/$LiveLogFileName",
            '',
            '## Experiment Table',
            '',
            '| ID | Name | Params | Runtime Sec | FPS | FACE_LOCK | HEAD_PROXY | LOST | Tracker Switches | Reacquired | Face Detected | Face Misses | Embedding Calls | MTCNN Calls | Quality vs C0 | Speed vs C0 |',
            '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |'
        )

        foreach ($row in $rows) {
            if ($null -ne $baseline) {
                $quality = Compare-Quality -baseline $baseline -row $row
                $speed = Compare-Speed -baseline $baseline -row $row
            }
            else {
                $quality = 'pending C0 baseline'
                $speed = 'pending C0 baseline'
            }
            $lines += "| $($row.id) | $($row.name) | $($row.params) | $([math]::Round($row.runtime_sec, 3)) | $([math]::Round($row.fps, 3)) | $($row.face_lock) | $($row.head_proxy) | $($row.lost) | $($row.tracker_switches) | $($row.reacquired) | $($row.face_detected) | $($row.face_misses) | $($row.embedding_calls) | $($row.mtcnn_calls) | $quality | $speed |"
        }

        $lines += ''
        $lines += '## Notes'
        $lines += ''
        $lines += '- Monitor output is updated by tools/tuning/monitor_manual_offline_experiment.ps1 in corner mode.'
        $lines += '- Final conclusions still require summary.json, frame_metrics.json, performance.json, and manual key-frame review.'
        Set-Content -Path $ResultsFile -Value $lines -Encoding UTF8
        return
    }

    $lines = @(
        '# Offline Tuning Results',
        '',
        '## Experiment Table',
        '',
        '| ID | Name | Params | Runtime Sec | FPS | FACE_LOCK | HEAD_PROXY | LOST | Tracker Switches | Reacquired | Face Detected | Face Misses | Embedding Calls | MTCNN Calls | Quality vs Full | Speed vs Full | Quality vs Light | Speed vs Light |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |'
    )

    $allRows = @($baselineFull, $baselineLight) + $rows
    foreach ($row in $allRows) {
        $qf = Compare-Quality -baseline $baselineFull -row $row
        $sf = Compare-Speed -baseline $baselineFull -row $row
        $ql = Compare-Quality -baseline $baselineLight -row $row
        $sl = Compare-Speed -baseline $baselineLight -row $row
        $lines += "| $($row.id) | $($row.name) | $($row.params) | $([math]::Round($row.runtime_sec, 3)) | $([math]::Round($row.fps, 3)) | $($row.face_lock) | $($row.head_proxy) | $($row.lost) | $($row.tracker_switches) | $($row.reacquired) | $($row.face_detected) | $($row.face_misses) | $($row.embedding_calls) | $($row.mtcnn_calls) | $qf | $sf | $ql | $sl |"
    }

    $lines += ''
    $lines += '## Notes'
    $lines += ''
    $lines += '- quality deltas are relative summaries against the current full and lightweight baselines.'
    $lines += '- speed deltas use effective FPS and runtime_sec from summary.json.'
    Set-Content -Path $ResultsFile -Value $lines -Encoding UTF8
}

function Get-CompletedRows {
    $rows = @()
    foreach ($exp in $experiments) {
        $runDir = Join-Path $Root (Join-Path $ProjectName $exp.name)
        $summaryPath = Join-Path $runDir ($SourceStem + '_summary.json')
        $performancePath = Join-Path $runDir ($SourceStem + '_performance.json')
        $frameMetricsPath = Join-Path $runDir ($SourceStem + '_frame_metrics.json')
        if ((Test-Path $summaryPath) -and (Test-Path $performancePath) -and (Test-Path $frameMetricsPath)) {
            $rows += Load-RunMetrics -SummaryPath $summaryPath -PerformancePath $performancePath -FrameMetricsPath $frameMetricsPath -Id $exp.id -Name $exp.name -Params $exp.params
        }
    }
    return $rows
}

function Get-ExperimentRows {
    param(
        [bool]$PidAlive,
        [string]$HeartbeatNote
    )

    $rows = @()
    foreach ($exp in $experiments) {
        $runDir = Join-Path $Root (Join-Path $ProjectName $exp.name)
        $summaryPath = Join-Path $runDir ($SourceStem + '_summary.json')
        $performancePath = Join-Path $runDir ($SourceStem + '_performance.json')
        $frameMetricsPath = Join-Path $runDir ($SourceStem + '_frame_metrics.json')
        $status = 'pending'
        $note = $exp.note

        if ((Test-Path $summaryPath) -and (Test-Path $performancePath) -and (Test-Path $frameMetricsPath)) {
            $status = 'completed'
            $note = 'JSON ready'
        }
        elseif ($exp.id -eq $ExperimentId) {
            if ($PidAlive) {
                $status = 'running'
                $note = $HeartbeatNote
            }
            else {
                $status = 'failed'
                $note = 'Process exited before JSON outputs were complete'
            }
        }

        $rows += [pscustomobject]@{
            id = $exp.id
            name = $exp.name
            params = $exp.params
            status = $status
            note = $note
        }
    }
    return $rows
}

function Update-ProgressFile {
    param(
        [string]$State,
        [string]$CurrentExperiment,
        [string]$ExtraNote,
        [bool]$PidAlive,
        [string]$HeartbeatNote
    )

    $experimentRows = Get-ExperimentRows -PidAlive $PidAlive -HeartbeatNote $HeartbeatNote
    $progressTitle = '# Offline Tuning Progress'
    if ($ExperimentSet -eq 'corner') { $progressTitle = '# Corner Case Tuning Progress' }
    $lines = @(
        $progressTitle,
        '',
        '## Status',
        '',
        "- State: $State",
        "- Last update: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
        "- Current experiment: $CurrentExperiment",
        "- Source video: $SourceVideo",
        "- Python: $Python",
        "- Live log: $LogDirRelative/$LiveLogFileName",
        "- Results table: docs/tuning/$ResultsFileName",
        ''
    )
    if ($ExtraNote) {
        $lines += "- Note: $ExtraNote"
        $lines += ''
    }
    $lines += '## Planned Experiments'
    $lines += ''
    $lines += '| ID | Name | Parameter Changes | Status | Notes |'
    $lines += '| --- | --- | --- | --- | --- |'
    foreach ($exp in $experimentRows) {
        $lines += "| $($exp.id) | $($exp.name) | $($exp.params) | $($exp.status) | $($exp.note) |"
    }
    $lines += ''
    $lines += '## Execution Log'
    $lines += ''
    if (Test-Path $LiveLog) {
        foreach ($line in (Get-Content $LiveLog -Tail 20)) {
            $lines += "- $line"
        }
    }
    Set-Content -Path $ProgressFile -Value $lines -Encoding UTF8
}

$baselineFull = $null
$baselineLight = $null
if ($ExperimentSet -eq 'offline') {
    $baselineFull = Load-RunMetrics -SummaryPath (Join-Path $Root 'runs/lock_target/offline_run/20260521-120258_summary.json') -PerformancePath (Join-Path $Root 'runs/lock_target/offline_run/20260521-120258_performance.json') -FrameMetricsPath (Join-Path $Root 'runs/lock_target/offline_run/20260521-120258_frame_metrics.json') -Id 'baseline_full' -Name 'offline_run' -Params 'baseline full'
    $baselineLight = Load-RunMetrics -SummaryPath (Join-Path $Root 'runs/lock_target/offline_run_light/20260521-120258_summary.json') -PerformancePath (Join-Path $Root 'runs/lock_target/offline_run_light/20260521-120258_performance.json') -FrameMetricsPath (Join-Path $Root 'runs/lock_target/offline_run_light/20260521-120258_frame_metrics.json') -Id 'baseline_light' -Name 'offline_run_light' -Params 'lightweight preset'
}

$outputVideo = Join-Path $Root (Join-Path $ProjectName (Join-Path $ExperimentName ($SourceStem + '_locked.mp4')))
$lastSize = -1

Write-LiveLog "Manual monitor attached to $ExperimentId $ExperimentName pid=$ProcessId params=$ParamsText"

while ($true) {
    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    $pidAlive = $null -ne $proc
    $sizeText = 'mp4 missing'

    if (Test-Path $outputVideo) {
        $fileInfo = [System.IO.FileInfo]::new($outputVideo)
        $fileInfo.Refresh()
        $sizeText = "mp4_bytes=$($fileInfo.Length)"
        if ($fileInfo.Length -ne $lastSize) {
            Write-LiveLog "Heartbeat $ExperimentId pid=$ProcessId $sizeText"
            $lastSize = $fileInfo.Length
        }
    }

    if (-not $pidAlive) {
        break
    }

    Update-ProgressFile -State 'running-manual' -CurrentExperiment $ExperimentName -ExtraNote ("Manual monitor active for $ExperimentId, PID $ProcessId") -PidAlive $true -HeartbeatNote ("PID $ProcessId active, $sizeText")
    Start-Sleep -Seconds $PollSeconds
}

$completedRows = Get-CompletedRows
Write-ResultsTable -baselineFull $baselineFull -baselineLight $baselineLight -rows $completedRows

$runDir = Join-Path $Root (Join-Path $ProjectName $ExperimentName)
$summaryPath = Join-Path $runDir ($SourceStem + '_summary.json')
$performancePath = Join-Path $runDir ($SourceStem + '_performance.json')
$frameMetricsPath = Join-Path $runDir ($SourceStem + '_frame_metrics.json')

if ((Test-Path $summaryPath) -and (Test-Path $performancePath) -and (Test-Path $frameMetricsPath)) {
    $row = Load-RunMetrics -SummaryPath $summaryPath -PerformancePath $performancePath -FrameMetricsPath $frameMetricsPath -Id $ExperimentId -Name $ExperimentName -Params $ParamsText
    Write-LiveLog "Completed $ExperimentId $ExperimentName fps=$([math]::Round($row.fps, 3)) runtime=$([math]::Round($row.runtime_sec, 3))"
    Update-ProgressFile -State 'ready-for-next-manual' -CurrentExperiment 'waiting for next manual launch' -ExtraNote ("Completed $ExperimentId. Results table updated.") -PidAlive $false -HeartbeatNote 'JSON ready'
}
else {
    Write-LiveLog "Failed ${ExperimentId} ${ExperimentName}: process exited before JSON outputs were complete"
    Update-ProgressFile -State 'manual-run-failed' -CurrentExperiment $ExperimentName -ExtraNote ("$ExperimentId exited without complete JSON outputs. Check logs.") -PidAlive $false -HeartbeatNote 'Process exited before JSON outputs were complete'
}