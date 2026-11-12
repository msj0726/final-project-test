"""Evaluate a 5-second central-camera face-direction rule on stored detections."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "backend"))
from analysis.modules.vision.observation import _face_direction, _hand_hull, _polygon_overlap

ROOT = Path("visual_test/results/example_video_comparison")
MIN_AWAY_SECONDS = 5.0


def away_intervals(rows, *, exclude_overlap=False):
    intervals = []
    start = None
    for row in [*rows, {"startSec": rows[-1]["endSec"], "face": None, "hands": [], "objects": []}]:
        direction, _ = _face_direction(row["face"])
        overlap = bool(row["face"]) and (
            any(
                (_polygon_overlap(_hand_hull(hand), row["face"]["box"]) or 0) >= 0.1
                for hand in row.get("hands", [])
            )
            or any(
                (_polygon_overlap(obj["polygon"], row["face"]["box"]) or 0) >= 0.1
                for obj in row.get("objects", [])
            )
        )
        is_away = direction is False and (not exclude_overlap or not overlap)
        if is_away and start is None:
            start = row["startSec"]
        elif not is_away and start is not None:
            end = row["startSec"]
            intervals.append({"startSec": start, "endSec": end, "durationSeconds": round(end - start, 3)})
            start = None
    return intervals


def qualifying(intervals):
    return [event for event in intervals if event["durationSeconds"] >= MIN_AWAY_SECONDS]


if __name__ == "__main__":
    rows = json.loads((ROOT / "raw.json").read_text())
    observed = away_intervals(rows)
    masked = away_intervals(rows, exclude_overlap=True)
    # These checks test duration/unknown handling, not model recognition accuracy.
    assert qualifying([{"durationSeconds": 4.8}]) == []
    assert len(qualifying([{"durationSeconds": 5.0}])) == 1
    assert qualifying([{"durationSeconds": 2.6}, {"durationSeconds": 2.6}]) == []
    result = {
        "source": "예시.mov",
        "cameraAssumption": "AUDIENCE_CENTER_NEAR_CAMERA",
        "positiveMeaning": "FACE_DIRECTION_TOWARD_CENTER_CAMERA_OR_FRONT_AUDIENCE_PROXY",
        "negativeRule": "CONTINUOUS_OBSERVABLE_AWAY_AT_LEAST_5_SECONDS",
        "faceDirectionOnly": True,
        "awayIntervals": observed,
        "negativeCandidateEvents": qualifying(observed),
        "strictOverlapMaskComparison": {
            "awayIntervals": masked,
            "negativeCandidateEvents": qualifying(masked),
            "status": "DIAGNOSTIC_ONLY_OVEREXCLUDES_SIDE_LOOKING_WITH_HAND_NEAR_FACE",
        },
        "coverageSeconds": 49.4,
        "videoSeconds": 62.8,
        "humanLabel": "NO_INTENTIONAL_LONG_AWAY_IN_THIS_VIDEO_USER_CONFIRMED",
        "eyeGazeValidated": False,
    }
    (ROOT / "central_camera_gaze_test.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({"awayIntervals": observed, "fiveSecondEvents": qualifying(observed)}, ensure_ascii=False))
