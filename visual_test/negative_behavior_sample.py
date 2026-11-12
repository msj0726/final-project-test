"""Inspect the user's local example video with the selected production Vision models."""

import json
import math
import sys
from collections import Counter
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from analysis.modules.vision import VisionModelPaths  # noqa: E402
from analysis.modules.vision.models import VisionDetectors  # noqa: E402
from analysis.modules.vision.observation import _face_direction, _polygon_overlap  # noqa: E402

VIDEO = next(
    path for path in Path("/Users/minseojang/Downloads").glob("*.mov")
    if "안되는" in path.name
)
OUT = ROOT / "visual_test/results/negative_behavior_sample"
MODEL_ROOT = Path("/Users/minseojang/Documents/ChatGPT/자소서/비언어행동_모델비교")
MODEL_PATHS = VisionModelPaths(
    MODEL_ROOT / "models/yolo11n-pose.pt",
    MODEL_ROOT / "models/yolov5n-face.pt",
    ROOT / "visual_test/models/yolo11n-seg.pt",
    MODEL_ROOT / "vendor/yolov5-face",
)
REVIEW_SECONDS = {0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 22, 24, 26, 28, 30, 32, 34, 36, 38}


def annotate(frame, result, second):
    display = frame.copy()
    body, face = result["body"], result["face"]
    if body:
        x1, y1, x2, y2 = map(int, body["box"])
        cv2.rectangle(display, (x1, y1), (x2, y2), (90, 235, 140), 3)
        for name, index in (("LS", 5), ("RS", 6), ("LW", 9), ("RW", 10)):
            point = body["points"][index]
            confidence = body["confidence"][index]
            cv2.circle(display, tuple(map(int, point)), 10, (0, 255, 0) if confidence >= .5 else (0, 0, 255), -1)
            cv2.putText(display, f"{name} {confidence:.2f}", (int(point[0]) + 12, int(point[1])), 0, .75, (0, 0, 0), 3)
    if face:
        x1, y1, x2, y2 = map(int, face["box"])
        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 225, 255), 3)
        for point in face["points"]:
            cv2.circle(display, tuple(map(int, point)), 5, (0, 225, 255), -1)
    for obj in result["objects"]:
        x1, y1, x2, y2 = map(int, obj["box"])
        cv2.rectangle(display, (x1, y1), (x2, y2), (255, 120, 30), 3)
        cv2.putText(display, f"{obj['label']} {obj['confidence']:.2f}", (x1, max(25, y1 - 10)), 0, .75, (20, 20, 20), 3)
    cv2.rectangle(display, (0, 0), (290, 52), (20, 30, 40), -1)
    cv2.putText(display, f"{second:04.1f}s", (18, 36), 0, 1, (255, 255, 255), 2)
    return cv2.resize(display, (960, 640))


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "frames").mkdir(exist_ok=True)
    model = VisionDetectors(MODEL_PATHS)
    capture = cv2.VideoCapture(str(VIDEO))
    assert capture.isOpened()
    rows = []
    target = 0.0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        actual = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
        if actual + .001 < target:
            continue
        result = model.detect(frame)
        body, face = result["body"], result["face"]
        direction, direction_reason = _face_direction(face)
        wrist_confidence = [body["confidence"][index] for index in (9, 10)] if body else [None, None]
        wrist_points = [body["points"][index] for index in (9, 10)] if body else [None, None]
        width = math.dist(body["points"][5], body["points"][6]) if body else None
        objects = []
        for obj in result["objects"]:
            overlap = _polygon_overlap(obj["polygon"], face["box"] if face else None)
            objects.append({
                "label": obj["label"], "confidence": obj["confidence"], "box": obj["box"],
                "faceOverlapRatio": overlap,
            })
        rows.append({
            "second": round(target, 3), "actualSecond": round(actual, 3),
            "hasSelectedBody": body is not None, "hasAssociatedFace": face is not None,
            "isCameraFacing": direction, "gazeReason": direction_reason,
            "wristConfidence": wrist_confidence, "wristPoints": wrist_points,
            "shoulderWidth": width, "objects": objects,
        })
        if round(target) in REVIEW_SECONDS and abs(target - round(target)) < .001:
            cv2.imwrite(str(OUT / "frames" / f"frame_{round(target):02d}.jpg"), annotate(frame, result, target))
        target = round(target + .2, 3)
    capture.release()
    counts = Counter(obj["label"] for row in rows for obj in row["objects"])
    (OUT / "frame_observations.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({
        "frames": len(rows), "bodyFrames": sum(row["hasSelectedBody"] for row in rows),
        "faceFrames": sum(row["hasAssociatedFace"] for row in rows),
        "leftWristFrames": sum(row["wristConfidence"][0] is not None and row["wristConfidence"][0] >= .5 for row in rows),
        "rightWristFrames": sum(row["wristConfidence"][1] is not None and row["wristConfidence"][1] >= .5 for row in rows),
        "objectLabels": counts,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
