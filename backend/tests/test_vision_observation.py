from pathlib import Path

import pytest

from analysis.modules.vision import VisionModelPaths, analyze_video
from analysis.modules.vision.observation import build_observation


def frame(index: int, *, hands_visible: bool = True, moving: bool = False) -> dict:
    points = [[0, 0] for _ in range(17)]
    points[5], points[6] = [100, 200], [200, 200]
    points[9], points[10] = [120 + (index * 2 if moving else 0), 250], [180, 250]
    confidence = [1.0] * 17
    if not hands_visible:
        confidence[9] = confidence[10] = 0.0
    return {
        "startSec": round(index * 0.2, 3),
        "endSec": round((index + 1) * 0.2, 3),
        "sceneCut": False,
        "frameShape": (540, 960),
        "body": {
            "box": [60, 80, 260, 500],
            "points": points,
            "confidence": confidence,
        },
        "face": {
            "box": [125, 90, 175, 145],
            "points": [[130, 110], [170, 110], [150, 125], [140, 140], [160, 140]],
            "confidence": 0.9,
        },
        "objects": [],
    }


def test_stationary_wrist_event_and_observation_contract():
    result = build_observation((frame(index) for index in range(50)), 10)

    assert result["isScoringReady"] is False
    assert "score" not in result and "totalScore" not in result
    assert result["vision"]["gaze"] == {
        "observableSeconds": 10,
        "frontFacingSeconds": 10,
        "frontFacingRatio": 1,
        "coverageRatio": 1,
        "method": "EXPERIMENTAL_5_POINT_FACE_GEOMETRY",
        "nonFrontFacingEvents": [],
    }
    assert result["vision"]["handObservableSeconds"] == 9
    assert result["vision"]["handStillSeconds"] == 9
    assert result["vision"]["gestureEvents"][0]["startSec"] == 1
    assert result["vision"]["gestureEvents"][0]["endSec"] == 10
    assert (
        result["evidence"][0]["evidenceId"]
        == result["vision"]["gestureEvents"][0]["evidenceRefs"][0]
    )
    assert result["vision"]["unobservableIntervals"] == [
        {
            "criterionKey": "HAND_STILLNESS",
            "startSec": 0,
            "endSec": 1,
            "reasonCode": "TEMPORAL_WARMUP",
        }
    ]


def test_hidden_hands_are_unknown_and_do_not_create_a_good_score():
    rows = [frame(index, hands_visible=False) for index in range(50)]
    result = build_observation(rows, 10)

    assert result["vision"]["handObservableSeconds"] == 0
    assert result["vision"]["handStillSeconds"] is None
    assert result["vision"]["gestureEvents"] == []
    assert result["vision"]["criterionStatus"]["HAND_STILLNESS"] == "UNOBSERVABLE"
    assert result["vision"]["unobservableIntervals"] == [
        {
            "criterionKey": "HAND_STILLNESS",
            "startSec": 0,
            "endSec": 10,
            "reasonCode": "WRISTS_OR_SHOULDERS_UNOBSERVABLE",
        }
    ]


def test_five_seconds_is_the_minimum_still_event():
    short = build_observation((frame(index) for index in range(29)), 5.8)
    long = build_observation((frame(index) for index in range(30)), 6)

    assert short["vision"]["gestureEvents"] == []
    assert short["vision"]["handStillSeconds"] == 0
    assert len(long["vision"]["gestureEvents"]) == 1
    assert long["vision"]["handStillSeconds"] == 5


def test_unseen_face_does_not_become_zero_gaze_score():
    rows = [frame(index) for index in range(5)]
    for row in rows:
        row["face"] = None
    result = build_observation(rows, 1)

    assert result["vision"]["gaze"]["frontFacingRatio"] is None
    assert result["vision"]["gaze"]["observableSeconds"] == 0
    assert result["vision"]["gaze"]["nonFrontFacingEvents"] == []
    assert result["vision"]["unobservableIntervals"][0] == {
        "criterionKey": "GAZE",
        "startSec": 0,
        "endSec": 1,
        "reasonCode": "NO_ASSOCIATED_FACE",
    }


def test_five_second_nonfront_face_event_has_evidence():
    rows = [frame(index) for index in range(25)]
    for row in rows:
        row["face"]["points"][2][0] += 10
    result = build_observation(rows, 5)

    event = result["vision"]["gaze"]["nonFrontFacingEvents"][0]
    assert event["kind"] == "FACE_NONFRONT_CANDIDATE"
    assert (event["startSec"], event["endSec"]) == (0, 5)
    assert event["confidence"] is None
    assert result["evidence"][0]["evidenceId"] == event["evidenceRefs"][0]


def test_short_or_unobservable_nonfront_runs_do_not_join():
    rows = [frame(index) for index in range(49)]
    for row in rows:
        row["face"]["points"][2][0] += 10
    rows[24]["face"] = None
    result = build_observation(rows, 9.8)

    assert result["vision"]["gaze"]["nonFrontFacingEvents"] == []


def test_eye_cover_breaks_nonfront_run():
    rows = [frame(index) for index in range(49)]
    for row in rows:
        row["face"]["points"][2][0] += 10
    rows[24]["hands"] = [[[125, 100], [175, 100], [175, 120], [125, 120]]]
    result = build_observation(rows, 9.8)

    assert result["vision"]["gaze"]["nonFrontFacingEvents"] == []
    assert any(
        interval["reasonCode"] == "EYE_REGION_OVERLAP"
        for interval in result["vision"]["unobservableIntervals"]
    )


def test_object_interaction_stays_a_candidate_for_llm():
    rows = [frame(index, moving=True) for index in range(12)]
    for index, row in enumerate(rows):
        x1 = 112 + index * 2
        row["objects"] = [
            {
                "label": "cell phone",
                "confidence": 0.8,
                "box": [x1, 240, x1 + 20, 260],
                "polygon": [[x1, 240], [x1 + 20, 240], [x1 + 20, 260], [x1, 260]],
            }
        ]
    result = build_observation(rows, 2.4)

    assert result["vision"]["gestureEvents"] == []
    candidates = result["vision"]["candidateEvents"]
    assert len(candidates) == 1
    assert candidates[0]["kind"] == "OBJECT_INTERACTION_CANDIDATE"
    assert candidates[0]["objectLabel"] == "cell phone"
    assert result["contextJudgments"][0]["status"] == "NOT_RUN"
    assert result["contextJudgments"][0]["verdict"] is None
    assert result["contextJudgments"][0]["evidenceRefs"] == candidates[0]["evidenceRefs"]


def test_face_overlap_is_only_a_candidate():
    rows = [frame(index) for index in range(2)]
    for row in rows:
        row["objects"] = [
            {
                "label": "book",
                "confidence": 0.8,
                "box": [125, 90, 175, 145],
                "polygon": [[125, 90], [175, 90], [175, 145], [125, 145]],
            }
        ]
    result = build_observation(rows, 0.4)

    assert [event["kind"] for event in result["vision"]["candidateEvents"]] == [
        "OBJECT_FACE_OVERLAP_CANDIDATE"
    ]
    assert result["vision"]["criterionStatus"]["FACE_OCCLUSION"] == "CANDIDATE_ONLY"


def test_hand_face_overlap_is_a_candidate_with_evidence():
    rows = [frame(index) for index in range(3)]
    for row in rows:
        row["hands"] = [[[125, 90], [175, 90], [175, 145], [125, 145]]]
    result = build_observation(rows, 0.6)

    candidate = result["vision"]["candidateEvents"][0]
    assert candidate["kind"] == "HAND_FACE_OVERLAP_CANDIDATE"
    assert (candidate["startSec"], candidate["endSec"]) == (0, 0.6)
    assert candidate["confidence"] is None
    assert result["evidence"][0]["evidenceId"] == candidate["evidenceRefs"][0]


def test_unassociated_face_does_not_create_hand_overlap():
    rows = [frame(index) for index in range(3)]
    for row in rows:
        row["face"] = None
        row["hands"] = [[[125, 90], [175, 90], [175, 145], [125, 145]]]
    result = build_observation(rows, 0.6)

    assert result["vision"]["candidateEvents"] == []


def test_hand_over_eyes_is_unobservable_for_gaze():
    rows = [frame(index) for index in range(3)]
    for row in rows:
        row["hands"] = [[[125, 100], [175, 100], [175, 120], [125, 120]]]
    result = build_observation(rows, 0.6)

    assert result["vision"]["gaze"]["observableSeconds"] == 0
    assert result["vision"]["gaze"]["frontFacingRatio"] is None
    assert result["vision"]["unobservableIntervals"][0] == {
        "criterionKey": "GAZE",
        "startSec": 0,
        "endSec": 0.6,
        "reasonCode": "EYE_REGION_OVERLAP",
    }


def test_hand_beside_face_keeps_gaze_observable():
    rows = [frame(index) for index in range(3)]
    for row in rows:
        row["hands"] = [[[125, 125], [155, 125], [155, 145], [125, 145]]]
    result = build_observation(rows, 0.6)

    assert result["vision"]["gaze"]["observableSeconds"] == 0.6
    assert result["vision"]["gaze"]["frontFacingSeconds"] == 0.6


def test_object_over_eyes_is_unobservable_for_gaze():
    rows = [frame(index) for index in range(3)]
    for row in rows:
        row["objects"] = [
            {
                "label": "cell phone",
                "confidence": 0.8,
                "box": [125, 100, 175, 120],
                "polygon": [[125, 100], [175, 100], [175, 120], [125, 120]],
            }
        ]
    result = build_observation(rows, 0.6)

    assert result["vision"]["gaze"]["observableSeconds"] == 0
    assert result["vision"]["unobservableIntervals"][0]["reasonCode"] == "EYE_REGION_OVERLAP"


def test_missing_input_is_rejected_before_loading_models(tmp_path: Path):
    missing = tmp_path / "video.mp4"
    model_paths = VisionModelPaths(missing, missing, missing, tmp_path)
    with pytest.raises(FileNotFoundError, match="video file"):
        analyze_video(missing, model_paths)
