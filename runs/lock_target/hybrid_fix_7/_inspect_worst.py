import json
import cv2
from pathlib import Path

root = Path(r'e:/Downloads/ultralytics')
run_dir = root / 'runs' / 'lock_target' / 'hybrid_fix_7'
metrics_path = run_dir / '20260521-120258_frame_metrics.json'
video_path = run_dir / '20260521-120258_locked.mp4'
out_dir = run_dir / 'inspection_frames_worst'
out_dir.mkdir(exist_ok=True)

with metrics_path.open('r', encoding='utf-8') as f:
    data = json.load(f)

candidates = [
    item for item in data
    if item.get('lock_mode') == 'FACE_LOCK' and item.get('visible') and item.get('distance_to_center') is not None
]
worst = sorted(candidates, key=lambda x: x['distance_to_center'], reverse=True)[:8]
cap = cv2.VideoCapture(str(video_path))
for item in worst:
    idx = item['frame_index']
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx - 1)
    ok, frame = cap.read()
    if ok:
        cv2.imwrite(str(out_dir / f"frame_{idx:04d}_dist_{item['distance_to_center']:.2f}.jpg"), frame)
cap.release()

for item in worst:
    print(item['frame_index'], item['distance_to_center'], item['control_distance_to_center'], item['state'], item['tracker_id'])
