import json
from collections import Counter
from pathlib import Path

run_dir = Path(r'e:/Downloads/ultralytics/runs/lock_target_realtime/camera_20260525-153555')
summary = json.loads((run_dir / 'camera_0_summary.json').read_text(encoding='utf-8'))
metrics = json.loads((run_dir / 'camera_0_frame_metrics.json').read_text(encoding='utf-8'))

visible = sum(1 for m in metrics if m['visible'])
invisible = len(metrics) - visible
states = Counter(m['state'] for m in metrics)
modes = Counter(m['lock_mode'] for m in metrics)
tracker_ids = Counter(m['tracker_id'] for m in metrics if m['tracker_id'] is not None)
dropped_total = sum(int(m.get('dropped_frames_before', 0) or 0) for m in metrics)
dropped_max = max((int(m.get('dropped_frames_before', 0) or 0) for m in metrics), default=0)
source_ids = [m.get('source_frame_id') for m in metrics if m.get('source_frame_id') is not None]
control_dist = [m['control_distance_to_center'] for m in metrics if m['control_distance_to_center'] is not None]
raw_dist = [m['distance_to_center'] for m in metrics if m['distance_to_center'] is not None]

def avg(vals):
    return round(sum(vals) / len(vals), 2) if vals else None

print('frames', len(metrics))
print('visible', visible)
print('invisible', invisible)
print('states', dict(states))
print('modes', dict(modes))
print('tracker_ids', dict(tracker_ids))
print('dropped_total_metrics', dropped_total)
print('dropped_max_metrics', dropped_max)
print('source_first_last', source_ids[0] if source_ids else None, source_ids[-1] if source_ids else None)
print('source_monotonic', all(b > a for a, b in zip(source_ids, source_ids[1:])))
print('avg_control_distance', avg(control_dist))
print('max_control_distance', max(control_dist) if control_dist else None)
print('avg_raw_distance', avg(raw_dist))
print('max_raw_distance', max(raw_dist) if raw_dist else None)
print('summary_process_fps', summary.get('process_fps'))
print('summary_process_latency_ms', summary.get('process_latency_ms'))
print('summary_dropped_total', summary.get('total_dropped_frames'))
print('summary_dropped_max', summary.get('max_dropped_frames'))
print('summary_processed_frames', summary.get('processed_frames'))
print('summary_session_duration_sec', summary.get('session_duration_sec'))
