param()

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
$SourceVideo = 'Q:\20260521-120258.mp4'
$ProjectName = 'runs/lock_target_tuning'
$DocsTuningDir = Join-Path $Root 'docs/tuning'
$ProgressFile = Join-Path $DocsTuningDir 'offline_tuning_progress.md'
$ResultsFile = Join-Path $DocsTuningDir 'offline_tuning_results.md'
$LogDir = Join-Path $Root 'runs/offline_tuning_logs'
$LiveLog = Join-Path $LogDir 'offline_tuning_live.log'

New-Item -ItemType Directory -Path $DocsTuningDir -Force | Out-Null
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$experiments = @()
$experiments += [pscustomobject]@{
    'id' = 'G1'
    'name' = 'detect_img1152'
    'params' = @('--imgsz', '1152')
    'note' = 'Detect upsize'
    'status' = 'pending'
}
$experiments += [pscustomobject]@{
    'id' = 'G2'
    'name' = 'face_recall_boost'
    'params' = @('--face-scale-factor', '1.03', '--face-min-confidence', '0.25')
    'note' = 'Face recall boost'
    'status' = 'pending'
}
$experiments += [pscustomobject]@{
    'id' = 'G3'
    'name' = 'reacquire_loose'
    'params' = @('--min-appearance', '0.32', '--reacquire-thresh', '0.42')
    'note' = 'Looser reacquire'
    'status' = 'pending'
}
$experiments += [pscustomobject]@{
    'id' = 'G4'
    'name' = 'reacquire_strict'
    'params' = @('--min-appearance', '0.38', '--reacquire-thresh', '0.48')
    'note' = 'Stricter reacquire'
    'status' = 'pending'
}
$experiments += [pscustomobject]@{
    'id' = 'G5'
    'name' = 'reid_interval_8'
    'params' = @('--reid-interval', '8')
    'note' = 'Lower ReID refresh'
    'status' = 'pending'
}
$experiments += [pscustomobject]@{
    'id' = 'G6'
    'name' = 'mtcnn_interval_3'
    'params' = @('--mtcnn-interval', '3')
    'note' = 'Lower MTCNN refresh'
    'status' = 'pending'
}
$experiments += [pscustomobject]@{
    'id' = 'G7'
    'name' = 'light_balanced'
    'params' = @('--reid-interval', '4', '--mtcnn-interval', '2')
    'note' = 'Balanced light preset'
    'status' = 'pending'
}

function Write-LiveLog {
    param([string]$Message)
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LiveLog -Value "[$stamp] $Message"
}

function Update-ProgressFile {
    param(
        [string]$State,
        [string]$CurrentExperiment,
        [array]$ExperimentRows,
        [string]$ExtraNote = ''
    )

    $lines = @(
        '# Offline Tuning Progress',
        '',
        '## Status',
        '',
        "- State: $State",
        "- Last update: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
        "- Current experiment: $CurrentExperiment",
        "- Source video: $SourceVideo",
        "- Python: $Python",
        "- Live log: runs/offline_tuning_logs/offline_tuning_live.log",
        "- Results table: docs/tuning/offline_tuning_results.md",
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
    foreach ($exp in $ExperimentRows) {
        $paramText = if ($exp.params.Count -gt 0) { ($exp.params -join ' ') } else { 'baseline' }
        $lines += "| $($exp.id) | $($exp.name) | $paramText | $($exp.status) | $($exp.note) |"
    }
    $lines += ''
    $lines += '## Execution Log'
    $lines += ''
    if (Test-Path $LiveLog) {
        $tail = Get-Content $LiveLog -Tail 20
        foreach ($line in $tail) {
            $lines += "- $line"
        }
    }
    Set-Content -Path $ProgressFile -Value $lines -Encoding UTF8
}

function Get-LockModeCounts {
    param([string]$FrameMetricsPath)
    $items = Get-Content $FrameMetricsPath -Raw | ConvertFrom-Json
    $grouped = $items | Group-Object lock_mode
    $map = @{}
    foreach ($g in $grouped) {
        $map[$g.Name] = $g.Count
    }
    return @{ FACE_LOCK = ($map['FACE_LOCK'] | ForEach-Object { $_ }) ; HEAD_PROXY = ($map['HEAD_PROXY'] | ForEach-Object { $_ }) ; LOST = ($map['LOST'] | ForEach-Object { $_ }) }
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
        face_lock = [int]($lockCounts['FACE_LOCK'] | ForEach-Object { if ($_ -eq $null) { 0 } else { $_ } })
        head_proxy = [int]($lockCounts['HEAD_PROXY'] | ForEach-Object { if ($_ -eq $null) { 0 } else { $_ } })
        lost = [int]($lockCounts['LOST'] | ForEach-Object { if ($_ -eq $null) { 0 } else { $_ } })
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

Write-LiveLog 'Experiment runner initialized.'
Update-ProgressFile -State 'setup' -CurrentExperiment 'preparing baselines' -ExperimentRows $experiments -ExtraNote 'Preparing baseline comparisons and starting offline runs.'

$baselineFull = Load-RunMetrics -SummaryPath (Join-Path $Root 'runs/lock_target/offline_run/20260521-120258_summary.json') -PerformancePath (Join-Path $Root 'runs/lock_target/offline_run/20260521-120258_performance.json') -FrameMetricsPath (Join-Path $Root 'runs/lock_target/offline_run/20260521-120258_frame_metrics.json') -Id 'baseline_full' -Name 'offline_run' -Params 'baseline full'
$baselineLight = Load-RunMetrics -SummaryPath (Join-Path $Root 'runs/lock_target/offline_run_light/20260521-120258_summary.json') -PerformancePath (Join-Path $Root 'runs/lock_target/offline_run_light/20260521-120258_performance.json') -FrameMetricsPath (Join-Path $Root 'runs/lock_target/offline_run_light/20260521-120258_frame_metrics.json') -Id 'baseline_light' -Name 'offline_run_light' -Params 'lightweight preset'
$resultRows = @()
Write-ResultsTable -baselineFull $baselineFull -baselineLight $baselineLight -rows $resultRows

foreach ($exp in $experiments) {
    $exp.status = 'running'
    Update-ProgressFile -State 'running' -CurrentExperiment $exp.name -ExperimentRows $experiments -ExtraNote $exp.note
    Write-LiveLog "Starting $($exp.id) $($exp.name)"

    $baseArgs = @(
        'lock_target.py',
        '--source', $SourceVideo,
        '--model', 'yolo26n.pt',
        '--tracker', 'cfg/trackers/botsort.yaml',
        '--reid-model', 'yolo26l.pt',
        '--classes', '0',
        '--conf', '0.25',
        '--iou', '0.5',
        '--imgsz', '960',
        '--initial-track-id', '1',
        '--fallback-to-first-face',
        '--project', $ProjectName,
        '--name', $exp.name,
        '--save-all-boxes'
    )
    $cmdArgs = $baseArgs + $exp.params
    $expLog = Join-Path $LogDir ($exp.name + '.log')
    $expStdOut = Join-Path $LogDir ($exp.name + '.stdout.log')
    $expStdErr = Join-Path $LogDir ($exp.name + '.stderr.log')

    Push-Location $Root
    try {
        if (Test-Path $expStdOut) { Remove-Item $expStdOut -Force }
        if (Test-Path $expStdErr) { Remove-Item $expStdErr -Force }
        if (Test-Path $expLog) { Remove-Item $expLog -Force }

        $proc = Start-Process -FilePath $Python -ArgumentList $cmdArgs -NoNewWindow -Wait -PassThru -RedirectStandardOutput $expStdOut -RedirectStandardError $expStdErr
        if (Test-Path $expStdOut) { Get-Content $expStdOut | Set-Content $expLog }
        if (Test-Path $expStdErr) { Get-Content $expStdErr | Add-Content $expLog }

        if ($proc.ExitCode -ne 0) {
            throw "Experiment $($exp.name) failed with exit code $($proc.ExitCode)"
        }
    }
    finally {
        Pop-Location
    }

    $stem = [System.IO.Path]::GetFileNameWithoutExtension($SourceVideo)
    $runDir = Join-Path $Root (Join-Path $ProjectName $exp.name)
    $summaryPath = Join-Path $runDir ($stem + '_summary.json')
    $performancePath = Join-Path $runDir ($stem + '_performance.json')
    $frameMetricsPath = Join-Path $runDir ($stem + '_frame_metrics.json')

    $row = Load-RunMetrics -SummaryPath $summaryPath -PerformancePath $performancePath -FrameMetricsPath $frameMetricsPath -Id $exp.id -Name $exp.name -Params ($exp.params -join ' ')
    $resultRows += $row
    Write-ResultsTable -baselineFull $baselineFull -baselineLight $baselineLight -rows $resultRows

    $exp.status = 'completed'
    Update-ProgressFile -State 'running' -CurrentExperiment 'post-processing next experiment' -ExperimentRows $experiments -ExtraNote ("Completed " + $exp.name)
    Write-LiveLog "Completed $($exp.id) $($exp.name) fps=$($row.fps) runtime=$($row.runtime_sec)"
}

Update-ProgressFile -State 'completed' -CurrentExperiment 'all experiments finished' -ExperimentRows $experiments -ExtraNote 'All offline experiments completed successfully.'
Write-LiveLog 'All experiments completed successfully.'