"""Compare Vision rule candidates without changing the backend contract."""

import json
import math
import sys
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path.cwd() / "backend"))
from analysis.modules.vision.observation import (
    _hand_hull,
    _motion_range,
    _polygon_overlap,
    build_observation,
)

ROOT = Path("visual_test/results/followup_rule_evaluation")
SOURCES = {
    "example_development": Path("visual_test/results/example_video_comparison/raw.json"),
    "gaze_development": Path("visual_test/results/new_gaze_video/raw.json"),
    "malaysia_presentation": ROOT / "malaysia_presentation_raw.json",
    "facepalm": ROOT / "facepalm_raw.json",
    "ian_presentation": ROOT / "ian_presentation_raw.json",
    "dance_hand_lesson": ROOT / "dance_hand_lesson_raw.json",
    "signing_stress": Path("visual_test/results/four_criteria/public_hand_raw.json"),
}


def events_from_flags(rows, flags, minimum=5, bridge_one_unknown=False):
    events = []
    start = None
    unknown = 0.0
    for i in range(len(rows) + 1):
        flag = flags[i] if i < len(rows) else False
        bridge = (
            bridge_one_unknown
            and flag is None
            and i > 0
            and i + 1 < len(rows)
            and flags[i - 1] is True
            and flags[i + 1] is True
        )
        if flag is True or bridge:
            if start is None:
                start = rows[i]["startSec"]
            if bridge:
                unknown += rows[i]["endSec"] - rows[i]["startSec"]
        elif start is not None:
            end = rows[i - 1]["endSec"]
            if end - start >= minimum - 1e-6:
                events.append(
                    {
                        "startSec": round(start, 3),
                        "endSec": round(end, 3),
                        "unobservedSecondsInside": round(unknown, 3),
                    }
                )
            start = None
            unknown = 0.0
    return events


def stillness_trial(rows, threshold, smooth=False, keep_one_gap=False):
    history = []
    flags = []
    previous_valid_time = None
    for row in rows:
        body = row["body"]
        valid = False
        if body:
            points, confidence = body["points"], body["confidence"]
            width = math.dist(points[5], points[6])
            height, frame_width = row["frameShape"]
            valid = width >= 20 and all(
                confidence[k] >= 0.5
                and 0 < points[k][0] < frame_width - 1
                and 0 < points[k][1] < height - 1
                for k in (5, 6, 9, 10)
            )
        if not valid:
            flags.append(None)
            if not keep_one_gap or (
                previous_valid_time is not None
                and row["startSec"] - previous_valid_time > 0.2 + 1e-6
            ):
                history.clear()
            continue
        if previous_valid_time is not None and row["startSec"] - previous_valid_time > (
            0.4 if keep_one_gap else 0.2
        ) + 1e-6:
            history.clear()
        previous_valid_time = row["startSec"]
        history.append(
            [
                [(points[w][j] - points[s][j]) / width for j in (0, 1)]
                for s, w in ((5, 9), (6, 10))
            ]
        )
        history = history[-6:]
        if len(history) < 6:
            flags.append(None)
            continue
        if smooth:
            filtered = [
                [
                    [median(history[q][hand][axis] for q in range(max(0, k - 1), min(6, k + 2))) for axis in (0, 1)]
                    for hand in (0, 1)
                ]
                for k in range(6)
            ]
        else:
            filtered = history
        flags.append(_motion_range(filtered) <= threshold)
    return {
        "observableSeconds": round(sum((r["endSec"] - r["startSec"]) for r, f in zip(rows, flags) if f is not None), 3),
        "stillFrameSeconds": round(sum((r["endSec"] - r["startSec"]) for r, f in zip(rows, flags) if f is True), 3),
        "events": events_from_flags(rows, flags, bridge_one_unknown=keep_one_gap),
        "flags": flags,
    }


def motion_bouts(rows, threshold=0.04):
    history = []
    moving = []
    bouts = []
    stop = 0
    visible_moving = 0
    for row in rows:
        body = row["body"]
        valid = False
        if body:
            points, conf = body["points"], body["confidence"]
            width = math.dist(points[5], points[6])
            height, frame_width = row["frameShape"]
            valid = width >= 20 and all(
                conf[k] >= 0.5
                and 0 < points[k][0] < frame_width - 1
                and 0 < points[k][1] < height - 1
                for k in (5, 6, 9, 10)
            )
        if not valid:
            if moving:
                bouts.append({"startSec": moving[0], "endSec": moving[-1] + 0.2, "endStatus": "OBSERVATION_LOST"})
            history, moving, stop = [], [], 0
            continue
        history.append([[(points[w][j] - points[s][j]) / width for j in (0, 1)] for s, w in ((5, 9), (6, 10))])
        history = history[-6:]
        if len(history) < 6:
            continue
        if _motion_range(history) > threshold:
            moving.append(row["startSec"])
            visible_moving += 1
            stop = 0
        elif moving:
            stop += 1
            if stop >= 2:
                bouts.append({"startSec": moving[0], "endSec": moving[-1] + 0.2, "endStatus": "OBSERVED_STOP"})
                moving, stop = [], 0
    if moving:
        bouts.append({"startSec": moving[0], "endSec": moving[-1] + 0.2, "endStatus": "VIDEO_END"})
    bouts = [b for b in bouts if b["endSec"] - b["startSec"] >= 0.4 - 1e-6]
    return {
        "movingFrameSeconds": round(visible_moving * 0.2, 3),
        "completedCount": sum(b["endStatus"] == "OBSERVED_STOP" for b in bouts),
        "unfinishedCount": sum(b["endStatus"] != "OBSERVED_STOP" for b in bouts),
        "bouts": bouts,
    }


def shoulder_anchor(body):
    if not body:
        return None
    points = body["points"]
    width = math.dist(points[5], points[6])
    if width < 20 or min(body["confidence"][5], body["confidence"][6]) < 0.5:
        return None
    return ([(points[5][j] + points[6][j]) / 2 for j in (0, 1)], width)


def face_tracking_trial(rows, max_age):
    last = None
    flags = []
    for row in rows:
        face, anchor, hands = row["face"], shoulder_anchor(row["body"]), row.get("hands", [])
        direct = bool(face) and any(
            (_polygon_overlap(_hand_hull(hand), face["box"]) or 0) >= 0.1 for hand in hands
        )
        tracked = False
        if face and anchor:
            last = (row["startSec"], face["box"], anchor)
        elif face:
            last = None
        elif last and anchor and row["startSec"] - last[0] <= max_age + 1e-6:
            _, box, (old_center, old_width) = last
            center, width = anchor
            predicted = [
                center[axis] + (box[j] - old_center[axis]) * width / old_width
                for j, axis in enumerate((0, 1, 0, 1))
            ]
            tracked = any(
                (_polygon_overlap(_hand_hull(hand), predicted) or 0) >= 0.1
                for hand in hands
            )
        flags.append(bool(direct or tracked))
    return {
        "events": events_from_flags(rows, flags, minimum=0.4),
        "flags": flags,
    }


def interval_flags(rows, events):
    return [any(e["startSec"] <= r["startSec"] < e["endSec"] - 1e-6 for e in events) for r in rows]


def evaluate_clip(name, path):
    rows = json.loads(path.read_text())
    summary = build_observation(rows, rows[-1]["endSec"])
    base_cover = [e for e in summary["vision"]["candidateEvents"] if e["kind"] == "HAND_FACE_OVERLAP_CANDIDATE"]
    trial_still = {}
    for threshold, smooth, gap in ((0.04, False, False), (0.04, False, True), (0.04, True, True), (0.08, True, True), (0.12, True, True)):
        key = f"threshold_{threshold}_smooth_{smooth}_gap_{gap}"
        trial = stillness_trial(rows, threshold, smooth, gap)
        trial_still[key] = {k: v for k, v in trial.items() if k != "flags"}
    tracked_short = face_tracking_trial(rows, 1.0)
    tracked_long = face_tracking_trial(rows, 7.0)
    return {
        "durationSeconds": rows[-1]["endSec"],
        "frames": len(rows),
        "bodyFrames": sum(r["body"] is not None for r in rows),
        "faceFrames": sum(r["face"] is not None for r in rows),
        "handFrames": sum(bool(r.get("hands")) for r in rows),
        "baseline": {
            "handObservableSeconds": summary["vision"]["handObservableSeconds"],
            "handStillSeconds": summary["vision"]["handStillSeconds"],
            "handStillEvents": summary["vision"]["gestureEvents"],
            "handFaceEvents": base_cover,
        },
        "stillnessTrials": trial_still,
        "motionTrial": motion_bouts(rows),
        "faceTrackingTrials": {
            "shortOneSecond": tracked_short["events"],
            "longSevenSecondsExploratoryOnly": tracked_long["events"],
        },
        "_faceCoverFlags": {
            "baseline": interval_flags(rows, base_cover),
            "shortOneSecond": interval_flags(rows, tracked_short["events"]),
            "longSevenSeconds": interval_flags(rows, tracked_long["events"]),
        },
    }


if __name__ == "__main__":
    result = {name: evaluate_clip(name, path) for name, path in SOURCES.items()}
    (ROOT / "trial_metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    for name, output in result.items():
        print(name, output["baseline"]["handStillSeconds"], len(output["baseline"]["handFaceEvents"]), output["motionTrial"]["completedCount"], output["motionTrial"]["unfinishedCount"])
