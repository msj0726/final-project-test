"""Run the current YOLO11n-pose on a CC0 60-second hand-motion stress clip."""
import json
import sys
from pathlib import Path

import cv2
import torch
from ultralytics import YOLO

sys.path.insert(0, str(Path.cwd() / "visual_test"))
from evaluate_four_criteria import hand_motion_episodes

VIDEO = Path("/Users/minseojang/Downloads/Bicycle_in_Ghanaian_sign_language_interpretation.webm")
ROOT = Path("visual_test/results/four_criteria")
ROOT.mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":
    torch.set_num_threads(1)
    model = YOLO("/Users/minseojang/Documents/ChatGPT/자소서/비언어행동_모델비교/models/yolo11n-pose.pt")
    capture = cv2.VideoCapture(str(VIDEO))
    rows = []
    target = 0.0
    while target < 60:
        decoded, frame = capture.read()
        if not decoded:
            break
        if capture.get(cv2.CAP_PROP_POS_MSEC) / 1000 + 0.001 < target:
            continue
        result = model.predict(frame, device="cpu", imgsz=640, conf=0.5, verbose=False)[0]
        body = None
        if len(result.boxes) and result.keypoints is not None:
            boxes = result.boxes.xyxy.cpu().numpy()
            areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
            order = areas.argsort()[::-1]
            if len(order) == 1 or areas[order[1]] / areas[order[0]] <= 0.5:
                index = int(order[0])
                body = {
                    "box": boxes[index].tolist(),
                    "points": result.keypoints.xy[index].cpu().numpy().tolist(),
                    "confidence": result.keypoints.conf[index].cpu().numpy().tolist(),
                }
        rows.append({"startSec": target, "endSec": round(target + 0.2, 3), "body": body, "face": None, "objects": [], "hands": [], "frameShape": frame.shape[:2]})
        target = round(target + 0.2, 3)
    capture.release()
    (ROOT / "public_hand_raw.json").write_text(json.dumps(rows))
    from analysis.modules.vision.observation import build_observation
    result = build_observation(rows, rows[-1]["endSec"])
    summary = {
        "source": "https://commons.wikimedia.org/wiki/File:Bicycle_in_Ghanaian_sign_language_interpretation.webm",
        "license": "CC0",
        "scope": "TECHNICAL_HAND_MOTION_STRESS_TEST_NOT_PRESENTATION_GESTURE_GROUND_TRUTH",
        "frames": len(rows),
        "handObservableSeconds": result["vision"]["handObservableSeconds"],
        "bothWristsVisibleSeconds": result["vision"]["bothWristsVisibleSeconds"],
        "handStillSeconds": result["vision"]["handStillSeconds"],
        "handStillEvents": result["vision"]["gestureEvents"],
        "motionEpisodeCount04": len(hand_motion_episodes(rows, 0.04)),
        "motionEpisodeCount08": len(hand_motion_episodes(rows, 0.08)),
        "motionEpisodes04": hand_motion_episodes(rows, 0.04),
    }
    (ROOT / "public_hand_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False))
