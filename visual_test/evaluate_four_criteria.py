"""Read-only exploratory diagnostics for four proposed Vision criteria."""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "backend"))
from analysis.modules.vision.observation import (
    _eye_region_is_covered,
    _face_direction,
    _hand_hull,
    _motion_range,
    _polygon_overlap,
    build_observation,
)

ROOT = Path("visual_test/results/four_criteria")
ROOT.mkdir(parents=True, exist_ok=True)
SOURCES = {
    "stillness_and_objects": Path("visual_test/results/example_video_comparison/raw.json"),
    "gaze_and_cover": Path("visual_test/results/new_gaze_video/raw.json"),
    "prior_negative_sample": Path("visual_test/results/model_comparison/raw.json"),
}


def hand_motion_episodes(rows, threshold):
    # Experimental transition count, not validated gesture recognition.
    history = []
    moving = []
    events = []
    stop_frames = 0
    for row in rows:
        body = row["body"]
        if not body:
            history.clear(); moving.clear(); stop_frames = 0
            continue
        points, conf = body["points"], body["confidence"]
        width = math.dist(points[5], points[6])
        height, frame_width = row["frameShape"]
        valid = width >= 20 and all(
            conf[k] >= 0.5 and 0 < points[k][0] < frame_width - 1 and 0 < points[k][1] < height - 1
            for k in (5, 6, 9, 10)
        )
        if not valid:
            history.clear(); moving.clear(); stop_frames = 0
            continue
        history.append([[(points[w][i] - points[s][i]) / width for i in (0, 1)] for s,w in ((5,9),(6,10))])
        history = history[-6:]
        if len(history) < 6:
            continue
        is_moving = _motion_range(history) > threshold
        if is_moving:
            moving.append(row)
            stop_frames = 0
        elif moving:
            stop_frames += 1
            if stop_frames >= 2:
                if moving[-1]["endSec"] - moving[0]["startSec"] >= 0.4:
                    events.append({"startSec": moving[0]["startSec"], "endSec": moving[-1]["endSec"]})
                moving.clear(); stop_frames = 0
    return events


def direction_runs(rows):
    result = []
    start = sign = None
    for row in [*rows, {"startSec": rows[-1]["endSec"], "face": None, "hands": [], "objects": []}]:
        face = row["face"]
        side = None
        if face and not _eye_region_is_covered(face, row.get("hands", []), row["objects"]):
            eyes = sorted(face["points"][:2], key=lambda point: point[0])
            axis = [eyes[1][i] - eyes[0][i] for i in (0, 1)]
            middle = [(eyes[0][i] + eyes[1][i]) / 2 for i in (0, 1)]
            nose = face["points"][2]
            offset = sum((nose[i] - middle[i]) * axis[i] for i in (0, 1)) / sum(v*v for v in axis)
            if abs(offset) > 0.18:
                side = "IMAGE_LEFT" if offset < 0 else "IMAGE_RIGHT"
        if side != sign:
            if sign is not None:
                result.append({"side": sign, "startSec": start, "endSec": row["startSec"], "durationSeconds": round(row["startSec"] - start, 1)})
            start,sign = (row["startSec"],side) if side is not None else (None,None)
    return result


if __name__ == "__main__":
    output = {}
    for name,path in SOURCES.items():
        rows=json.loads(path.read_text());summary=build_observation(rows,rows[-1]["endSec"])
        output[name]={
            "durationSeconds":rows[-1]["endSec"],
            "handObservableSeconds":summary["vision"]["handObservableSeconds"],
            "handCoverageRatio":summary["vision"]["handCoverageRatio"],
            "handStillSeconds":summary["vision"]["handStillSeconds"],
            "gestureEvents":summary["vision"]["gestureEvents"],
            "handFaceCandidates":[e for e in summary["vision"]["candidateEvents"] if e["kind"]=="HAND_FACE_OVERLAP_CANDIDATE"],
            "gazeUnknownIntervals":[e for e in summary["vision"]["unobservableIntervals"] if e["criterionKey"]=="GAZE"],
            "lateralRuns":direction_runs(rows),
            "experimentalMotionEpisodeCounts":{str(t):len(hand_motion_episodes(rows,t)) for t in (0.04,0.08)},
            "experimentalMotionEvents04":hand_motion_episodes(rows,0.04),
        }
    (ROOT/"metrics.json").write_text(json.dumps(output,ensure_ascii=False,indent=2))
    print(json.dumps({name:{"coverage":x["handCoverageRatio"],"motionCounts":x["experimentalMotionEpisodeCounts"],"lateralRuns":x["lateralRuns"]} for name,x in output.items()},ensure_ascii=False))
