"""Extract held-out public clips with the current Vision detector configuration."""

import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path.cwd() / "backend"))
from analysis.modules.vision.models import VisionDetectors, VisionModelPaths
from analysis.modules.vision.observation import build_observation


ROOT = Path("visual_test/results/followup_rule_evaluation")
OLD = Path("/Users/minseojang/Documents/ChatGPT/자소서/비언어행동_모델비교")
PATHS = VisionModelPaths(
    OLD / "models/yolo11n-pose.pt",
    OLD / "models/yolov5n-face.pt",
    Path("visual_test/models/yolo11n-seg.pt"),
    OLD / "vendor/yolov5-face",
    Path("visual_test/models/hand_landmarker.task"),
)
CLIPS = {
    "malaysia_presentation": (Path("/private/tmp/propitch_malaysia_public.webm"), 60.0),
    "facepalm": (Path("/private/tmp/propitch_facepalm_public.webm"), 3.4),
    "ian_presentation": (Path("/private/tmp/propitch_ian_public.webm"), 59.0),
    "dance_hand_lesson": (Path("/private/tmp/propitch_dance_public.webm"), 60.0),
}


def extract(clip_id, detectors):
    video, duration = CLIPS[clip_id]
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot decode {video}")
    rows = []
    target = 0.0
    while target < duration - 1e-6:
        decoded, frame = capture.read()
        if not decoded:
            break
        if capture.get(cv2.CAP_PROP_POS_MSEC) / 1000 + 0.001 < target:
            continue
        rows.append(
            {
                "startSec": target,
                "endSec": min(round(target + 0.2, 3), duration),
                **detectors.detect(frame),
            }
        )
        target = round(target + 0.2, 3)
        if len(rows) % 50 == 0:
            print(f"{clip_id}: {len(rows)} frames", flush=True)
    capture.release()
    if not rows:
        raise RuntimeError(f"No sampled frames in {video}")
    (ROOT / f"{clip_id}_raw.json").write_text(json.dumps(rows))
    summary = build_observation(rows, rows[-1]["endSec"])
    (ROOT / f"{clip_id}_vision_v4.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )
    print(f"{clip_id}: complete {len(rows)} frames", flush=True)


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    detectors = VisionDetectors(PATHS)
    for clip_id in sys.argv[1:]:
        extract(clip_id, detectors)
