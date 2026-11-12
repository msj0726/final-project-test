"""Experimental video observations for the scoring team's input, without scores."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from statistics import median

SAMPLE_SECONDS = 0.2
CONFIG_VERSION = "vision-20261111-v4-nonfront5-eye-occlusion"


def _distance(point: list[float], box: list[float]) -> float:
    x, y = point
    x1, y1, x2, y2 = box
    return math.hypot(max(x1 - x, 0, x - x2), max(y1 - y, 0, y - y2))


def _iou(first: list[float], second: list[float]) -> float:
    x1, y1 = max(first[0], second[0]), max(first[1], second[1])
    x2, y2 = min(first[2], second[2]), min(first[3], second[3])
    overlap = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = (first[2] - first[0]) * (first[3] - first[1])
    area_b = (second[2] - second[0]) * (second[3] - second[1])
    return overlap / max(1, area_a + area_b - overlap)


def _face_direction(face: dict | None) -> tuple[bool | None, str | None]:
    if face is None:
        return None, "NO_ASSOCIATED_FACE"
    eyes = sorted(face["points"][:2], key=lambda point: point[0])
    axis_x, axis_y = eyes[1][0] - eyes[0][0], eyes[1][1] - eyes[0][1]
    eye_distance = math.hypot(axis_x, axis_y)
    if eye_distance < 12:
        return None, "FACE_TOO_SMALL"
    eye_mid = [(eyes[0][j] + eyes[1][j]) / 2 for j in (0, 1)]
    mouth_mid = [(face["points"][3][j] + face["points"][4][j]) / 2 for j in (0, 1)]
    vertical = [-axis_y / eye_distance, axis_x / eye_distance]
    height = sum((mouth_mid[j] - eye_mid[j]) * vertical[j] for j in (0, 1))
    if height <= 3:
        return None, "INVALID_LANDMARK_GEOMETRY"
    nose = face["points"][2]
    horizontal_offset = (
        (nose[0] - eye_mid[0]) * axis_x + (nose[1] - eye_mid[1]) * axis_y
    ) / eye_distance**2
    nose_fraction = sum((nose[j] - eye_mid[j]) * vertical[j] for j in (0, 1)) / height
    return (
        abs(horizontal_offset) <= 0.18
        and 0.2 <= nose_fraction <= 0.8
        and 0.3 <= height / eye_distance <= 1.3
        and abs(math.degrees(math.atan2(axis_y, axis_x))) <= 20,
        None,
    )


def _polygon_overlap(polygon: list[list[float]], box: list[float] | None) -> float | None:
    if box is None or len(polygon) < 3:
        return None
    x1, y1, x2, y2 = box
    if x2 <= x1 or y2 <= y1:
        return None
    clipped = polygon
    for index, boundary, keep in (
        (0, x1, lambda value, edge: value >= edge),
        (0, x2, lambda value, edge: value <= edge),
        (1, y1, lambda value, edge: value >= edge),
        (1, y2, lambda value, edge: value <= edge),
    ):
        result = []
        for start, end in zip(clipped, clipped[1:] + clipped[:1]):
            start_inside, end_inside = keep(start[index], boundary), keep(end[index], boundary)
            if start_inside != end_inside:
                fraction = (boundary - start[index]) / (end[index] - start[index])
                result.append([start[j] + fraction * (end[j] - start[j]) for j in (0, 1)])
            if end_inside:
                result.append(end)
        clipped = result
        if not clipped:
            return 0.0
    area = (
        abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(clipped, clipped[1:] + clipped[:1]))) / 2
    )
    return min(1.0, area / ((x2 - x1) * (y2 - y1)))


def _hand_hull(points: list[list[float]]) -> list[list[float]]:
    ordered = sorted({(float(x), float(y)) for x, y in points})
    if len(ordered) < 3:
        return []

    def cross(start, middle, end):
        return (middle[0] - start[0]) * (end[1] - start[1]) - (middle[1] - start[1]) * (
            end[0] - start[0]
        )

    lower, upper = [], []
    for sequence, hull in ((ordered, lower), (reversed(ordered), upper)):
        for point in sequence:
            while len(hull) >= 2 and cross(hull[-2], hull[-1], point) <= 0:
                hull.pop()
            hull.append(point)
    return [list(point) for point in lower[:-1] + upper[:-1]]


def _eye_region_is_covered(face: dict, hands: list, objects: list) -> bool:
    eyes = face["points"][:2]
    width = face["box"][2] - face["box"][0]
    height = face["box"][3] - face["box"][1]
    eye_box = [
        min(point[0] for point in eyes) - width * 0.08,
        min(point[1] for point in eyes) - height * 0.07,
        max(point[0] for point in eyes) + width * 0.08,
        max(point[1] for point in eyes) + height * 0.07,
    ]
    # shortcut: 2D overlap cannot prove depth; validate on labeled side-hand videos before scoring.
    return any(
        (_polygon_overlap(polygon, eye_box) or 0) >= 0.25
        for polygon in [
            *(_hand_hull(hand) for hand in hands),
            *(obj["polygon"] for obj in objects),
        ]
    )


def _motion_range(history: list[list[list[float]]]) -> float:
    return max(
        math.hypot(*(history[i][w][j] - history[k][w][j] for j in (0, 1)))
        for i in range(len(history))
        for k in range(i)
        for w in (0, 1)
    )


def _is_comoving(history: list[tuple[float, list[float], list[float]]]) -> tuple[bool | None, str]:
    if len(history) < 6 or history[-1][0] - history[0][0] < 1 - 1e-6:
        return None, "TEMPORAL_WARMUP"
    first_wrist, first_object = history[0][1:]
    wrist = [[point[1][j] - first_wrist[j] for j in (0, 1)] for point in history]
    obj = [[point[2][j] - first_object[j] for j in (0, 1)] for point in history]
    wrist_motion = max(math.hypot(*point) for point in wrist)
    object_motion = max(math.hypot(*point) for point in obj)
    if min(wrist_motion, object_motion) < 0.03:
        return False, "INSUFFICIENT_MOTION"
    dot = sum(sum(a[j] * b[j] for j in (0, 1)) for a, b in zip(wrist, obj))
    norms = math.sqrt(
        sum(sum(value * value for value in point) for point in wrist)
        * sum(sum(value * value for value in point) for point in obj)
    )
    residual = math.sqrt(
        sum(sum((a[j] - b[j]) ** 2 for j in (0, 1)) for a, b in zip(wrist, obj)) / len(history)
    )
    if dot / norms < 0.8 or residual > 0.05:
        return False, "MOTION_MISMATCH"
    return True, ""


def _events(rows: list[dict], flags: list[bool | None], kind: str, minimum: float) -> list[dict]:
    events = []
    start = end = None
    for row, flag in [*zip(rows, flags), (None, False)]:
        if flag is True:
            if start is None:
                start = row["startSec"]
            end = row["endSec"]
        elif start is not None:
            if end - start >= minimum - 1e-6:
                event_id = f"vision-{kind.lower()}-{len(events) + 1}"
                events.append(
                    dict(
                        eventId=event_id,
                        kind=kind,
                        startSec=round(start, 3),
                        endSec=round(end, 3),
                        confidence=None,
                        evidenceRefs=[f"{event_id}-evidence"],
                    )
                )
            start = end = None
    return events


def _unknown_intervals(rows: list[dict], criterion: str, value: str, reason: str) -> list[dict]:
    intervals = []
    for row in rows:
        if row[value] is not None:
            continue
        if (
            intervals
            and intervals[-1]["reasonCode"] == row[reason]
            and abs(intervals[-1]["endSec"] - row["startSec"]) < 1e-6
        ):
            intervals[-1]["endSec"] = row["endSec"]
        else:
            intervals.append(
                dict(
                    criterionKey=criterion,
                    startSec=row["startSec"],
                    endSec=row["endSec"],
                    reasonCode=row[reason],
                )
            )
    return intervals


def _object_events(detections: list[tuple[dict, dict]], track_id: str, kind: str, flag: str):
    events = []
    current = []
    last_end = None
    for row, obj in [*detections, (None, None)]:
        is_true = obj is not None and obj[flag] is True
        if current and (not is_true or abs(row["startSec"] - last_end) > 1e-6):
            start = current[0][0]["startSec"]
            if last_end - start >= 0.4 - 1e-6:
                event_id = f"vision-{kind.lower()}-{track_id}-{len(events) + 1}"
                events.append(
                    dict(
                        eventId=event_id,
                        kind=kind,
                        startSec=round(start, 3),
                        endSec=round(last_end, 3),
                        confidence=None,
                        evidenceRefs=[f"{event_id}-evidence"],
                        objectTrackId=track_id,
                        objectLabel=current[0][1]["label"],
                        objectLabelConfidence=round(
                            median(item[1]["confidence"] for item in current), 3
                        ),
                    )
                )
            current = []
        if is_true:
            current.append((row, obj))
            last_end = row["endSec"]
    return events


def build_observation(frames: Iterable[dict], duration_seconds: float) -> dict:
    """Convert 5 FPS detector rows into the agreed observation JSON."""
    rows = list(frames)
    if not rows or duration_seconds <= 0:
        raise ValueError("The video has no decodable frames")
    hand_history = []
    previous_body = None
    tracks = {}
    next_track = 0
    diagnostics = defaultdict(int)
    for row in rows:
        body, face = row["body"], row["face"]
        row["isCameraFacing"], row["gazeReason"] = _face_direction(face)
        if face and _eye_region_is_covered(face, row.get("hands", []), row["objects"]):
            row["isCameraFacing"], row["gazeReason"] = None, "EYE_REGION_OVERLAP"
        row["isHandFaceOverlapCandidate"] = bool(face) and any(
            (_polygon_overlap(_hand_hull(hand), face["box"]) or 0) >= 0.1
            for hand in row.get("hands", [])
        )
        row["isBothHandsStill"], row["handStillReason"] = None, "NO_BODY"
        row["bothWristsVisible"] = False
        wrist_points, shoulder_width, anchor = {}, 0.0, None
        if body:
            points, confidence = body["points"], body["confidence"]
            shoulder_width = math.dist(points[5], points[6])
            current_body = body["box"]
            if previous_body:
                old_width = max(1, previous_body[2] - previous_body[0])
                old_center = [(previous_body[j] + previous_body[j + 2]) / 2 for j in (0, 1)]
                center = [(current_body[j] + current_body[j + 2]) / 2 for j in (0, 1)]
                if (
                    math.dist(center, old_center) > old_width * 0.5
                    or abs((current_body[2] - current_body[0]) / old_width - 1) > 0.4
                ):
                    row["sceneCut"] = True
            previous_body = current_body
            height, width = row["frameShape"]
            valid_shoulders = shoulder_width >= 20 and all(
                confidence[j] >= 0.5
                and 0 < points[j][0] < width - 1
                and 0 < points[j][1] < height - 1
                for j in (5, 6)
            )
            if valid_shoulders:
                anchor = [(points[5][j] + points[6][j]) / 2 for j in (0, 1)]
                wrist_points = {
                    j: points[j]
                    for j in (9, 10)
                    if confidence[j] >= 0.5
                    and 0 < points[j][0] < width - 1
                    and 0 < points[j][1] < height - 1
                }
            row["bothWristsVisible"] = len(wrist_points) == 2
            if row["bothWristsVisible"]:
                if row.get("sceneCut"):
                    hand_history = []
                hand_history.append(
                    [
                        [(points[w][j] - points[s][j]) / shoulder_width for j in (0, 1)]
                        for s, w in ((5, 9), (6, 10))
                    ]
                )
                hand_history = hand_history[-6:]
                if len(hand_history) == 6:
                    row["isBothHandsStill"] = _motion_range(hand_history) <= 0.04
                    row["handStillReason"] = None
                else:
                    row["handStillReason"] = "TEMPORAL_WARMUP"
            else:
                hand_history = []
                row["handStillReason"] = "WRISTS_OR_SHOULDERS_UNOBSERVABLE"
        else:
            previous_body = None
            hand_history = []
        if row.get("sceneCut"):
            tracks = {}
        active = {
            key: value
            for key, value in tracks.items()
            if row["startSec"] - value["lastSeenSec"] <= 0.4 + 1e-6
        }
        used = set()
        for obj in row["objects"]:
            matches = [
                (_iou(obj["box"], value["box"]), key)
                for key, value in tracks.items()
                if value["label"] == obj["label"]
                and key not in used
                and row["startSec"] - value["lastSeenSec"] - SAMPLE_SECONDS <= 0.4 + 1e-6
            ]
            overlap, track_id = max(matches, default=(0, None))
            if overlap < 0.3:
                next_track += 1
                track_id = f"object-{next_track}"
                track = dict(history=[], wristSide=None)
            else:
                track = tracks[track_id]
                used.add(track_id)
            obj["objectTrackId"] = track_id
            wrist_side = min(
                wrist_points,
                key=lambda index: _distance(wrist_points[index], obj["box"]),
                default=None,
            )
            is_near = (
                wrist_side is not None
                and _distance(wrist_points[wrist_side], obj["box"]) <= shoulder_width * 0.12
            )
            if is_near:
                diagnostics["nearWristDetectionCount"] += 1
                if track["wristSide"] != wrist_side:
                    track["history"] = []
                track["wristSide"] = wrist_side
                obj_center = [(obj["box"][j] + obj["box"][j + 2]) / 2 for j in (0, 1)]
                track["history"].append(
                    (
                        row["startSec"],
                        [
                            (wrist_points[wrist_side][j] - anchor[j]) / shoulder_width
                            for j in (0, 1)
                        ],
                        [(obj_center[j] - anchor[j]) / shoulder_width for j in (0, 1)],
                    )
                )
                track["history"] = [
                    item for item in track["history"] if row["startSec"] - item[0] <= 1 + 1e-6
                ]
                obj["isComoving"], reason = _is_comoving(track["history"])
                if reason:
                    diagnostics[
                        {
                            "TEMPORAL_WARMUP": "insufficientHistoryCount",
                            "MOTION_MISMATCH": "motionMismatchCount",
                            "INSUFFICIENT_MOTION": "insufficientMotionCount",
                        }[reason]
                    ] += 1
                if obj["isComoving"]:
                    diagnostics["comovingDetectionCount"] += 1
            else:
                track["history"] = []
                obj["isComoving"] = None if wrist_side is None else False
            face_overlap = _polygon_overlap(obj["polygon"], face["box"] if face else None)
            obj["isFaceOverlapCandidate"] = face_overlap is not None and face_overlap >= 0.1
            track.update(box=obj["box"], label=obj["label"], lastSeenSec=row["startSec"])
            active[track_id] = track
        tracks = active

    still_events = _events(rows, [row["isBothHandsStill"] for row in rows], "HAND_STILLNESS", 5)
    nonfront_events = _events(
        rows,
        [row["isCameraFacing"] is False for row in rows],
        "FACE_NONFRONT_CANDIDATE",
        5,
    )
    hand_face_events = _events(
        rows,
        [row["isHandFaceOverlapCandidate"] for row in rows],
        "HAND_FACE_OVERLAP_CANDIDATE",
        0.4,
    )
    detections_by_track = defaultdict(list)
    for row in rows:
        for obj in row["objects"]:
            detections_by_track[obj["objectTrackId"]].append((row, obj))
    candidates = hand_face_events
    for track_id, detections in detections_by_track.items():
        for kind, flag in (
            ("OBJECT_INTERACTION_CANDIDATE", "isComoving"),
            ("OBJECT_FACE_OVERLAP_CANDIDATE", "isFaceOverlapCandidate"),
        ):
            candidates.extend(_object_events(detections, track_id, kind, flag))
    events = still_events + nonfront_events + candidates
    evidence = [
        dict(
            evidenceId=event["evidenceRefs"][0],
            sourceType="VISION",
            startSec=event["startSec"],
            endSec=event["endSec"],
            description={
                "HAND_STILLNESS": "양손목의 몸통 상대 위치가 5초 이상 연속 정지한 후보",
                "FACE_NONFRONT_CANDIDATE": (
                    "얼굴 방향이 중앙 카메라 기준 비정면으로 5초 이상 연속 판정된 후보; "
                    "눈동자 시선·관객 응시 미확정"
                ),
                "OBJECT_INTERACTION_CANDIDATE": "손목 근접 및 동반 이동 후보; 접촉과 관련성 미확정",
                "OBJECT_FACE_OVERLAP_CANDIDATE": (
                    "물건 마스크와 얼굴 박스의 겹침 후보; 실제 가림 미확정"
                ),
                "HAND_FACE_OVERLAP_CANDIDATE": (
                    "손 특징점 외곽과 얼굴 박스의 겹침 후보; 실제 가림 미확정"
                ),
            }[event["kind"]],
        )
        for event in events
    ]
    gaze_observable = round(
        sum(row["endSec"] - row["startSec"] for row in rows if row["isCameraFacing"] is not None), 3
    )
    front_facing = round(
        sum(row["endSec"] - row["startSec"] for row in rows if row["isCameraFacing"] is True), 3
    )
    hand_observable = round(
        sum(row["endSec"] - row["startSec"] for row in rows if row["isBothHandsStill"] is not None),
        3,
    )
    both_visible = round(
        sum(row["endSec"] - row["startSec"] for row in rows if row["bothWristsVisible"]), 3
    )
    interaction_refs = [
        ref
        for event in candidates
        if event["kind"] == "OBJECT_INTERACTION_CANDIDATE"
        for ref in event["evidenceRefs"]
    ]
    return {
        "schemaVersion": "vision-observation-v4-experiment",
        "observationConfigVersion": CONFIG_VERSION,
        "sourceStartSec": 0,
        "sourceEndSec": round(duration_seconds, 3),
        "sampleDurationSeconds": round(duration_seconds, 3),
        "isScoringReady": False,
        "vision": {
            "gaze": {
                "observableSeconds": gaze_observable,
                "frontFacingSeconds": front_facing,
                "frontFacingRatio": front_facing / gaze_observable if gaze_observable else None,
                "coverageRatio": gaze_observable / duration_seconds,
                "method": "EXPERIMENTAL_5_POINT_FACE_GEOMETRY",
                "nonFrontFacingEvents": nonfront_events,
            },
            "handObservableSeconds": hand_observable,
            "handStillSeconds": round(
                sum(event["endSec"] - event["startSec"] for event in still_events), 3
            )
            if hand_observable
            else None,
            "bothWristsVisibleSeconds": both_visible,
            "handCoverageRatio": hand_observable / duration_seconds,
            "gestureEvents": still_events,
            "candidateEvents": candidates,
            "interactionDiagnostics": {
                **{
                    key: diagnostics[key]
                    for key in (
                        "nearWristDetectionCount",
                        "insufficientHistoryCount",
                        "motionMismatchCount",
                        "insufficientMotionCount",
                        "comovingDetectionCount",
                    )
                },
                "unit": "DETECTION_INSTANCES_NOT_EVENTS",
            },
            "unobservableIntervalsStatus": "GENERATED",
            "unobservableIntervals": _unknown_intervals(
                rows, "GAZE", "isCameraFacing", "gazeReason"
            )
            + _unknown_intervals(rows, "HAND_STILLNESS", "isBothHandsStill", "handStillReason"),
            "criterionStatus": {
                "HAND_STILLNESS": "EVALUATED" if hand_observable else "UNOBSERVABLE",
                "FACE_OCCLUSION": "CANDIDATE_ONLY",
                "UNRELATED_OBJECT_TOUCH": "NOT_EVALUATED",
            },
        },
        "evidence": evidence,
        "contextJudgments": [
            {
                "criterionKey": "UNRELATED_OBJECT_TOUCH",
                "status": "NOT_RUN",
                "verdict": None,
                "reason": "LLM_NOT_EXECUTED",
                "evidenceRefs": interaction_refs,
            }
        ],
        "limitations": [
            "점수 환산 보류; 이 결과는 루브릭 입력용 관찰값이며 최종 Report가 아님.",
            "양손 정지는 손목 기준 5초; 손가락 움직임은 판정하지 않음.",
            (
                "카메라 정면은 얼굴 5점 기하의 추정이며 실제 눈동자 시선이 아님. "
                "손·물건이 눈 영역과 겹치면 관찰 불가로 제외."
            ),
            "물건의 실제 얼굴 가림·접촉·발표 관련성은 확정하지 않음.",
            "0.4초 물건 추적 ID만 유지하며 미검출 프레임은 보간하지 않음.",
            "실험 임계값은 독립 정확도 검증 전; 미검출은 행동 부재가 아님.",
            "손 특징점 외곽과 얼굴 박스의 2D 겹침은 실제 가림을 확정하지 않음.",
        ],
    }
