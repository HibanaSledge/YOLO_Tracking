param(
    [string]$SourceVideo = 'Q:\20260528-160426.mp4',
    [string]$RunId = 'priority_sweep_20260529',
    [int]$PollSeconds = 30,
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
$ProjectName = "runs/lock_target_priority_sweep/$RunId"
$DocsTuningDir = Join-Path $Root 'docs/tuning'
$PlanFile = Join-Path $DocsTuningDir "priority_sweep_experiment_plan_$RunId.md"
$ResultsFile = Join-Path $DocsTuningDir "priority_sweep_results_$RunId.md"
$ProgressFile = Join-Path $DocsTuningDir "priority_sweep_progress_$RunId.md"
$LogDir = Join-Path $Root "runs/priority_sweep_logs/$RunId"
$LiveLog = Join-Path $LogDir 'priority_sweep_live.log'

New-Item -ItemType Directory -Path $DocsTuningDir -Force | Out-Null
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

if (-not (Test-Path $SourceVideo)) {
    throw "Source video not found: $SourceVideo"
}
if (-not (Test-Path (Join-Path $Root 'yolo26n.pt'))) {
    throw 'Required weight missing: yolo26n.pt'
}
if (-not (Test-Path (Join-Path $Root 'yolo26l.pt'))) {
    throw 'Required weight missing: yolo26l.pt'
}

$optionalYolo26x = Test-Path (Join-Path $Root 'yolo26x.pt')

$experiments = @(
    [pscustomobject]@{ id = 'P0'; name = 'priority_baseline'; phase = 'baseline'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = @(); paramsText = 'baseline full'; direction = 'Same-source baseline for priority sweep'; risk = 'Must run first; all deltas are relative to this baseline' },
    [pscustomobject]@{ id = 'P1'; name = 'priority_reid_interval4'; phase = 'reid-interval'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = @('--reid-interval', '4'); paramsText = '--reid-interval 4'; direction = 'Test first lightweight ReID refresh step'; risk = 'May reduce identity stability around occlusion or crossings' },
    [pscustomobject]@{ id = 'P2'; name = 'priority_reid_interval6'; phase = 'reid-interval'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = @('--reid-interval', '6'); paramsText = '--reid-interval 6'; direction = 'Measure medium ReID refresh sparsity'; risk = 'Embedding calls should drop; quality must not be inferred from speed alone' },
    [pscustomobject]@{ id = 'P3'; name = 'priority_reid_interval8'; phase = 'reid-interval'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = @('--reid-interval', '8'); paramsText = '--reid-interval 8'; direction = 'Re-test previous speed-oriented boundary on this source'; risk = 'Higher risk of delayed identity correction' },
    [pscustomobject]@{ id = 'P4'; name = 'priority_reid_interval10'; phase = 'reid-interval'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = @('--reid-interval', '10'); paramsText = '--reid-interval 10'; direction = 'Stress-test upper ReID interval boundary'; risk = 'May over-sparsify appearance refresh and hide ID drift' },
    [pscustomobject]@{ id = 'P5'; name = 'priority_face_scale102'; phase = 'face-scale-factor'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = @('--face-scale-factor', '1.02'); paramsText = '--face-scale-factor 1.02'; direction = 'Local sweep around C3 face-scale-factor gain'; risk = 'More face candidates and false FACE_LOCK risk' },
    [pscustomobject]@{ id = 'P6'; name = 'priority_face_scale103'; phase = 'face-scale-factor'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = @('--face-scale-factor', '1.03'); paramsText = '--face-scale-factor 1.03'; direction = 'Repeat previous best face-scale setting in priority sequence'; risk = 'Needs manual key-frame review before calling it better' },
    [pscustomobject]@{ id = 'P7'; name = 'priority_face_scale104'; phase = 'face-scale-factor'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = @('--face-scale-factor', '1.04'); paramsText = '--face-scale-factor 1.04'; direction = 'Check whether gain remains near default scale'; risk = 'May lose C3 benefit while retaining extra cost' },
    [pscustomobject]@{ id = 'P8'; name = 'priority_face_conf025'; phase = 'face-min-confidence'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = @('--face-min-confidence', '0.25'); paramsText = '--face-min-confidence 0.25'; direction = 'Relax MTCNN confidence for face recall'; risk = 'False FACE_LOCK risk; do not equate more detections with better lock' },
    [pscustomobject]@{ id = 'P9'; name = 'priority_face_conf028'; phase = 'face-min-confidence'; model = 'yolo26n.pt'; reidModel = 'yolo26l.pt'; params = @('--face-min-confidence', '0.28'); paramsText = '--face-min-confidence 0.28'; direction = 'Intermediate face confidence threshold between C4 and baseline'; risk = 'Small deltas may be inconclusive without key-frame review' },
    [pscustomobject]@{ id = 'P10'; name = 'priority_detector_yolo26l'; phase = 'detector-model'; model = 'yolo26l.pt'; reidModel = 'yolo26l.pt'; params = @(); paramsText = '--model yolo26l.pt'; direction = 'Detector model A/B: yolo26n.pt versus yolo26l.pt'; risk = 'Likely slower; quality must improve enough to justify cost' },
    [pscustomobject]@{ id = 'P11'; name = 'priority_reid_yolo26n'; phase = 'reid-model'; model = 'yolo26n.pt'; reidModel = 'yolo26n.pt'; params = @(); paramsText = '--reid-model yolo26n.pt'; direction = 'ReID model A/B for lightweight embedding cost'; risk = 'May reduce appearance discrimination even if faster' }
)

if ($optionalYolo26x) {
    $experiments += [pscustomobject]@{ id = 'P12'; name = 'priority_detector_yolo26x'; phase = 'optional-detector-model'; model = 'yolo26x.pt'; reidModel = 'yolo26l.pt'; params = @(); paramsText = '--model yolo26x.pt'; direction = 'Optional quality-first detector model test because yolo26x.pt exists'; risk = 'Expected large runtime cost; only useful if quality clearly improves' }
}

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

function Find-ActiveExperimentProcess {
    param([pscustomobject]$Experiment)

    $needleSource = "--source $SourceVideo"
    $needleProject = "--project $ProjectName"
    $needleName = "--name $($Experiment.name)"
    return Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object {
            $_.CommandLine -like "*$needleSource*" -and
            $_.CommandLine -like "*$needleProject*" -and
            $_.CommandLine -like "*$needleName*"
        } |
        Select-Object -First 1
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
        phase = $Experiment.phase
        model = $Experiment.model
        reid_model = $Experiment.reidModel
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

    if ($row.id -eq 'P0') { return 'same-source baseline for the priority sweep video' }
    $speed = Get-SpeedImpactLabel -baseline $baseline -row $row
    $quality = Get-QualityImpactLabel -baseline $baseline -row $row
    $qualityDelta = Compare-Quality -baseline $baseline -row $row
    $speedDelta = Compare-Speed -baseline $baseline -row $row
    return "$($row.phase): speed is $speed ($speedDelta), quality is $quality ($qualityDelta)"
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

function Write-ExperimentPlan {
    $lines = @(
        '# Priority Sweep Experiment Plan',
        '',
        "- Source video: $SourceVideo",
        "- Run ID: $RunId",
        "- Project: $ProjectName",
        "- Live log: runs/priority_sweep_logs/$RunId/priority_sweep_live.log",
        "- yolo26x.pt available: $optionalYolo26x",
        '',
        '## Order',
        '',
        '1. Baseline on the same source.',
        '2. ReID interval sweep: 4 / 6 / 8 / 10.',
        '3. Face recall local sweep: face-scale-factor, then face-min-confidence.',
        '4. Detector model A/B: yolo26n.pt versus yolo26l.pt.',
        '5. ReID model A/B: yolo26l.pt versus yolo26n.pt.',
        '6. Optional yolo26x.pt only if the weight exists.',
        '',
        '## Planned Experiments',
        '',
        '| ID | Name | Phase | Model | ReID Model | Params | Direction | Risk |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |'
    )
    foreach ($exp in $experiments) {
        $lines += "| $($exp.id) | $($exp.name) | $($exp.phase) | $($exp.model) | $($exp.reidModel) | $($exp.paramsText) | $($exp.direction) | $($exp.risk) |"
    }
    if (-not $optionalYolo26x) {
        $lines += "| skipped | priority_detector_yolo26x | optional-detector-model | yolo26x.pt | yolo26l.pt | --model yolo26x.pt | Optional quality-first test | Skipped because yolo26x.pt is missing |"
    }
    $lines += ''
    $lines += '## Required Evidence'
    $lines += ''
    $lines += '- summary: runtime_sec, effective_fps, tracker_switches, reacquired_count, face_detected_frames, total_face_misses, max_face_miss_streak.'
    $lines += '- frame_metrics: FACE_LOCK / HEAD_PROXY / LOST / SEARCHING distribution and manual key-frame review for fake FACE_LOCK.'
    $lines += '- performance: frame_total_ms, collect_candidates_ms, embedding_ms, face_detect_mtcnn_ms, embedding_calls, face_detect_mtcnn_calls.'
    $lines += '- A speed win is not accepted unless quality stays same-source comparable.'

    Set-Content -Path $PlanFile -Value $lines -Encoding UTF8
}

function Write-ResultsTable {
    $rows = Get-CompletedRows
    $baseline = $rows | Where-Object { $_.id -eq 'P0' } | Select-Object -First 1

    $lines = @(
        '# Priority Sweep Tuning Results',
        '',
        "- Source video: $SourceVideo",
        "- Run ID: $RunId",
        "- Project: $ProjectName",
        "- Plan: docs/tuning/priority_sweep_experiment_plan_$RunId.md",
        "- Live log: runs/priority_sweep_logs/$RunId/priority_sweep_live.log",
        '',
        '## Experiment Table',
        '',
        '| ID | Name | Phase | Model | ReID Model | Params | Runtime Sec | FPS | FACE_LOCK | HEAD_PROXY | LOST | SEARCHING | Tracker Switches | Reacquired | Face Detected | Face Misses | Max Face Miss Streak | Embedding Calls | MTCNN Calls | Frame Avg ms | Collect Avg ms | Embedding Avg ms | MTCNN Avg ms | Speed Impact | Quality Impact | Analysis |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |'
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
            $analysis = 'Run P0 first to enable same-source comparison.'
        }

        $lines += "| $($row.id) | $($row.name) | $($row.phase) | $($row.model) | $($row.reid_model) | $($row.params) | $(Format-Number $row.runtime_sec) | $(Format-Number $row.fps) | $($row.face_lock) | $($row.head_proxy) | $($row.lost) | $($row.searching) | $($row.tracker_switches) | $($row.reacquired) | $($row.face_detected) | $($row.face_misses) | $($row.max_face_miss_streak) | $($row.embedding_calls) | $($row.mtcnn_calls) | $(Format-Number $row.frame_total_avg_ms 2) | $(Format-Number $row.collect_avg_ms 2) | $(Format-Number $row.embedding_avg_ms 2) | $(Format-Number $row.mtcnn_avg_ms 2) | $speedLabel | $qualityLabel | $analysis |"
    }

    $lines += ''
    $lines += '## Required Review After Each Round'
    $lines += ''
    $lines += '- summary + frame_metrics + performance must all exist before a run is considered complete.'
    $lines += '- FACE_LOCK increase must be manually reviewed for fake FACE_LOCK before it is treated as quality improvement.'
    $lines += '- HEAD_PROXY is not equivalent to true face lock.'
    $lines += '- Tracker id continuity is not enough to prove business identity continuity.'

    Set-Content -Path $ResultsFile -Value $lines -Encoding UTF8
}

function Update-ProgressFile {
    param([string]$State, [string]$CurrentExperiment, [string]$ExtraNote = '')

    $lines = @(
        '# Priority Sweep Tuning Progress',
        '',
        "- State: $State",
        "- Last update: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
        "- Current experiment: $CurrentExperiment",
        "- Source video: $SourceVideo",
        "- Python: $Python",
        "- Run ID: $RunId",
        "- Plan: docs/tuning/priority_sweep_experiment_plan_$RunId.md",
        "- Results table: docs/tuning/priority_sweep_results_$RunId.md",
        "- Live log: runs/priority_sweep_logs/$RunId/priority_sweep_live.log",
        ''
    )
    if ($ExtraNote) {
        $lines += "- Note: $ExtraNote"
        $lines += ''
    }
    $lines += '## Planned Experiments'
    $lines += ''
    $lines += '| ID | Name | Phase | Model | ReID Model | Params | Status | Direction | Risk |'
    $lines += '| --- | --- | --- | --- | --- | --- | --- | --- | --- |'
    foreach ($exp in $experiments) {
        $status = 'pending'
        if (Test-ExperimentComplete -Experiment $exp) { $status = 'completed' }
        elseif ($exp.name -eq $CurrentExperiment) { $status = 'running' }
        $lines += "| $($exp.id) | $($exp.name) | $($exp.phase) | $($exp.model) | $($exp.reidModel) | $($exp.paramsText) | $status | $($exp.direction) | $($exp.risk) |"
    }
    if (-not $optionalYolo26x) {
        $lines += '| skipped | priority_detector_yolo26x | optional-detector-model | yolo26x.pt | yolo26l.pt | --model yolo26x.pt | skipped | Optional quality-first test | yolo26x.pt is missing |'
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

function Invoke-Experiment {
    param([pscustomobject]$Experiment)

    $paths = Get-ExperimentPaths -Experiment $Experiment
    if ((Test-ExperimentComplete -Experiment $Experiment) -and (-not $Force)) {
        Write-LiveLog "Skipping $($Experiment.id) $($Experiment.name); outputs already exist."
        Write-ResultsTable
        Update-ProgressFile -State 'running' -CurrentExperiment $Experiment.name -ExtraNote "Skipped existing $($Experiment.id)."
        return
    }

    $activeProc = Find-ActiveExperimentProcess -Experiment $Experiment

    if ($Force -and (Test-Path $paths.runDir)) {
        Remove-Item $paths.runDir -Recurse -Force
    }
    if ($null -eq $activeProc) {
        if (Test-Path $paths.stdout) { Remove-Item $paths.stdout -Force }
        if (Test-Path $paths.stderr) { Remove-Item $paths.stderr -Force }
        if (Test-Path $paths.mergedLog) { Remove-Item $paths.mergedLog -Force }
    }

    Update-ProgressFile -State 'running' -CurrentExperiment $Experiment.name -ExtraNote $Experiment.direction
    Write-LiveLog "Starting $($Experiment.id) $($Experiment.name) model=$($Experiment.model) reid_model=$($Experiment.reidModel) params=$($Experiment.paramsText)"

    $baseArgs = @(
        'lock_target.py',
        '--source', $SourceVideo,
        '--model', $Experiment.model,
        '--tracker', 'cfg/trackers/botsort.yaml',
        '--reid-model', $Experiment.reidModel,
        '--classes', '0',
        '--conf', '0.25',
        '--iou', '0.5',
        '--imgsz', '960',
        '--initial-track-id', '1',
        '--fallback-to-first-face',
        '--project', $ProjectName,
        '--name', $Experiment.name,
        '--save-all-boxes'
    )
    $cmdArgs = $baseArgs + $Experiment.params

    Push-Location $Root
    try {
        if ($null -ne $activeProc) {
            $processId = [int]$activeProc.ProcessId
            Write-LiveLog "Attaching existing $($Experiment.id) $($Experiment.name) pid=$processId"
        }
        else {
            $proc = Start-Process -FilePath $Python -ArgumentList $cmdArgs -NoNewWindow -PassThru -RedirectStandardOutput $paths.stdout -RedirectStandardError $paths.stderr
            $processId = [int]$proc.Id
        }
        $lastSize = -1
        while ($null -ne (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
            $sizeText = 'mp4 missing'
            if (Test-Path $paths.lockedVideo) {
                $fileInfo = [System.IO.FileInfo]::new($paths.lockedVideo)
                $fileInfo.Refresh()
                $sizeText = "mp4_bytes=$($fileInfo.Length)"
                if ($fileInfo.Length -ne $lastSize) {
                    Write-LiveLog "Heartbeat $($Experiment.id) pid=$processId $sizeText"
                    $lastSize = $fileInfo.Length
                }
            }
            Update-ProgressFile -State 'running' -CurrentExperiment $Experiment.name -ExtraNote "PID $processId active, $sizeText"
            Start-Sleep -Seconds $PollSeconds
        }
        if (Test-Path $paths.stdout) { Get-Content $paths.stdout | Set-Content $paths.mergedLog }
        if (Test-Path $paths.stderr) { Get-Content $paths.stderr | Add-Content $paths.mergedLog }
    }
    finally {
        Pop-Location
    }

    if (-not (Test-ExperimentComplete -Experiment $Experiment)) {
        throw "Experiment $($Experiment.id) $($Experiment.name) finished without complete JSON outputs"
    }

    $row = Load-RunMetrics -Experiment $Experiment
    Write-LiveLog "Completed $($Experiment.id) $($Experiment.name) fps=$(Format-Number $row.fps) runtime=$(Format-Number $row.runtime_sec) face_lock=$($row.face_lock) head_proxy=$($row.head_proxy) lost=$($row.lost) switches=$($row.tracker_switches) embedding_calls=$($row.embedding_calls) mtcnn_calls=$($row.mtcnn_calls)"
    Write-ResultsTable
    Update-ProgressFile -State 'running' -CurrentExperiment $Experiment.name -ExtraNote "Completed $($Experiment.id). Results table updated."
}

Write-LiveLog "Priority sweep initialized source=$SourceVideo run_id=$RunId optional_yolo26x=$optionalYolo26x"
Write-ExperimentPlan
Write-ResultsTable
Update-ProgressFile -State 'setup' -CurrentExperiment 'preparing' -ExtraNote 'Preparing P0-P11 priority sweep experiments.'

foreach ($exp in $experiments) {
    Invoke-Experiment -Experiment $exp
}

Write-ResultsTable
Update-ProgressFile -State 'completed' -CurrentExperiment 'all experiments finished' -ExtraNote 'Priority sweep experiments completed successfully.'
Write-LiveLog 'All priority sweep experiments completed successfully.'