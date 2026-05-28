param(
    [string]$StartAfterId = 'G1',
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
$Python = 'C:/Users/Stuart.Cai/AppData/Local/Programs/Python/Python310/python.exe'
$SourceVideo = 'Q:\20260521-120258.mp4'
$SourceStem = [System.IO.Path]::GetFileNameWithoutExtension($SourceVideo)
$ProjectName = 'runs/lock_target_tuning'
$DocsTuningDir = Join-Path $Root 'docs/tuning'
$ProgressFile = Join-Path $DocsTuningDir 'offline_tuning_progress.md'
$ResultsFile = Join-Path $DocsTuningDir 'offline_tuning_results.md'
$LogDir = Join-Path $Root 'runs/offline_tuning_logs'
$LiveLog = Join-Path $LogDir 'offline_tuning_live.log'

New-Item -ItemType Directory -Path $DocsTuningDir -Force | Out-Null
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$experiments = @(
    [pscustomobject]@{ id = 'G1'; name = 'detect_img1152'; params = @('--imgsz', '1152'); paramsText = '--imgsz 1152'; note = 'Detect upsize' },
    [pscustomobject]@{ id = 'G2'; name = 'face_recall_boost'; params = @('--face-scale-factor', '1.03', '--face-min-confidence', '0.25'); paramsText = '--face-scale-factor 1.03 --face-min-confidence 0.25'; note = 'Face recall boost' },
    [pscustomobject]@{ id = 'G3'; name = 'reacquire_loose'; params = @('--min-appearance', '0.32', '--reacquire-thresh', '0.42'); paramsText = '--min-appearance 0.32 --reacquire-thresh 0.42'; note = 'Looser reacquire' },
    [pscustomobject]@{ id = 'G4'; name = 'reacquire_strict'; params = @('--min-appearance', '0.38', '--reacquire-thresh', '0.48'); paramsText = '--min-appearance 0.38 --reacquire-thresh 0.48'; note = 'Stricter reacquire' },
    [pscustomobject]@{ id = 'G5'; name = 'reid_interval_8'; params = @('--reid-interval', '8'); paramsText = '--reid-interval 8'; note = 'Lower ReID refresh' },
    [pscustomobject]@{ id = 'G6'; name = 'mtcnn_interval_3'; params = @('--mtcnn-interval', '3'); paramsText = '--mtcnn-interval 3'; note = 'Lower MTCNN refresh' },
    [pscustomobject]@{ id = 'G7'; name = 'light_balanced'; params = @('--reid-interval', '4', '--mtcnn-interval', '2'); paramsText = '--reid-interval 4 --mtcnn-interval 2'; note = 'Balanced light preset' }
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
    $counts = @{ FACE_LOCK = 0; HEAD_PROXY = 0; LOST = 0 }
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

    return [ordered]@{
        id = $Experiment.id
        name = $Experiment.name
        params = $Experiment.paramsText
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

function Get-ParameterFocus {
    param($row)

    switch ($row.id) {
        'baseline_full' { return 'baseline' }
        'baseline_light' { return 'lightweight preset' }
        'G1' { return 'imgsz' }
        'G2' { return 'face-scale-factor + face-min-confidence' }
        'G3' { return 'min-appearance + reacquire-thresh (loose)' }
        'G4' { return 'min-appearance + reacquire-thresh (strict)' }
        'G5' { return 'reid-interval' }
        'G6' { return 'mtcnn-interval' }
        'G7' { return 'reid-interval + mtcnn-interval' }
        default { return 'unknown' }
    }
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
    $switchDelta = $row.tracker_switches - $baseline.tracker_switches

    if (($faceLockDelta -ge 8) -and ($switchDelta -le 0)) { return 'better' }
    if (($faceLockDelta -ge 0) -and ($headProxyDelta -le 0) -and ($switchDelta -le 2)) { return 'slightly better' }
    if (($faceLockDelta -le -8) -or ($switchDelta -ge 4)) { return 'worse' }
    if (($faceLockDelta -lt 0) -or ($headProxyDelta -gt 0) -or ($switchDelta -gt 0)) { return 'slightly worse' }
    return 'near baseline'
}

function Get-AnalysisText {
    param($baseline, $row)

    $focus = Get-ParameterFocus -row $row
    $fpsDelta = [math]::Round(($row.fps - $baseline.fps), 3)
    $faceLockDelta = $row.face_lock - $baseline.face_lock
    $headProxyDelta = $row.head_proxy - $baseline.head_proxy
    $switchDelta = $row.tracker_switches - $baseline.tracker_switches

    if ($row.id -like 'baseline_*') {
        return 'reference row'
    }

    return "$focus changed fps by $fpsDelta, FACE_LOCK by $faceLockDelta, HEAD_PROXY by $headProxyDelta, tracker_switches by $switchDelta"
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
    param($baselineFull, $baselineLight)

    $rows = @()
    foreach ($exp in $experiments) {
        if (Test-ExperimentComplete -Experiment $exp) {
            $rows += Load-RunMetrics -Experiment $exp
        }
    }

    $lines = @(
        '# Offline Tuning Results',
        '',
        '## Experiment Table',
        '',
        '| ID | Name | Parameter Focus | Params | Runtime Sec | FPS | FACE_LOCK | HEAD_PROXY | LOST | Tracker Switches | Reacquired | Face Detected | Face Misses | Embedding Calls | MTCNN Calls | Speed vs Full | Quality vs Full | Speed vs Light | Quality vs Light | Speed Impact | Quality Impact | Analysis |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |'
    )

    $allRows = @($baselineFull, $baselineLight) + $rows
    foreach ($row in $allRows) {
        $focus = Get-ParameterFocus -row $row
        $qf = Compare-Quality -baseline $baselineFull -row $row
        $sf = Compare-Speed -baseline $baselineFull -row $row
        $ql = Compare-Quality -baseline $baselineLight -row $row
        $sl = Compare-Speed -baseline $baselineLight -row $row
        $speedLabel = Get-SpeedImpactLabel -baseline $baselineFull -row $row
        $qualityLabel = Get-QualityImpactLabel -baseline $baselineFull -row $row
        $analysis = Get-AnalysisText -baseline $baselineFull -row $row
        $lines += "| $($row.id) | $($row.name) | $focus | $($row.params) | $([math]::Round($row.runtime_sec, 3)) | $([math]::Round($row.fps, 3)) | $($row.face_lock) | $($row.head_proxy) | $($row.lost) | $($row.tracker_switches) | $($row.reacquired) | $($row.face_detected) | $($row.face_misses) | $($row.embedding_calls) | $($row.mtcnn_calls) | $sf | $qf | $sl | $ql | $speedLabel | $qualityLabel | $analysis |"
    }

    $lines += ''
    $lines += '## Notes'
    $lines += ''
    $lines += '- quality deltas are relative summaries against the current full and lightweight baselines.'
    $lines += '- speed deltas use effective FPS and runtime_sec from summary.json.'
    $lines += '- speed impact and quality impact labels are interpreted against baseline_full.'

    if ($rows.Count -gt 0) {
        $lines += ''
        $lines += '## Current Analysis'
        $lines += ''
        foreach ($row in $rows) {
            $focus = Get-ParameterFocus -row $row
            $speedLabel = Get-SpeedImpactLabel -baseline $baselineFull -row $row
            $qualityLabel = Get-QualityImpactLabel -baseline $baselineFull -row $row
            $analysis = Get-AnalysisText -baseline $baselineFull -row $row
            $lines += "- $($row.id) ${focus}: speed is $speedLabel, quality is $qualityLabel. $analysis."
        }
    }

    Set-Content -Path $ResultsFile -Value $lines -Encoding UTF8
}

function Update-ProgressFile {
    param(
        [string]$State,
        [string]$CurrentExperiment,
        [string]$ExtraNote,
        [string]$RunningId = '',
        [string]$RunningNote = ''
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

    foreach ($exp in $experiments) {
        $status = 'pending'
        $note = $exp.note
        if (Test-ExperimentComplete -Experiment $exp) {
            $status = 'completed'
            $note = 'JSON ready'
        }
        elseif ($exp.id -eq $RunningId) {
            $status = 'running'
            $note = $RunningNote
        }
        $lines += "| $($exp.id) | $($exp.name) | $($exp.paramsText) | $status | $note |"
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

$baselineFull = [ordered]@{
    id = 'baseline_full'
    name = 'offline_run'
    params = 'baseline full'
    runtime_sec = [double](Get-Content (Join-Path $Root 'runs/lock_target/offline_run/20260521-120258_summary.json') -Raw | ConvertFrom-Json).runtime_sec
    fps = [double](Get-Content (Join-Path $Root 'runs/lock_target/offline_run/20260521-120258_summary.json') -Raw | ConvertFrom-Json).effective_fps
    face_lock = 565
    head_proxy = 98
    lost = 48
    tracker_switches = 5
    reacquired = 3
    face_detected = 551
    face_misses = 110
    embedding_calls = 645
    mtcnn_calls = 791
}

$baselineLight = [ordered]@{
    id = 'baseline_light'
    name = 'offline_run_light'
    params = 'lightweight preset'
    runtime_sec = [double](Get-Content (Join-Path $Root 'runs/lock_target/offline_run_light/20260521-120258_summary.json') -Raw | ConvertFrom-Json).runtime_sec
    fps = [double](Get-Content (Join-Path $Root 'runs/lock_target/offline_run_light/20260521-120258_summary.json') -Raw | ConvertFrom-Json).effective_fps
    face_lock = 546
    head_proxy = 117
    lost = 48
    tracker_switches = 5
    reacquired = 3
    face_detected = 532
    face_misses = 129
    embedding_calls = 166
    mtcnn_calls = 355
}

$startIndex = -1
for ($i = 0; $i -lt $experiments.Count; $i++) {
    if ($experiments[$i].id -eq $StartAfterId) {
        $startIndex = $i
        break
    }
}
if ($startIndex -lt 0) {
    throw "Unknown StartAfterId: $StartAfterId"
}

$prereq = $experiments[$startIndex]
Write-LiveLog "Resume runner armed after $($prereq.id) $($prereq.name)"
Write-ResultsTable -baselineFull $baselineFull -baselineLight $baselineLight

while (-not (Test-ExperimentComplete -Experiment $prereq)) {
    $paths = Get-ExperimentPaths -Experiment $prereq
    $sizeText = 'waiting for G1 outputs'
    if (Test-Path $paths.lockedVideo) {
        $videoInfo = [System.IO.FileInfo]::new($paths.lockedVideo)
        $videoInfo.Refresh()
        $sizeText = "waiting for $($prereq.id) JSON, mp4_bytes=$($videoInfo.Length)"
    }
    Update-ProgressFile -State 'waiting-for-prerequisite' -CurrentExperiment $prereq.name -ExtraNote ("Resume runner armed. Will start G2-G7 after $($prereq.id) completes.") -RunningId $prereq.id -RunningNote $sizeText
    Start-Sleep -Seconds $PollSeconds
}

Write-ResultsTable -baselineFull $baselineFull -baselineLight $baselineLight
Write-LiveLog "Detected completion for $($prereq.id) $($prereq.name); continuing remaining experiments"

for ($i = $startIndex + 1; $i -lt $experiments.Count; $i++) {
    $exp = $experiments[$i]
    if (Test-ExperimentComplete -Experiment $exp) {
        Write-LiveLog "Skipping $($exp.id) $($exp.name); outputs already exist"
        continue
    }

    $paths = Get-ExperimentPaths -Experiment $exp
    Update-ProgressFile -State 'running-auto' -CurrentExperiment $exp.name -ExtraNote ("Auto-resume runner executing $($exp.id) after $($prereq.id).") -RunningId $exp.id -RunningNote 'Launching experiment'
    Write-LiveLog "Starting $($exp.id) $($exp.name)"

    if (Test-Path $paths.stdout) { Remove-Item $paths.stdout -Force }
    if (Test-Path $paths.stderr) { Remove-Item $paths.stderr -Force }
    if (Test-Path $paths.mergedLog) { Remove-Item $paths.mergedLog -Force }

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

    Write-ResultsTable -baselineFull $baselineFull -baselineLight $baselineLight
    $row = Load-RunMetrics -Experiment $exp
    Write-LiveLog "Completed $($exp.id) $($exp.name) fps=$([math]::Round($row.fps, 3)) runtime=$([math]::Round($row.runtime_sec, 3))"
    Update-ProgressFile -State 'running-auto' -CurrentExperiment $exp.name -ExtraNote ("Completed $($exp.id). Continuing remaining experiments.")
}

Write-ResultsTable -baselineFull $baselineFull -baselineLight $baselineLight
Write-LiveLog 'Remaining experiments completed successfully.'
Update-ProgressFile -State 'completed' -CurrentExperiment 'all experiments finished' -ExtraNote 'G2-G7 auto-resume completed successfully.'