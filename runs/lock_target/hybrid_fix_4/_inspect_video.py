import json
import cv2
import base64
from pathlib import Path

root = Path(r'e:/Downloads/ultralytics')
run_dir = root / 'runs' / 'lock_target' / 'hybrid_fix_4'
metrics_path = run_dir / '20260521-120258_frame_metrics.json'
video_path = run_dir / '20260521-120258_locked.mp4'
out_dir = run_dir / 'inspection_frames'
out_dir.mkdir(exist_ok=True)

with metrics_path.open('r', encoding='utf-8') as f:
    data = json.load(f)

# Pick representative frames: early stable, early hold/deadband, lost->reacquire, final stable.
interesting = []
interesting.append(1)
for item in data:
    if item['state'] == 'HOLD' and item['visible']:
        interesting.append(item['frame_index'])
        break
for item in data:
    if item.get('deadband_active'):
        interesting.append(item['frame_index'])
        break
lost_index = None
for item in data:
    if item['state'] == 'LOST':
        lost_index = item['frame_index']
        interesting.append(lost_index)
        break
if lost_index is not None:
    for item in data:
        if item['frame_index'] > lost_index and item['state'] == 'REACQUIRE':
            interesting.append(item['frame_index'])
            break
interesting.append(data[-1]['frame_index'])
interesting = list(dict.fromkeys(interesting))

cap = cv2.VideoCapture(str(video_path))
if not cap.isOpened():
    raise RuntimeError(f'Failed to open {video_path}')

saved = []
for frame_idx in interesting:
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx - 1)
    ok, frame = cap.read()
    if not ok:
        continue
    img_path = out_dir / f'frame_{frame_idx:04d}.jpg'
    cv2.imwrite(str(img_path), frame)
    saved.append(img_path)
cap.release()

cards = []
for img_path in saved:
    frame_idx = int(img_path.stem.split('_')[1])
    item = data[frame_idx - 1]
    b64 = base64.b64encode(img_path.read_bytes()).decode('ascii')
    cards.append(f"""
    <section class='card'>
      <h2>Frame {frame_idx} | state={item['state']} | visible={item['visible']} | tracker_id={item['tracker_id']}</h2>
      <p>raw_dist={item['distance_to_center']} | control_dist={item['control_distance_to_center']} | control_active={item['control_active']} | deadband={item['deadband_active']}</p>
      <img src='data:image/jpeg;base64,{b64}' alt='frame {frame_idx}' />
    </section>
    """)

html = f"""
<!doctype html>
<html>
<head>
<meta charset='utf-8' />
<title>hybrid_fix_4 inspection</title>
<style>
body {{ font-family: Segoe UI, sans-serif; background:#111; color:#eee; margin:0; padding:24px; }}
h1 {{ margin:0 0 16px; }}
.card {{ margin:0 0 28px; padding:16px; background:#1b1b1b; border:1px solid #333; border-radius:12px; }}
p {{ color:#cfcfcf; }}
img {{ max-width:420px; border:1px solid #444; display:block; }}
</style>
</head>
<body>
<h1>hybrid_fix_4 inspection</h1>
{''.join(cards)}
</body>
</html>
"""
(report_path := run_dir / 'inspection_report.html').write_text(html, encoding='utf-8')
print(report_path)
print('\n'.join(str(p) for p in saved))
