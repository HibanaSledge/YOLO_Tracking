param(
    [string]$SourceVideo = 'Q:\20260528-160426.mp4',
    [string]$RunId = 'corner_20260528_160426',
    [switch]$Force
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
$SourceStem = [System.IO.Path]::GetFileNameWithoutExtension($SourceVideo)
$ProjectName = "runs/lock_target_corner_cases/$RunId"
$DocsTuningDir = Join-Path $Root 'docs/tuning'
$ResultsFile = Join-Path $DocsTuningDir "corner_case_tuning_results_$RunId.md"
$ProgressFile = Join-Path $DocsTuningDir "corner_case_tuning_progress_$RunId.md"
$LogDir = Join-Path $Root "runs/corner_case_tuning_logs/$RunId"
$LiveLog = Join-Path $LogDir 'corner_case_tuning_live.log'

New-Item -ItemType Directory -Path $DocsTuningDir -Force | Out-Null
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

if (-not (Test-Path $SourceVideo)) {
    throw "Source video not found: $SourceVideo"
}

$experiments = @(
    [pscustomobject]@{ id = 'C0'; name = 'corner_baseline'; focus = 'baseline'; params = @(); paramsText = 'baseline full'; direction = 'Build the same-source baseline for the new corner-case input'; risk = 'Must run first, otherwise later experiments cannot be attributed' },
    [pscustomobject]@{ id = 'C1'; name = 'corner_img1152'; focus = 'imgsz'; params = @('--imgsz', '1152'); paramsText = '--imgsz 1152'; direction = 'Increase detector resolution to test small, blurry, or edge targets'; risk = 'Slower speed; tracker_switches may rise if track distribution changes' },
    [pscustomobject]@{ id = 'C2'; name = 'corner_conf020'; focus = 'conf'; params = @('--conf', '0.20'); paramsText = '--conf 0.20'; direction = 'Lower person confidence threshold to recover weak detections'; risk = 'More false positives and possible identity switches' },
    [pscustomobject]@{ id = 'C3'; name = 'corner_face_scale103'; focus = 'face-scale-factor'; params = @('--face-scale-factor', '1.03'); paramsText = '--face-scale-factor 1.03'; direction = 'Improve classical face recall and observe FACE_LOCK changes'; risk = 'More candidates, slower processing, and more false-face risk' },
    [pscustomobject]@{ id = 'C4'; name = 'corner_face_conf025'; focus = 'face-min-confidence'; params = @('--face-min-confidence', '0.25'); paramsText = '--face-min-confidence 0.25'; direction = 'Relax MTCNN face confidence for side-face, occlusion, and low light'; risk = 'Higher false FACE_LOCK risk; manual key-frame review is required' },
    [pscustomobject]@{ id = 'C5'; name = 'corner_reacq_loose'; focus = 'min-appearance + reacquire-thresh'; params = @('--min-appearance', '0.30', '--reacquire-thresh', '0.40'); paramsText = '--min-appearance 0.30 --reacquire-thresh 0.40'; direction = 'Loosen cross-ID reacquire gates to test recovery after occlusion'; risk = 'More misbind risk in crowded or similar-appearance scenes' },
    [pscustomobject]@{ id = 'C6'; name = 'corner_reacq_strict'; focus = 'min-appearance + reacquire-thresh'; params = @('--min-appearance', '0.40', '--reacquire-thresh', '0.50'); paramsText = '--min-appearance 0.40 --reacquire-thresh 0.50'; direction = 'Tighten cross-ID reacquire gates to reduce wrong recovery'; risk = 'May miss correct recovery and increase LOST or HEAD_PROXY' },
    [pscustomobject]@{ id = 'C7'; name = 'corner_control_stable'; focus = 'control-alpha + control-max-step'; params = @('--control-alpha', '0.82', '--control-max-step', '25'); paramsText = '--control-alpha 0.82 --control-max-step 25'; direction = 'Prioritize gimbal-control stability under jitter'; risk = 'Slower response and possible lag in fast motion' },
    [pscustomobject]@{ id = 'C8'; name = 'corner_mtcnn2'; focus = 'mtcnn-interval'; params = @('--mtcnn-interval', '2'); paramsText = '--mtcnn-interval 2'; direction = 'Reduce real-face refresh frequency alone to test speed-quality boundary'; risk = 'Sparse face refresh may worsen HEAD_PROXY and center offset' }
)

function Write-LiveLog {
    param([string]$Message)
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LiveLog -Value "[$stamp] $Message"
}

function Get-ExperimentPaths {
    param([pscustomobject]$Experiment)

    $runDir = Join-Path $Root (Join-Path $ProjectName $Experiment.name)
    return [pscustomobject]@{
        runDir = $runDir
        summary = Join-Path $runDir ($SourceStem + '_summary.json')
        performance = Join-Path $runDir ($SourceStem + '_performance.json')
        frameMetrics = Join-Path $runDir ($SourceStem + '_frame_metrics.json')
        lockedVideo = Join-Path $runDir ($SourceStem + '_locked.mp4')
        stdout = Join-Path $LogDir ($Experiment.id + '_' + $Experiment.name + '.stdout.log')
        stderr = Join-Path $LogDir ($Experiment.id + '_' + $Experiment.name + '.stderr.log')
        mergedLog = Join-Path $LogDir ($Experiment.id + '_' + $Experiment.name + '.log')
    }
}

function Test-ExperimentComplete {
    param([pscustomobject]$Experiment)
    $paths = Get-ExperimentPaths -Experiment $Experiment
    return (Test-Path $paths.summary) -and (Test-Path $paths.performance) -and (Test-Path $paths.frameMetrics)
}

function Get-LockModeCounts {
    param([string]$FrameMetricsPath)

    $items = Get-Content $FrameMetricsPath -Raw | ConvertFrom-Json
    $counts = @{ FACE_LOCK = 0; HEAD_PROXY = 0; LOST = 0; SEARCHING = 0 }
    foreach ($item in $items) {
        if ($null -ne $item.lock_mode -and $counts.ContainsKey([string]$item.lock_mode)) {
            $counts[[string]$item.lock_mode] += 1
        }
    }
    return $counts
}

function Load-RunMetrics {
    param([pscustomobject]$Experiment)

    $paths = Get-ExperimentPaths -Experiment $Experiment
    $summary = Get-Content $paths.summary -Raw | ConvertFrom-Json
    $performance = Get-Content $paths.performance -Raw | ConvertFrom-Json
    $lockCounts = Get-LockModeCounts -FrameMetricsPath $paths.frameMetrics

    $frameTotalAvg = $null
    $collectAvg = $null
    $embeddingAvg = $null
    $mtcnnAvg = $null
    if ($null -ne $performance.stages.frame_total_ms) { $frameTotalAvg = [double]$performance.stages.frame_total_ms.avg_ms }
    if ($null -ne $performance.stages.collect_candidates_ms) { $collectAvg = [double]$performance.stages.collect_candidates_ms.avg_ms }
    if ($null -ne $performance.stages.embedding_ms) { $embeddingAvg = [double]$performance.stages.embedding_ms.avg_ms }
    if ($null -ne $performance.stages.face_detect_mtcnn_ms) { $mtcnnAvg = [double]$performance.stages.face_detect_mtcnn_ms.avg_ms }

    return [ordered]@{
        id = $Experiment.id
        name = $Experiment.name
        focus = $Experiment.focus
        params = $Experiment.paramsText
        runtime_sec = [double]$summary.runtime_sec
        fps = [double]$summary.effective_fps
        face_lock = [int]$lockCounts['FACE_LOCK']
        head_proxy = [int]$lockCounts['HEAD_PROXY']
        lost = [int]$lockCounts['LOST']
        searching = [int]$lockCounts['SEARCHING']
        tracker_switches = [int]$summary.tracker_switches
        reacquired = [int]$summary.reacquired_count
        face_detected = [int]$summary.face_detected_frames
        face_misses = [int]$summary.total_face_misses
        max_face_miss_streak = [int]$summary.max_face_miss_streak
        embedding_calls = [int]$performance.counts.embedding_calls.total
        mtcnn_calls = [int]$performance.counts.face_detect_mtcnn_calls.total
        frame_total_avg_ms = $frameTotalAvg
        collect_avg_ms = $collectAvg
        embedding_avg_ms = $embeddingAvg
        mtcnn_avg_ms = $mtcnnAvg
    }
}

function Format-Number {
    param($Value, [int]$Digits = 3)
    if ($null -eq $Value) { return '' }
    return [string]([math]::Round([double]$Value, $Digits))
}

function Compare-Speed {
    param($baseline, $row)
    return "fps $(Format-Number ($row.fps - $baseline.fps)); runtime $(Format-Number ($row.runtime_sec - $baseline.runtime_sec)) sec"
}

function Compare-Quality {
    param($baseline, $row)
    return "FACE_LOCK $($row.face_lock - $baseline.face_lock); HEAD_PROXY $($row.head_proxy - $baseline.head_proxy); LOST $($row.lost - $baseline.lost); switch $($row.tracker_switches - $baseline.tracker_switches); face_miss $($row.face_misses - $baseline.face_misses)"
}

function Get-SpeedImpactLabel {
    param($baseline, $row)
    $fpsDelta = $row.fps - $baseline.fps
    if ($fpsDelta -ge 0.25) { return 'faster' }
    if ($fpsDelta -ge 0.05) { return 'slightly faster' }
    if ($fpsDelta -le -0.25) { return 'slower' }
    if ($fpsDelta -le -0.05) { return 'slightly slower' }
    return 'near baseline'
}

function Get-QualityImpactLabel {
    param($baseline, $row)
    $faceLockDelta = $row.face_lock - $baseline.face_lock
    $headProxyDelta = $row.head_proxy - $baseline.head_proxy
    $lostDelta = $row.lost - $baseline.lost
    $switchDelta = $row.tracker_switches - $baseline.tracker_switches
    $missDelta = $row.face_misses - $baseline.face_misses

    if (($faceLockDelta -ge 8) -and ($headProxyDelta -le 0) -and ($lostDelta -le 0) -and ($switchDelta -le 1)) { return 'better' }
    if (($faceLockDelta -ge 0) -and ($headProxyDelta -le 8) -and ($lostDelta -le 4) -and ($switchDelta -le 2) -and ($missDelta -le 8)) { return 'slightly better' }
    if (($faceLockDelta -le -12) -or ($lostDelta -ge 8) -or ($switchDelta -ge 4) -or ($missDelta -ge 20)) { return 'worse' }
    if (($faceLockDelta -lt 0) -or ($headProxyDelta -gt 8) -or ($lostDelta -gt 0) -or ($switchDelta -gt 0) -or ($missDelta -gt 8)) { return 'slightly worse' }
    return 'near baseline'
}

function Get-AnalysisText {
    param($baseline, $row)

    if ($row.id -eq 'C0') { return 'same-source baseline for the new corner-case video' }
    $speed = Get-SpeedImpactLabel -baseline $baseline -row $row
    $quality = Get-QualityImpactLabel -baseline $baseline -row $row
    $qualityDelta = Compare-Quality -baseline $baseline -row $row
    $speedDelta = Compare-Speed -baseline $baseline -row $row
    return "$($row.focus): speed is $speed ($speedDelta), quality is $quality ($qualityDelta)"
}

function Get-CompletedRows {
    $rows = @()
    foreach ($exp in $experiments) {
        if (Test-ExperimentComplete -Experiment $exp) {
            $rows += Load-RunMetrics -Experiment $exp
        }
    }
    return $rows
}

function Write-ResultsTable {
    $rows = Get-CompletedRows
    $baseline = $rows | Where-Object { $_.id -eq 'C0' } | Select-Object -First 1

    $lines = @(
        '# Corner Case Tuning Results',
        '',
        "- Source video: $SourceVideo",
        "- Run ID: $RunId",
        "- Project: $ProjectName",
        "- Live log: runs/corner_case_tuning_logs/$RunId/corner_case_tuning_live.log",
        '',
        '## Experiment Table',
        '',
        '| ID | Name | Focus | Params | Runtime Sec | FPS | FACE_LOCK | HEAD_PROXY | LOST | SEARCHING | Tracker Switches | Reacquired | Face Detected | Face Misses | Max Face Miss Streak | Embedding Calls | MTCNN Calls | Frame Avg ms | Collect Avg ms | Embedding Avg ms | MTCNN Avg ms | Speed Impact | Quality Impact | Analysis |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |'
    )

    foreach ($row in $rows) {
        if ($null -ne $baseline) {
            $speedLabel = Get-SpeedImpactLabel -baseline $baseline -row $row
            $qualityLabel = Get-QualityImpactLabel -baseline $baseline -row $row
            $analysis = Get-AnalysisText -baseline $baseline -row $row
        }
        else {
            $speedLabel = 'pending baseline'
            $qualityLabel = 'pending baseline'
            $analysis = 'Run C0 first to enable same-source comparison.'
        }

        $lines += "| $($row.id) | $($row.name) | $($row.focus) | $($row.params) | $(Format-Number $row.runtime_sec) | $(Format-Number $row.fps) | $($row.face_lock) | $($row.head_proxy) | $($row.lost) | $($row.searching) | $($row.tracker_switches) | $($row.reacquired) | $($row.face_detected) | $($row.face_misses) | $($row.max_face_miss_streak) | $($row.embedding_calls) | $($row.mtcnn_calls) | $(Format-Number $row.frame_total_avg_ms 2) | $(Format-Number $row.collect_avg_ms 2) | $(Format-Number $row.embedding_avg_ms 2) | $(Format-Number $row.mtcnn_avg_ms 2) | $speedLabel | $qualityLabel | $analysis |"
    }

    $lines += ''
    $lines += '## Required Review After Each Round'
    $lines += ''
    $lines += '- summary: effective_fps, runtime_sec, tracker_switches, reacquired_count, face_detected_frames, total_face_misses, max_face_miss_streak.'
    $lines += '- frame_metrics: FACE_LOCK / HEAD_PROXY / LOST / SEARCHING distribution and manual check for fake FACE_LOCK.'
    $lines += '- performance: frame_total_ms, collect_candidates_ms, embedding_ms, face_detect_mtcnn_ms, embedding_calls, MTCNN calls.'
    $lines += '- video: inspect crossing, occlusion, side-face, dark/blur, and control-center drift segments before declaring pass.'

    Set-Content -Path $ResultsFile -Value $lines -Encoding UTF8
}

function Update-ProgressFile {
    param([string]$State, [string]$CurrentExperiment, [string]$ExtraNote = '')

    $lines = @(
        '# Corner Case Tuning Progress',
        '',
        "- State: $State",
        "- Last update: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
        "- Current experiment: $CurrentExperiment",
        "- Source video: $SourceVideo",
        "- Run ID: $RunId",
        "- Results table: docs/tuning/corner_case_tuning_results_$RunId.md",
        "- Live log: runs/corner_case_tuning_logs/$RunId/corner_case_tuning_live.log",
        ''
    )
    if ($ExtraNote) {
        $lines += "- Note: $ExtraNote"
        $lines += ''
    }
    $lines += '## Planned Experiments'
    $lines += ''
    $lines += '| ID | Name | Focus | Params | Status | Direction | Risk |'
    $lines += '| --- | --- | --- | --- | --- | --- | --- |'
    foreach ($exp in $experiments) {
        $status = 'pending'
        if (Test-ExperimentComplete -Experiment $exp) { $status = 'completed' }
        elseif ($exp.name -eq $CurrentExperiment) { $status = 'running' }
        $lines += "| $($exp.id) | $($exp.name) | $($exp.focus) | $($exp.paramsText) | $status | $($exp.direction) | $($exp.risk) |"
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

Write-LiveLog "Corner-case tuning initialized source=$SourceVideo run_id=$RunId"
Update-ProgressFile -State 'setup' -CurrentExperiment 'preparing' -ExtraNote 'Preparing C0-C8 corner-case experiments.'
Write-ResultsTable

foreach ($exp in $experiments) {
    $paths = Get-ExperimentPaths -Experiment $exp
    if ((Test-ExperimentComplete -Experiment $exp) -and (-not $Force)) {
        Write-LiveLog "Skipping $($exp.id) $($exp.name); outputs already exist."
        Write-ResultsTable
        continue
    }

    if ($Force -and (Test-Path $paths.runDir)) {
        Remove-Item $paths.runDir -Recurse -Force
    }
    if (Test-Path $paths.stdout) { Remove-Item $paths.stdout -Force }
    if (Test-Path $paths.stderr) { Remove-Item $paths.stderr -Force }
    if (Test-Path $paths.mergedLog) { Remove-Item $paths.mergedLog -Force }

    Update-ProgressFile -State 'running' -CurrentExperiment $exp.name -ExtraNote $exp.direction
    Write-LiveLog "Starting $($exp.id) $($exp.name) params=$($exp.paramsText)"

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

    Push-Location $Root
    try {
        $proc = Start-Process -FilePath $Python -ArgumentList $cmdArgs -NoNewWindow -Wait -PassThru -RedirectStandardOutput $paths.stdout -RedirectStandardError $paths.stderr
        if (Test-Path $paths.stdout) { Get-Content $paths.stdout | Set-Content $paths.mergedLog }
        if (Test-Path $paths.stderr) { Get-Content $paths.stderr | Add-Content $paths.mergedLog }
        if ($proc.ExitCode -ne 0) {
            throw "Experiment $($exp.id) $($exp.name) failed with exit code $($proc.ExitCode)"
        }
    }
    finally {
        Pop-Location
    }

    if (-not (Test-ExperimentComplete -Experiment $exp)) {
        throw "Experiment $($exp.id) $($exp.name) finished without complete JSON outputs"
    }

    $row = Load-RunMetrics -Experiment $exp
    Write-LiveLog "Completed $($exp.id) $($exp.name) fps=$(Format-Number $row.fps) runtime=$(Format-Number $row.runtime_sec) face_lock=$($row.face_lock) head_proxy=$($row.head_proxy) switches=$($row.tracker_switches)"
    Write-ResultsTable
    Update-ProgressFile -State 'running' -CurrentExperiment $exp.name -ExtraNote "Completed $($exp.id). Results table updated."
}

Write-ResultsTable
Update-ProgressFile -State 'completed' -CurrentExperiment 'all experiments finished' -ExtraNote 'C0-C8 corner-case experiments completed successfully.'
Write-LiveLog 'All corner-case experiments completed successfully.'
