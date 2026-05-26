import base64
from pathlib import Path

run_dir = Path(r'e:/Downloads/ultralytics/runs/lock_target/hybrid_fix_7')
img_dir = run_dir / 'inspection_frames_worst'
out = run_dir / 'inspection_worst_report.html'
items = []
for path in sorted(img_dir.glob('*.jpg')):
    b64 = base64.b64encode(path.read_bytes()).decode('ascii')
    items.append(f"<section class='card'><h2>{path.name}</h2><img src='data:image/jpeg;base64,{b64}' alt='{path.name}' /></section>")
out.write_text(f"<!doctype html><html><head><meta charset='utf-8'><title>worst face lock</title><style>body{{font-family:Segoe UI,sans-serif;background:#111;color:#eee;padding:24px}} .card{{margin:0 0 28px;padding:16px;background:#1b1b1b;border:1px solid #333;border-radius:12px}} img{{max-width:420px;border:1px solid #444;display:block}}</style></head><body><h1>worst FACE_LOCK frames</h1>{''.join(items)}</body></html>", encoding='utf-8')
print(out)
