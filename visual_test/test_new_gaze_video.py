"""Inspect the user-labeled away-looking interval with the current Vision models."""

import json
import sys
import time
import unicodedata
from pathlib import Path

import cv2

sys.path.insert(0, str(Path.cwd() / "backend"))
from analysis.modules.vision.models import VisionDetectors, VisionModelPaths
from analysis.modules.vision.observation import build_observation

ROOT = Path("visual_test/results/new_gaze_video")
ROOT.mkdir(parents=True, exist_ok=True)
VIDEO = next(
    path
    for path in Path("/Users/minseojang/Downloads").glob("*.mov")
    if unicodedata.normalize("NFC", path.name) == "동영상 2026. 11. 11. 오후 4.29.mov"
)
OLD = Path("/Users/minseojang/Documents/ChatGPT/자소서/비언어행동_모델비교")
MODELS = VisionModelPaths(
    OLD / "models/yolo11n-pose.pt",
    OLD / "models/yolov5n-face.pt",
    Path("visual_test/models/yolo11n-seg.pt"),
    OLD / "vendor/yolov5-face",
    Path("visual_test/models/hand_landmarker.task"),
)

if __name__ == "__main__":
    detectors = VisionDetectors(MODELS)
    capture = cv2.VideoCapture(str(VIDEO))
    rows = []
    target_seconds = 0.0
    start = time.monotonic()
    previous_histogram = None
    while True:
        decoded, frame = capture.read()
        if not decoded:
            break
        if capture.get(cv2.CAP_PROP_POS_MSEC) / 1000 + 0.001 < target_seconds:
            continue
        histogram = cv2.calcHist(
            [cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)], [0, 1], None, [16, 16], [0, 180, 0, 256]
        )
        cv2.normalize(histogram, histogram)
        scene_cut = previous_histogram is not None and cv2.compareHist(
            previous_histogram, histogram, cv2.HISTCMP_BHATTACHARYYA
        ) > 0.6
        previous_histogram = histogram
        rows.append(
            dict(
                startSec=target_seconds,
                endSec=round(target_seconds + 0.2, 3),
                sceneCut=scene_cut,
                **detectors.detect(frame),
            )
        )
        target_seconds = round(target_seconds + 0.2, 3)
    fps = capture.get(cv2.CAP_PROP_FPS)
    frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
    capture.release()
    duration = max(frame_count / fps, rows[-1]["endSec"])
    for row in rows:
        row["endSec"] = min(row["endSec"], duration)
    (ROOT / "raw.json").write_text(json.dumps(rows))
    result = build_observation(rows, duration)
    (ROOT / "vision.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({"frames": len(rows), "duration": duration, "seconds": round(time.monotonic() - start, 2)}))
