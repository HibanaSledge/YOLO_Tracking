from pathlib import Path
import cv2
video = Path(r'e:/Downloads/ultralytics/runs/lock_target_realtime/camera_20260525-153555/camera_0_locked.mp4')
cap = cv2.VideoCapture(str(video))
print({
    'opened': cap.isOpened(),
    'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    'fps': cap.get(cv2.CAP_PROP_FPS),
    'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
    'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    'duration_sec': round((cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1e-6)), 2) if cap.isOpened() else None,
})
cap.release()
