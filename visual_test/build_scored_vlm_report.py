"""Aggregate experimental VLM observations into user-specified visual scores."""

import base64
import html
import json
import math
from pathlib import Path

from score_vlm_video import PROMPT, QWEN_CRITERIA_PROMPT, ROOT, validate

PROVIDERS = (
    ("openai", "GPT-6.1 Sol · API"),
    ("qwen", "Qwen3.5-9B · 기존 프롬프트"),
    ("qwen_criteria", "Qwen3.5-9B · 기준 명시 프롬프트"),
)


def merge(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1] + 1e-6:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def duration(intervals):
    return sum(end - start for start, end in merge(intervals))


def subtract(intervals, blocked):
    remaining = []
    for start, end in merge(intervals):
        pieces = [[start, end]]
        for cut_start, cut_end in merge(blocked):
            pieces = [[a, min(b, cut_start)] for a, b in pieces if a < cut_start and min(b, cut_start) > a] + [[max(a, cut_end), b] for a, b in pieces if b > cut_end and b > max(a, cut_end)]
        remaining.extend(pieces)
    return merge(remaining)


def intersect(left, right):
    return merge([[max(a, c), min(b, d)] for a, b in left for c, d in right if max(a, c) < min(b, d)])


def score_model(provider, manifest):
    video_duration = manifest["durationSeconds"]
    visible = []
    still = []
    motion_stops = []
    face_cover = []
    unrelated = []
    off_target = []
    unobservable = []
    failures = []
    semantic_issues = []
    motion_stillness_conflicts = []
    model_seconds = 0
    cost = 0
    for window in manifest["windows"]:
        path = ROOT / f"{provider}_v3_{window['id']}.json"
        if not path.exists():
            failures.append({"windowId": window["id"], "reason": "NOT_RUN"})
            unobservable.append([window["startSec"], window["endSec"]])
            continue
        output = json.loads(path.read_text())
        model_seconds += output.get("elapsedSeconds", 0)
        cost += output.get("costUsdUpperBound", 0)
        if output.get("status") != "OK":
            failures.append({"windowId": window["id"], "reason": output.get("error", output.get("httpStatus", output.get("status")))})
            unobservable.append([window["startSec"], window["endSec"]])
            continue
        try:
            result = validate(output["result"], window)
        except (ValueError, TypeError, KeyError) as error:
            failures.append({"windowId": window["id"], "reason": "REVALIDATION: " + str(error)})
            unobservable.append([window["startSec"], window["endSec"]])
            continue
        visible.extend(result["bothWristsVisibleIntervals"])
        still.extend(intersect(result["bothWristsStillCandidateIntervals"], result["bothWristsVisibleIntervals"]))
        if duration(result["bothWristsStillCandidateIntervals"]) > duration(intersect(result["bothWristsStillCandidateIntervals"], result["bothWristsVisibleIntervals"])) + 1e-6:
            semantic_issues.append({"windowId": window["id"], "reason": "STILLNESS_OUTSIDE_WRIST_VISIBILITY"})
        motion_stops.extend(result["handMotionStopSeconds"])
        conflicting_stops = [second for second in result["handMotionStopSeconds"] if any(start + 0.5 < second < end - 0.5 for start, end in result["bothWristsStillCandidateIntervals"])]
        if conflicting_stops:
            motion_stillness_conflicts.append({"windowId": window["id"], "handMotionStopSeconds": conflicting_stops})
        face_cover.extend([[e["startSec"], e["endSec"]] for e in result["faceCoverEvents"]])
        unrelated.extend(result["unrelatedObjectTouchEvents"])
        off_target.extend(result["headOffTargetIntervals"])
        unobservable.extend(result["gazeUnobservableIntervals"])
        if duration(intersect(result["gazeUnobservableIntervals"], result["headOffTargetIntervals"])) > 0:
            semantic_issues.append({"windowId": window["id"], "reason": "OFF_TARGET_AND_UNOBSERVABLE_OVERLAP"})

    visible = merge(visible)
    still = [x for x in merge(still) if x[1] - x[0] >= 5 - 1e-6]
    face_cover = merge(face_cover)
    merged_unrelated = []
    for label in sorted({event["objectLabel"] for event in unrelated}):
        for start, end in merge([[event["startSec"], event["endSec"]] for event in unrelated if event["objectLabel"] == label]):
            reason = next(event["reason"] for event in unrelated if event["objectLabel"] == label and event["startSec"] < end and event["endSec"] > start)
            merged_unrelated.append({"startSec": start, "endSec": end, "objectLabel": label, "reason": reason})
    unrelated = merged_unrelated
    unobservable = merge(unobservable + face_cover)
    off_target = subtract(off_target, unobservable)
    unique_stops = []
    for second in sorted(motion_stops):
        if not unique_stops or second - unique_stops[-1] > 0.5:
            unique_stops.append(second)
    minute_rows = []
    for minute in range(math.ceil(video_duration / 60)):
        start = minute * 60
        end = min(start + 60, video_duration)
        if end - start < 30:
            break
        count = sum(start <= second < end for second in unique_stops)
        allowance = math.floor(8 * (end - start) / 60 + 1e-9)
        minute_rows.append({"startSec": start, "endSec": round(end, 2), "handMotionCount": count, "allowedCount": allowance, "excessCount": max(0, count - allowance)})
    penalties = {"handMotionExcess": sum(x["excessCount"] for x in minute_rows), "handStillness": len(still), "faceOcclusion": len(face_cover), "unrelatedObjectTouch": len(unrelated)}
    raw_penalty = sum(penalties.values())
    gesture_score = max(30, 100 - raw_penalty)
    gaze_observable = video_duration - duration(unobservable)
    off_duration = duration(off_target)
    off_ratio = off_duration / gaze_observable if gaze_observable > 1e-6 else None
    gaze_score = None if off_ratio is None else max(0, min(100, math.floor((100 - 400 * max(0, off_ratio - 0.05)) + 0.5)))
    gaze_coverage = gaze_observable / video_duration
    hand_coverage = duration(visible) / video_duration
    warnings = ["60도는 보정된 각도 측정이 아닌 VLM의 큰 방향 전환 추정값입니다.", "초당 2프레임에서 완료 손동작과 짧은 가림이 누락될 수 있습니다.", "양손목 관찰률 자체도 사람 정답으로 검증되지 않았습니다.", "발표 관련성에는 음성 전사가 제공되지 않았습니다."]
    if gaze_coverage <= 0.5:
        warnings.append("얼굴 방향을 영상의 50% 이상 관찰할 수 없어 시선 점수 해석에 주의가 필요합니다.")
    if hand_coverage <= 0.5:
        warnings.append("양손목을 영상의 50% 이상 함께 관찰할 수 없어 제스처 점수 해석에 주의가 필요합니다. 화면 밖 자체는 감점하지 않았습니다.")
    if failures:
        warnings.append(f"모델 출력 실패 {len(failures)}구간은 행동 없음으로 간주하지 않았습니다. 점수는 관찰된 감점만 반영합니다.")
    if semantic_issues:
        warnings.append(f"모델 출력의 관찰 조건 충돌 {len(semantic_issues)}건은 집계에서 보수적으로 제외·조정했습니다.")
    if motion_stillness_conflicts:
        warnings.append(f"{len(motion_stillness_conflicts)}개 구간에서 손동작 종료가 같은 모델의 양손 정지 후보 안에 있어 제스처 사건의 일관성이 부족합니다. 임시 점수에는 두 출력을 모두 반영했습니다.")
    if raw_penalty >= 70:
        warnings.append(f"총 원감점 {raw_penalty}점이 70점 상한에 도달해 제스처는 최저 30점입니다. 상한을 넘는 행동 차이는 점수에 나타나지 않습니다.")
    return {"model": provider, "validWindows": len(manifest["windows"]) - len(failures), "totalWindows": len(manifest["windows"]), "failures": failures, "semanticIssues": semantic_issues, "motionStillnessConflicts": motion_stillness_conflicts, "inferenceSeconds": round(model_seconds, 2), "apiCostUsdUpperBound": round(cost, 6), "gesture": {"score": gesture_score, "rawDeduction": raw_penalty, "appliedDeduction": min(70, raw_penalty), "deductions": penalties, "handCoverageRatio": round(hand_coverage, 4), "handObservableSeconds": round(duration(visible), 2), "handStillnessEvents": still, "faceOcclusionEvents": face_cover, "unrelatedObjectTouchEvents": unrelated, "minuteMotionCounts": minute_rows}, "gaze": {"score": gaze_score, "observableSeconds": round(gaze_observable, 2), "unobservableSeconds": round(duration(unobservable), 2), "coverageRatio": round(gaze_coverage, 4), "offTargetSeconds": round(off_duration, 2), "offTargetRatio": None if off_ratio is None else round(off_ratio, 4), "offTargetIntervals": off_target}, "visualTwoItemMean": None if gaze_score is None else math.floor((gesture_score + gaze_score) / 2 + 0.5), "warnings": warnings}


def escape(value):
    return html.escape(str(value))


def clock(seconds):
    return f"{int(seconds // 60):02}:{seconds % 60:04.1f}"


def thumbnail(second):
    frame = ROOT / "frames" / f"{max(0, round(second * 2)):04}.jpg"
    if not frame.exists():
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(frame.read_bytes()).decode()


def report(manifest, scores):
    score_cards = ""
    evidence_blocks = ""
    for provider, title in PROVIDERS:
        result = scores[provider]
        gesture = result["gesture"]
        gaze = result["gaze"]
        top = f"<article class='model'><h3>{title}</h3><div class='score-grid'><div><strong>{gesture['score']}</strong><span>제스처 / 100</span></div><div><strong>{gaze['score'] if gaze['score'] is not None else '판단 불가'}</strong><span>시선 / 100</span></div><div><strong>{result['visualTwoItemMean'] if result['visualTwoItemMean'] is not None else '—'}</strong><span>시각 2항목 평균</span></div></div><p class='meta'>유효 JSON {result['validWindows']}/{result['totalWindows']}구간 · 손목 관찰률 {gesture['handCoverageRatio']*100:.1f}% · 시선 관찰률 {gaze['coverageRatio']*100:.1f}%</p></article>"
        score_cards += top
        deductions = gesture["deductions"]
        tags = [f"손짓 초과 {deductions['handMotionExcess']}회", f"5초 정지 {deductions['handStillness']}건", f"얼굴 가림 {deductions['faceOcclusion']}건", f"무관 물건 {deductions['unrelatedObjectTouch']}건"]
        tag_html = "".join(f"<span class='chip'>{escape(tag)}</span>" for tag in tags)
        gaze_percent = "판단 불가" if gaze["offTargetRatio"] is None else f"{gaze['offTargetRatio']*100:.1f}%"
        narrative = f"<p>이 모델은 관찰된 사건을 기준으로 제스처에서 {gesture['appliedDeduction']}점을 감점해 {gesture['score']}점을 냈습니다. 시선 방향을 판단할 수 있었던 {gaze['observableSeconds']:.1f}초 중 정면 외 방향 후보는 {gaze['offTargetSeconds']:.1f}초({gaze_percent})여서 시선 점수는 {gaze['score'] if gaze['score'] is not None else '판단 불가'}입니다. 시각 2항목 평균은 {result['visualTwoItemMean'] if result['visualTwoItemMean'] is not None else '계산 불가'}이며, 발화 속도·유창성이 없으므로 백엔드의 4항목 최종 총점은 아닙니다.</p>"
        advice = []
        if deductions["handMotionExcess"]:
            peak = max(gesture["minuteMotionCounts"], key=lambda row: row["excessCount"])
            advice.append(f"손동작 초과가 가장 큰 감점 원인입니다. 특히 {clock(peak['startSec'])}–{clock(peak['endSec'])}에 완료 손동작 {peak['handMotionCount']}회를 출력했으므로 그 구간에서 실제 손짓을 다시 확인하는 것이 우선입니다.")
        if deductions["handStillness"]:
            advice.append(f"양손 정지 후보가 5초 이상 이어진 사건 {deductions['handStillness']}건을 출력했습니다. 손목 가시성과 실제 움직임을 함께 확인한 뒤 피드백에 반영해야 합니다.")
        if deductions["faceOcclusion"]:
            advice.append(f"얼굴 가림 후보 {deductions['faceOcclusion']}건은 아래 근거 프레임에서 손·물건이 얼굴을 실제 가리는지 확인할 수 있습니다.")
        if gaze["score"] is not None and gaze["score"] < 100:
            advice.append("이 루브릭은 발표 화면을 향하는 시간도 정면 외 방향으로 셉니다. 발표 자료를 확인하는 행동과 청중을 보는 행동을 구분해 피드백을 해석하세요.")
        narrative += "<p><strong>개선 검토:</strong> " + escape(" ".join(advice) if advice else "이번 관찰값에서는 설정한 감점 사건이 확인되지 않았습니다. 관찰률과 모델 오류를 함께 확인하세요.") + "</p>"
        warning_html = "".join(f"<li>{escape(w)}</li>" for w in result["warnings"])
        event_list = [("양손 정지", x[0], x[1]) for x in gesture["handStillnessEvents"][:3]] + [("얼굴 가림", x[0], x[1]) for x in gesture["faceOcclusionEvents"][:3]] + [("정면 외 방향", x[0], x[1]) for x in gaze["offTargetIntervals"][:3]]
        samples = "".join(f"<figure><img src='{thumbnail(start)}' alt='{escape(kind)} {clock(start)}'><figcaption>{escape(kind)} · {clock(start)}–{clock(end)}</figcaption></figure>" for kind, start, end in event_list if thumbnail(start))
        minute_html = "".join("<tr><td>" + clock(x["startSec"]) + "–" + clock(x["endSec"]) + "</td><td>" + str(x["handMotionCount"]) + "</td><td>" + str(x["allowedCount"]) + "</td><td>" + str(x["excessCount"]) + "</td></tr>" for x in gesture["minuteMotionCounts"])
        details = f"<details><summary>분당 손동작과 감점 내역 보기</summary><div class='scroll'><table><tr><th>시간</th><th>완료 손동작</th><th>허용 횟수</th><th>초과 감점</th></tr>{minute_html}</table></div><pre>{escape(json.dumps(result, ensure_ascii=False, indent=2))}</pre></details>"
        evidence_blocks += f"<article class='analysis'><h3>{title}: 시각 평가</h3><div class='chips'>{tag_html}</div>{narrative}<div class='evidence'>{samples}</div><h4>해석 시 주의</h4><ul>{warning_html}</ul>{details}</article>"
    old_qwen = scores["qwen"]
    revised_qwen = scores["qwen_criteria"]
    gpt = scores["openai"]
    comparison = (
        f"결론: 수정 Qwen의 양손목 관찰률은 {old_qwen['gesture']['handCoverageRatio']*100:.1f}%에서 {revised_qwen['gesture']['handCoverageRatio']*100:.1f}%로 늘어 사용자가 확인한 '대부분 손목이 보임'에 더 가깝습니다(GPT {gpt['gesture']['handCoverageRatio']*100:.1f}%). "
        f"정면 외 방향 후보 비율도 기존 {old_qwen['gaze']['offTargetRatio']*100:.1f}%에서 수정 {revised_qwen['gaze']['offTargetRatio']*100:.1f}%로 바뀌어 GPT {gpt['gaze']['offTargetRatio']*100:.1f}%와 비슷합니다. "
        f"하지만 수정 Qwen의 5초 이상 양손 정지 {revised_qwen['gesture']['deductions']['handStillness']}건은 GPT {gpt['gesture']['deductions']['handStillness']}건보다 훨씬 많고, 얼굴 가림은 {revised_qwen['gesture']['deductions']['faceOcclusion']}건으로 GPT의 후보 {gpt['gesture']['deductions']['faceOcclusion']}건을 여전히 놓칩니다. "
        f"유효 JSON은 {revised_qwen['validWindows']}/75구간이며 정지·손동작 충돌이 {len(revised_qwen['motionStillnessConflicts'])}구간 있습니다. 따라서 손목 관찰 누락은 개선됐지만 제스처 결과를 GPT 대신 채택하기에는 근거가 부족합니다. 사람의 사건 정답이 없어 GPT의 횟수와 점수도 정확하다고 확정할 수 없습니다."
    )
    summary_rows = "".join(
        f"<tr><th>{escape(title)}</th><td>{scores[provider]['validWindows']}/{scores[provider]['totalWindows']}</td><td>{len(scores[provider]['semanticIssues'])}</td><td>{len(scores[provider]['motionStillnessConflicts'])}</td><td>{scores[provider]['gesture']['handCoverageRatio']*100:.1f}%</td><td>{sum(row['handMotionCount'] for row in scores[provider]['gesture']['minuteMotionCounts'])}</td><td>{format(scores[provider]['gaze']['offTargetRatio']*100, '.1f')+'%' if scores[provider]['gaze']['offTargetRatio'] is not None else '—'}</td><td>{scores[provider]['gesture']['score']}</td><td>{scores[provider]['gaze']['score'] if scores[provider]['gaze']['score'] is not None else '—'}</td><td>{scores[provider]['apiCostUsdUpperBound']:.4f}</td></tr>"
        for provider, title in PROVIDERS
    )
    deduction_labels = {"handMotionExcess": "분당 손짓 초과", "handStillness": "5초 이상 양손 정지", "faceOcclusion": "손·물건의 얼굴 가림", "unrelatedObjectTouch": "무관 물건 접촉"}
    deduction_rows = "".join(f"<tr><th>{label}</th>" + "".join(f"<td>−{scores[provider]['gesture']['deductions'][key]}점</td>" for provider, _ in PROVIDERS) + "</tr>" for key, label in deduction_labels.items())
    deduction_headers = "".join(f"<th>{escape(title)}</th>" for _, title in PROVIDERS)
    checked_scenes = [
        (170, "손목 관찰 차이", "이 프레임에서는 발표자의 양손목 위치를 확인할 수 있습니다. 160–180초에서 기존 Qwen은 0초, 수정 Qwen은 약 17초, GPT는 20초를 양손목 관찰 가능으로 기록했습니다. 한 프레임으로 구간 전체의 정답을 확정하지는 않습니다."),
        (233, "컵 접촉 후보 검토", "수정 Qwen은 232–235초에 컵 접촉을 출력했습니다. 이 프레임에서는 손끝이 화면 밖에 있어 실제 접촉을 확인하기 어렵습니다. 해당 감점을 확정하면 오검출 위험이 있습니다."),
        (365, "수정 Qwen의 시선 후보 회복", "고개가 아래·발표 화면 쪽을 향하는 모습이 보입니다. GPT와 수정 Qwen은 이 구간을 정면 외 방향으로 표시했고 기존 Qwen은 놓쳤습니다."),
        (867, "비정면 구간 경계 차이", "고개를 숙이는 모습이 보입니다. 기존 Qwen은 866–871초, 수정 Qwen은 866초 일부와 870–872초, GPT는 868.5–872.5초를 정면 외 방향 후보로 기록해 시간 경계가 서로 다릅니다."),
        (159, "GPT만 얼굴 가림 후보", "손이 이마 일부에 겹칩니다. GPT는 짧은 얼굴 가림을 출력했고 기존·수정 Qwen은 출력하지 않았습니다."),
    ]
    checked_html = "".join(f"<figure><img src='{thumbnail(second)}' alt='{clock(second)} 장면'><figcaption><strong>{escape(title)} · {clock(second)}</strong><br>{escape(description)}</figcaption></figure>" for second, title, description in checked_scenes)
    source = escape(Path(manifest["sourcePath"]).name)
    page = f"""<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>발표 영상 시각 평가 · 세 모델 비교</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f2f6fa;color:#17324a;font:16px/1.65 system-ui,-apple-system,sans-serif}}main{{max-width:1180px;margin:auto;padding:24px}}header{{padding:32px;background:#173b5f;color:white;border-radius:18px}}h1,h2,h3{{line-height:1.28}}h1{{margin:0 0 12px}}section{{background:white;padding:24px;margin:20px 0;border-radius:16px;box-shadow:0 2px 14px #1232}}.lead{{font-size:18px}}.cards{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}.model{{border:1px solid #d8e5ef;padding:20px;border-radius:14px}}.score-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}.score-grid div{{background:#eaf4ff;padding:12px;border-radius:12px;text-align:center}}.score-grid strong{{font-size:32px;display:block;color:#064d87}}.score-grid span{{font-size:12px}}.meta{{font-size:14px}}.chip{{display:inline-block;border:1px solid #66a5d2;color:#075888;border-radius:999px;padding:4px 12px;margin:0 7px 8px 0;background:#f5fbff}}.analysis{{border-top:1px solid #d6e3ef;padding-top:22px;margin-top:22px}}.evidence{{display:flex;gap:10px;overflow:auto}}figure{{margin:4px 0;min-width:210px;width:24%}}figure img{{width:100%;border-radius:8px}}figcaption{{font-size:13px}}.notice{{background:#fff4db;border-left:4px solid #dc9b17;padding:16px}}table{{border-collapse:collapse;width:100%;min-width:650px}}td,th{{border:1px solid #d4e1eb;padding:8px;text-align:left}}th{{background:#edf4fa}}.scroll{{overflow:auto}}pre{{white-space:pre-wrap;background:#132c43;color:#e9f3fa;padding:16px;border-radius:10px;font-size:12px;overflow-wrap:anywhere}}summary{{cursor:pointer;font-weight:bold;padding:12px}}a{{color:#006cae}}@media(max-width:720px){{.cards{{grid-template-columns:1fr}}main{{padding:12px}}section{{padding:16px}}}}
</style></head><body><main><header><h1>발표 영상 시각 평가</h1><p class='lead'>GPT · 기존 Qwen · 기준 명시 Qwen: 같은 영상과 프레임으로 관찰 JSON 비교</p><p>{source} · 전체 {clock(manifest['durationSeconds'])} · 2프레임/초 · 20초 구간 {len(manifest['windows'])}개</p></header>
<section><h2>결과 먼저</h2><p>{comparison}</p><div class='scroll'><table><tr><th>모델</th><th>유효 JSON</th><th>관찰 모순</th><th>정지·손동작 충돌 구간</th><th>양손목 관찰률</th><th>완료 손동작</th><th>정면 외 비율</th><th>제스처</th><th>시선</th><th>API 비용 USD</th></tr>{summary_rows}</table></div><p class='meta'>관찰 모순은 양손목이 보이지 않는데 정지로 기록하거나 시선 이탈과 관찰 불가가 겹친 경우입니다. 정지·손동작 충돌은 정지 후보 내부에서 손동작이 끝났다고 동시에 기록한 구간 수입니다.</p><div class='cards'>{score_cards}</div><h3>제스처 감점 내역</h3><div class='scroll'><table><tr><th>행동</th>{deduction_headers}</tr>{deduction_rows}</table></div><p class='notice'>여기의 점수는 사용자가 정한 임시 시각 루브릭을 모델 관찰값에 적용한 실험 결과입니다. 정확한 60° 각도와 실제 눈맞춤을 측정한 점수가 아니며, 사람 정답과 대조하지 않았습니다. 전체 발표의 공식 4항목 총점으로 사용하지 마세요.</p></section>
<section><h2>이번에 바꾼 것</h2><p>기준 명시 Qwen은 모델 가중치·프레임·2fps 샘플링·20초 분할·JSON 필드·채점 코드를 기존 Qwen과 동일하게 유지했습니다. 프롬프트에서 손목을 손과 팔의 접합부로 근사해 찾고, 짧은 관찰 구간도 기록하도록 지시했습니다. 손의 이동 후 정지, 실제 얼굴 가림, 화면·위·아래 방향, 얼굴 가림 시 시선 관찰 불가를 각각 명시했습니다. GPT와 기존 Qwen에는 기존 공통 프롬프트를 사용했습니다.</p><p>이 영상의 기존 실패 구간을 보고 수정한 프롬프트이므로 수정 Qwen 수치는 탐색 결과입니다. 새 촬영 영상의 사람 정답으로 누락과 오검출을 함께 평가해야 성능 향상을 주장할 수 있습니다.</p><details><summary>수정 Qwen 프롬프트 전문</summary><pre>{escape(QWEN_CRITERIA_PROMPT)}</pre></details></section>
<section><h2>점수 계산 기준</h2><div class='scroll'><table><tr><th>항목</th><th>실험 계산</th><th>주의</th></tr><tr><td>제스처</td><td>100 − 분당 8회 초과 손동작 횟수 − 5초 이상 양손 정지 사건 수 − 실제 얼굴 가림 사건 수 − 무관 물건 접촉 사건 수. 각 1점, 최대 70점 감점해 최저 30점.</td><td>연속 사건은 한 건으로 묶고 겹친 얼굴 가림은 한 번만 셈. 마지막 46초는 길이에 비례해 허용 손동작 6회로 계산. 보이지 않는 시간 자체는 감점하지 않음.</td></tr><tr><td>시선</td><td>정면 외 방향 후보 시간 ÷ 얼굴 방향 관찰 가능 시간. 이 비율 5% 이하면 100점, 5~30%는 1%포인트당 4점 감점, 30% 이상은 0점.</td><td>큰 좌우 회전·아래·위·발표 화면 방향을 모델이 추정. 가림·미검출 시간은 분모에서 제외. 60°는 미보정 근삿값.</td></tr><tr><td>관찰 부족</td><td>양손목 또는 얼굴 방향을 영상의 50% 이하 시간만 관찰하면 안내문 표시.</td><td>관찰 불가는 0점이나 100점의 증거가 아님. 모델 출력 실패 구간도 미관찰로 처리.</td></tr><tr><td>시각 2항목 평균</td><td>제스처와 시선 점수의 동일 가중 평균, .5는 올림.</td><td>발화 속도와 유창성 점수가 빠진 참고값으로, 백엔드 4항목 총점과 다름.</td></tr></table></div></section>
<section><h2>불일치 장면 직접 확인</h2><p>모델 출력이 달랐던 장면에서 선택한 표본입니다. 출력 확인 후 고른 사례이며 전 구간의 사람 정답이나 정확도 통계가 아닙니다.</p><div class='evidence'>{checked_html}</div></section>
<section><h2>모델별 근거와 평가 문장</h2><p>제공된 예시 이미지의 배치와 읽기 쉬운 문장 형식을 참고했습니다. 태도·성격 같은 특성은 영상만으로 단정하지 않고 관찰된 시간과 사건만 설명합니다.</p>{evidence_blocks}</section>
<section><h2>재현 자료와 한계</h2><p><a href='aggregate.json'>전체 점수 JSON</a> · <a href='manifest.json'>프레임·기존 프롬프트·점수 설정</a></p><p>원출력은 이 폴더의 <code>openai_v3_*.json</code>, <code>qwen_v3_*.json</code>, <code>qwen_criteria_v3_*.json</code>에 저장했습니다. 모든 결과의 JSON 구조를 같은 검증 함수로 다시 검사했고 실패 구간은 관찰 불가로 처리했습니다. 수정 Qwen의 출력 한도에 걸린 첫 응답은 따로 보관하고 같은 프롬프트로 한도를 늘려 다시 실행했습니다. 이 영상은 프롬프트 선택과 평가에 함께 사용됐으므로 독립 일반화 평가가 아닙니다.</p><p>영상은 한 사례이며 사람이 전 구간을 라벨링하지 않았습니다. 초당 2프레임은 빠른 손짓·짧은 가림을 놓칠 수 있습니다. 영상 대부분의 손목과 손짓이 보인다는 사람의 확인은 정성적 대조이며 정밀한 관찰률 정답은 아닙니다. Claude API는 키 인증이 두 번 모두 401로 거절되어 사용자 요청대로 비교에서 제외했습니다.</p><details><summary>GPT·기존 Qwen 공통 관찰 프롬프트</summary><pre>{escape(PROMPT)}</pre></details><p>GPT 비용은 반환 토큰에 <a href='https://developers.openai.com/api/docs/models/gpt-6.1-sol'>OpenAI 공식 단가</a>를 적용한 계산값입니다. 실제 청구서가 아니며 이전 시험 비용은 표에 포함하지 않았습니다. Qwen에는 API 호출 비용이 없고 로컬 실행 시간·전력은 별도입니다. 이번 로컬 실행은 macOS 26.1, MLX 0.31.2, mlx-vlm 0.7.12에서 진행했습니다. MLX 0.32.4는 이 환경에서 Metal 커널 오류가 발생해 실험용 가상환경만 이전 버전으로 바꿨습니다. 코드를 Git에 올리지 않았습니다.</p></section></main></body></html>"""
    (ROOT / "report.html").write_text(page)


def main():
    manifest = json.loads((ROOT / "manifest.json").read_text())
    scores = {provider: score_model(provider, manifest) for provider, _ in PROVIDERS}
    motion_counts = {provider: sum(row["handMotionCount"] for row in result["gesture"]["minuteMotionCounts"]) for provider, result in scores.items()}
    if min(motion_counts.values()) * 2 < max(motion_counts.values()):
        for result in scores.values():
            result["warnings"].append("동일 영상에서 모델별 완료 손동작 수가 크게 다릅니다. 사람 정답 없이 과다·과소 계수 여부를 확정할 수 없습니다.")
    assert merge([[0, 1], [1, 2]]) == [[0, 2]]
    assert subtract([[0, 10]], [[3, 5]]) == [[0, 3], [5, 10]]
    assert all(result["gesture"]["score"] >= 30 for result in scores.values())
    (ROOT / "aggregate.json").write_text(json.dumps({"sourcePath": manifest["sourcePath"], "durationSeconds": manifest["durationSeconds"], "evaluationType": "REUSED_SINGLE_UNLABELLED_VIDEO_PROMPT_SELECTION", "isScoringReady": False, "notEvaluatedItems": ["SPEECH_RATE", "FLUENCY"], "promptVariants": {"openai": "baseline-v3", "qwen": "baseline-v3", "qwen_criteria": "criteria-explicit-v1"}, "scores": scores}, ensure_ascii=False, indent=2))
    report(manifest, scores)
    for provider, value in scores.items():
        print(provider, "valid", value["validWindows"], "/", value["totalWindows"], "gesture", value["gesture"]["score"], "gaze", value["gaze"]["score"], "cost", value["apiCostUsdUpperBound"])


if __name__ == "__main__":
    main()
