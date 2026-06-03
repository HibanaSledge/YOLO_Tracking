param(
    [string]$SourceVideo = 'Q:\20260528-160426.mp4',
    [string]$RunId = 'priority_sweep_20260529',
    [string]$ReportRelativePath = 'docs/tuning/offline_tuning_analysis_report.md'
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
$ResultsFileRelative = "docs/tuning/priority_sweep_results_$RunId.md"
$ProgressFileRelative = "docs/tuning/priority_sweep_progress_$RunId.md"
$PlanFileRelative = "docs/tuning/priority_sweep_experiment_plan_$RunId.md"
$ReportFile = Join-Path $Root $ReportRelativePath

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$experiments = @(
    [pscustomobject]@{ id = 'P0'; name = 'priority_baseline'; phase = 'baseline'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = 'baseline full' },
    [pscustomobject]@{ id = 'P1'; name = 'priority_reid_interval4'; phase = 'reid-interval'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = '--reid-interval 4' },
    [pscustomobject]@{ id = 'P2'; name = 'priority_reid_interval6'; phase = 'reid-interval'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = '--reid-interval 6' },
    [pscustomobject]@{ id = 'P3'; name = 'priority_reid_interval8'; phase = 'reid-interval'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = '--reid-interval 8' },
    [pscustomobject]@{ id = 'P4'; name = 'priority_reid_interval10'; phase = 'reid-interval'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = '--reid-interval 10' },
    [pscustomobject]@{ id = 'P5'; name = 'priority_face_scale102'; phase = 'face-scale-factor'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = '--face-scale-factor 1.02' },
    [pscustomobject]@{ id = 'P6'; name = 'priority_face_scale103'; phase = 'face-scale-factor'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = '--face-scale-factor 1.03' },
    [pscustomobject]@{ id = 'P7'; name = 'priority_face_scale104'; phase = 'face-scale-factor'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = '--face-scale-factor 1.04' },
    [pscustomobject]@{ id = 'P8'; name = 'priority_face_conf025'; phase = 'face-min-confidence'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = '--face-min-confidence 0.25' },
    [pscustomobject]@{ id = 'P9'; name = 'priority_face_conf028'; phase = 'face-min-confidence'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = '--face-min-confidence 0.28' },
    [pscustomobject]@{ id = 'P10'; name = 'priority_detector_yolo26l'; phase = 'detector-model'; model = 'yolo26l.pt'; reidModel = 'yolo26l.pt'; params = '--model yolo26l.pt' },
    [pscustomobject]@{ id = 'P11'; name = 'priority_reid_yolo26n'; phase = 'reid-model'; model = 'yolo26n.pt'; reidModel = 'yolo26n.pt'; params = '--reid-model yolo26n.pt' }
)

function Write-LiveLog {
    param([string]$Message)
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LiveLog -Value "[$stamp] $Message"
}

function Format-Number {
    param($Value, [int]$Digits = 3)
    if ($null -eq $Value) { return '' }
    return [string]([math]::Round([double]$Value, $Digits))
}

function Get-ExperimentPaths {
    param([pscustomobject]$Experiment)

    $runDir = Join-Path $Root (Join-Path $ProjectName $Experiment.name)
    return [pscustomobject]@{
        runDir = $runDir
        summary = Join-Path $runDir ($SourceStem + '_summary.json')
        performance = Join-Path $runDir ($SourceStem + '_performance.json')
        frameMetrics = Join-Path $runDir ($SourceStem + '_frame_metrics.json')
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

    return [pscustomobject]@{
        id = $Experiment.id
        name = $Experiment.name
        phase = $Experiment.phase
        model = $Experiment.model
        reid_model = $Experiment.reidModel
        params = $Experiment.params
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

function Get-DeltaText {
    param($Baseline, $Row)
    return "FPS $(Format-Number ($Row.fps - $Baseline.fps)); runtime $(Format-Number ($Row.runtime_sec - $Baseline.runtime_sec)) sec; FACE_LOCK $($Row.face_lock - $Baseline.face_lock); HEAD_PROXY $($Row.head_proxy - $Baseline.head_proxy); LOST $($Row.lost - $Baseline.lost); switches $($Row.tracker_switches - $Baseline.tracker_switches); face_misses $($Row.face_misses - $Baseline.face_misses)"
}

function Row-Line {
    param($Baseline, $Row)
    return "| $($Row.id) | $($Row.name) | $($Row.phase) | $($Row.params) | $(Format-Number $Row.runtime_sec) | $(Format-Number $Row.fps) | $($Row.face_lock) | $($Row.head_proxy) | $($Row.lost) | $($Row.tracker_switches) | $($Row.face_misses) | $($Row.embedding_calls) | $($Row.mtcnn_calls) | $(Format-Number $Row.frame_total_avg_ms 2) | $(Get-DeltaText -Baseline $Baseline -Row $Row) |"
}

$missing = @($experiments | Where-Object { -not (Test-ExperimentComplete -Experiment $_) })
if ($missing.Count -gt 0) {
    $missingText = ($missing | ForEach-Object { "$($_.id) $($_.name)" }) -join ', '
    Write-LiveLog "Priority sweep analysis skipped: incomplete experiments: $missingText"
    Write-Output "Incomplete experiments: $missingText"
    exit 2
}

$rows = @($experiments | ForEach-Object { Load-RunMetrics -Experiment $_ })
$baseline = $rows | Where-Object { $_.id -eq 'P0' } | Select-Object -First 1
$reidRows = @($rows | Where-Object { $_.phase -eq 'reid-interval' })
$faceScaleRows = @($rows | Where-Object { $_.phase -eq 'face-scale-factor' })
$faceConfRows = @($rows | Where-Object { $_.phase -eq 'face-min-confidence' })
$detectorRow = $rows | Where-Object { $_.id -eq 'P10' } | Select-Object -First 1
$reidModelRow = $rows | Where-Object { $_.id -eq 'P11' } | Select-Object -First 1

$bestReidSpeed = $reidRows | Sort-Object -Property fps -Descending | Select-Object -First 1
$bestFaceLock = $faceScaleRows | Sort-Object -Property face_lock -Descending | Select-Object -First 1
$bestFrameAvg = $rows | Sort-Object -Property frame_total_avg_ms | Select-Object -First 1

$markerStart = "<!-- priority_sweep_${RunId}_analysis_start -->"
$markerEnd = "<!-- priority_sweep_${RunId}_analysis_end -->"

$lines = @(
    $markerStart,
    '',
    "## 15. Priority Sweep P0-P11 Analysis ($RunId)",
    '',
    '### 15.1 Scope and evidence',
    '',
    "- Source video: $SourceVideo",
    "- Run ID: $RunId",
    "- Plan: $PlanFileRelative",
    "- Progress: $ProgressFileRelative",
    "- Results: $ResultsFileRelative",
    "- Outputs: $ProjectName",
    "- Analysis time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    '',
    'This section is generated from same-source summary.json, frame_metrics.json, and performance.json. Manual key-frame review is still required before declaring identity, FACE_LOCK, or control quality final.',
    '',
    '### 15.2 Summary table',
    '',
    '| ID | Name | Phase | Params | Runtime Sec | FPS | FACE_LOCK | HEAD_PROXY | LOST | Switches | Face Misses | Embedding Calls | MTCNN Calls | Frame Avg ms | Delta vs P0 |',
    '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |'
)
foreach ($row in $rows) {
    $lines += Row-Line -Baseline $baseline -Row $row
}

$lines += ''
$lines += '### 15.3 Auto findings'
$lines += ''
$lines += "- ReID interval line: fastest row is $($bestReidSpeed.id) $($bestReidSpeed.name), $(Get-DeltaText -Baseline $baseline -Row $bestReidSpeed). If key-frame review finds no identity drift, it is the first speed candidate."
$lines += "- Face scale line: highest FACE_LOCK row is $($bestFaceLock.id) $($bestFaceLock.name), $(Get-DeltaText -Baseline $baseline -Row $bestFaceLock). It improves face-lock count but must be weighed against runtime cost."
$lines += "- Global lowest frame_total average is $($bestFrameAvg.id) $($bestFrameAvg.name), frame_total_avg_ms=$(Format-Number $bestFrameAvg.frame_total_avg_ms 2), $(Get-DeltaText -Baseline $baseline -Row $bestFrameAvg)."
if ($null -ne $detectorRow) {
    $lines += "- Detector model A/B: $($detectorRow.id) $($detectorRow.name), $(Get-DeltaText -Baseline $baseline -Row $detectorRow). Adopt yolo26l.pt detector only if quality gain justifies speed cost."
}
if ($null -ne $reidModelRow) {
    $lines += "- ReID model A/B: $($reidModelRow.id) $($reidModelRow.name), $(Get-DeltaText -Baseline $baseline -Row $reidModelRow). Adopt yolo26n.pt ReID only if speed gain does not reduce identity quality."
}

$lines += ''
$lines += '### 15.4 Recommendations'
$lines += ''
$lines += '1. Review key frames for P0, fastest ReID interval candidate, best face-scale candidate, P10, and P11.'
$lines += '2. For speed-first tuning, prefer the ReID interval line before sparsifying MTCNN.'
$lines += '3. For quality-first tuning, prefer the best local face-scale setting, then test a combined compromise if runtime is acceptable.'
$lines += '4. Model switching should require both metric improvement and manual review; do not switch only because one metric improved.'
$lines += ''
$lines += '### 15.5 Evidence gaps'
$lines += ''
$lines += '- Manual key-frame review has not been completed.'
$lines += '- Offline evidence is not equal to realtime camera FPS or closed-loop gimbal stability.'
$lines += '- Real QGimbal closed-loop telemetry and control response are not included in this experiment.'
$lines += ''
$lines += $markerEnd

$section = ($lines -join [Environment]::NewLine) + [Environment]::NewLine

if (Test-Path $ReportFile) {
    $content = Get-Content $ReportFile -Raw
    $pattern = [regex]::Escape($markerStart) + '.*?' + [regex]::Escape($markerEnd) + "\s*"
    if ([regex]::IsMatch($content, $pattern, [System.Text.RegularExpressions.RegexOptions]::Singleline)) {
        $content = [regex]::Replace($content, $pattern, $section, [System.Text.RegularExpressions.RegexOptions]::Singleline)
    }
    else {
        $content = $content.TrimEnd() + [Environment]::NewLine + [Environment]::NewLine + $section
    }
    Set-Content -Path $ReportFile -Value $content -Encoding UTF8
}
else {
    Set-Content -Path $ReportFile -Value $section -Encoding UTF8
}

Write-LiveLog "Priority sweep analysis appended to $ReportRelativePath"
Write-Output "Analysis appended to $ReportRelativePath"