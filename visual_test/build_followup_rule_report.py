"""Build the four-stage Vision follow-up experiment report."""

import base64
import html
import json
from pathlib import Path


ROOT = Path("visual_test/results/followup_rule_evaluation")
TRIAL = json.loads((ROOT / "trial_metrics.json").read_text())
LABELS = json.loads((ROOT / "holdout_labels.json").read_text())


def image(path):
    data = base64.b64encode(Path(path).read_bytes()).decode()
    return f"data:image/jpeg;base64,{data}"


def intervals(events):
    return ", ".join(f"{event['startSec']:.1f}–{event['endSec']:.1f}초" for event in events) or "없음"


def code(value):
    return html.escape(json.dumps(value, ensure_ascii=False, indent=2))


old = TRIAL["example_development"]
gaze = TRIAL["gaze_development"]
dance = TRIAL["dance_hand_lesson"]
cover = TRIAL["facepalm"]
stage = TRIAL["malaysia_presentation"]
close = TRIAL["ian_presentation"]
signing = TRIAL["signing_stress"]
trial_key = "threshold_0.12_smooth_True_gap_True"
dance_event = dance["stillnessTrials"][trial_key]["events"][0]
old_event = old["stillnessTrials"][trial_key]["events"][0]
face_label = next(item for item in LABELS["labels"] if item["clipId"] == "facepalm")
face_positive = [
    i for i in range(cover["frames"])
    if any(start <= i * LABELS["samplingSeconds"] < end for start, end in face_label["faceCoverPositiveIntervals"])
]
face_negative = [
    i for i in range(cover["frames"])
    if any(start <= i * LABELS["samplingSeconds"] < end for start, end in face_label["faceCoverNegativeIntervals"])
]
assert face_positive and max(face_positive) < cover["frames"]
assert face_negative and not set(face_positive) & set(face_negative)
assert all(len(flags) == cover["frames"] for flags in cover["_faceCoverFlags"].values())
face_recall = {
    name: sum(flags[i] for i in face_positive)
    for name, flags in cover["_faceCoverFlags"].items()
}
face_false_positives = {
    name: sum(flags[i] for i in face_negative)
    for name, flags in cover["_faceCoverFlags"].items()
}
summary = {
    "developmentStillnessKnownLabelSeconds": [21, 27],
    "developmentStillnessBaselineEvents": old["baseline"]["handStillEvents"],
    "developmentStillnessRelaxedEvent": old_event,
    "holdoutDanceStillnessCoarseLabelSeconds": [43, 51],
    "holdoutDanceStillnessBaselineEvents": dance["baseline"]["handStillEvents"],
    "holdoutDanceStillnessRelaxedEvent": dance_event,
    "holdoutDanceMotionCoarseMinimumTransitions": 11,
    "holdoutDanceCompletedMotionBouts": dance["motionTrial"]["completedCount"],
    "signingStressMovingSeconds": signing["motionTrial"]["movingFrameSeconds"],
    "signingStressCompletedMotionBouts": signing["motionTrial"]["completedCount"],
    "signingStressUnfinishedBouts": signing["motionTrial"]["unfinishedCount"],
    "developmentFaceCoverBaseline": gaze["baseline"]["handFaceEvents"],
    "developmentFaceCoverTrackedOneSecond": gaze["faceTrackingTrials"]["shortOneSecond"],
    "developmentFaceCoverTrackedSevenSecondsExploratory": gaze["faceTrackingTrials"]["longSevenSecondsExploratoryOnly"],
    "holdoutFacepalmPositiveFrames": len(face_positive),
    "holdoutFacepalmDetectedPositiveFrames": face_recall,
    "holdoutFacepalmNegativeFrames": len(face_negative),
    "holdoutFacepalmFalsePositiveFrames": face_false_positives,
    "holdoutPresentationBodyFrames": stage["bodyFrames"],
    "holdoutPresentationFaceFrames": stage["faceFrames"],
    "holdoutPresentationHandFrames": stage["handFrames"],
    "holdoutCloseupHandObservableSeconds": close["baseline"]["handObservableSeconds"],
    "scoringReady": False,
}
(ROOT / "report_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))

pose_img = image(ROOT / "stillness_pose_overlay.jpg")
dance_img = image(ROOT / "dance_39_59_contact.jpg")
face_img = image(ROOT / "facepalm_contact.jpg")
stage_img = image(ROOT / "malaysia_wrong_person.jpg")
html_text = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Vision 후속 4단계 실험 보고서</title><style>
body{{margin:0;background:#f3f6fb;color:#1b2940;font:16px/1.65 system-ui,sans-serif;overflow-wrap:anywhere}}
main{{max-width:1120px;margin:auto;padding:24px}}h1,h2{{line-height:1.3}}h1{{font-size:34px}}h2{{font-size:25px;margin-top:0}}
.hero{{background:#152b46;color:white;border-radius:20px;padding:32px}}.hero p{{font-size:19px}}section{{background:white;border-radius:16px;padding:26px;margin:20px 0}}
.no{{color:#af332d;font-weight:700}}.some{{color:#9e6610;font-weight:700}}.yes{{color:#126945;font-weight:700}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #d7e0eb;padding:11px;text-align:left;vertical-align:top}}th{{background:#edf3fa}}.scroll{{overflow:auto}}
.note{{padding:14px;border-left:5px solid #c47922;background:#fff7e9}}.bad{{padding:14px;border-left:5px solid #c24a43;background:#fff1ef}}
img{{max-width:100%;height:auto;border-radius:10px}}figcaption{{font-size:13px;color:#52637b}}figure{{margin:20px 0}}code,pre{{font-family:ui-monospace,SFMono-Regular,monospace}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#14263d;color:#e8f1fd;border-radius:10px;padding:18px;font-size:13px}}a{{color:#0b5da3}}.hero a{{color:#a8d9ff}}
</style></head><body><main><div class="hero"><h1>Vision 후속 4단계 실험</h1><p><strong>결론 먼저:</strong> 5초 정지 규칙을 완화하면 알려진 누락과 새 손동작 영상의 정지 한 구간을 잡지만, 다른 행동에도 정지 사건이 늘어 채택은 보류한다. 얼굴 추적은 가림 후보를 늘리지만 새 가림 영상에서도 1초 추적만으로는 대부분을 놓친다. 공개 발표 영상에서는 관객을 발표자로 선택해 시선·손 결과가 거의 생성되지 않았다.</p><p>이 보고서는 <strong>시험 코드의 비교 결과</strong>다. 백엔드 모델·정식 JSON·API는 변경하지 않았고, 점수도 계산하지 않았다.</p></div>
<section><h2>네 단계 결과</h2><div class="scroll"><table><tr><th>단계</th><th>실측</th><th>판정</th></tr>
<tr><td>① 21–27초 좌표</td><td>23.8초 왼쪽 손목 신뢰도 0.483&lt;0.5로 이력 초기화. 25초 이후 어깨 대비 손목 변화가 0.08–0.135로 기존 기준 0.04를 초과.</td><td class="yes">누락 원인 확인. 실제 미세 움직임과 좌표 오차의 비율은 미확정.</td></tr>
<tr><td>② 정지·손짓 규칙</td><td>기존 정지 사건 0건 → 완화 시험에서 21.2–27.0초. 새 손동작 영상에서도 기존 0건 → 42.4–48.4초 한 사건. 새 영상의 사람이 표시한 손목 유지 구간은 대략 43–51초.</td><td class="some">후보는 개선되지만 새 영상의 뒤 2.6초 누락·다른 사건의 오검출 가능성 남음.</td></tr>
<tr><td>③ 얼굴 소실 추적</td><td>기존 영상 22.4–26.0초 후보 → 1초 추적을 더하면 26.2–27.4초 후보. 별도 얼굴 가림 영상에서 기존 0/8표본, 1초 추적 2/8표본 포착.</td><td class="some">일부 회복. 7초 연장 추적은 개발 영상에서 33.4초까지 따라가지만 위치 오차 위험으로 채택 불가.</td></tr>
<tr><td>④ 새 영상 사람 정답 대조</td><td>실제 공개 발표 60초 표본: 몸 5/300, 얼굴 0/300, 손 0/300. 손동작 시범: 양손 판정 가능 53/60초. 가까운 발표 얼굴 영상은 손 판정 가능 0초.</td><td class="no">일반화 입증 실패. 새 발표 영상의 관객 선택 문제가 먼저 해결돼야 함.</td></tr></table></div></section>
<section><h2>① 손목 좌표와 실제 화면</h2><p>사용자가 지정한 <strong>예시.mov 21–27초</strong>는 같은 영상으로 여러 번 시험한 개발 구간이다. 손은 주로 턱 앞에 머문다. 23.8초 한 손목의 신뢰도가 0.483으로 기준 0.5 아래라 과거 1초 이력이 지워졌고, 그 다음 1초를 다시 모으는 동안 판정이 비었다. 24.8–26.0초에는 몸통과 머리도 움직이며 어깨 대비 손목 좌표가 달라진다. 화면과 좌표만으로 실제 손 움직임과 관절 추정 흔들림을 완전히 분해할 수 없다.</p><figure><img src="{pose_img}" alt="21~27초의 손목과 어깨 관절 좌표 및 신뢰도를 겹친 장면"><figcaption>초록 관절은 신뢰도 0.5 이상, 빨강 관절은 그 미만. 23.8초 빨간 손목이 시간 이력을 끊는다. 사용자 제공 영상.</figcaption></figure><p>기존 JSON의 <code>handStillSeconds=0</code>은 5초 사건 합계가 0이라는 뜻이다. 짧게 정지한 모든 프레임이 0이라는 뜻이 아니다.</p></section>
<section><h2>② 규칙 비교: 숫자가 좋아 보여도 사건은 다르다</h2><p>시험 규칙은 5FPS에서 6개 손목 표본을 이용한다. 변경 후보는 <strong>3점 중앙값 평활화, 한 프레임(0.2초) 관찰 불가 허용, 이동 임계값 0.04/0.08/0.12 비교</strong>다. 관찰 불가 프레임은 정지로 확정하지 않고 사건 안의 미관찰 시간으로 별도 계산했다.</p><div class="scroll"><table><tr><th>규칙</th><th>기존 21–27초</th><th>새 손동작 시범의 43–51초</th></tr>
<tr><td>현재 백엔드 0.04</td><td>사건 없음</td><td>사건 없음</td></tr>
<tr><td>0.08 + 평활화 + 0.2초 공백</td><td>사건 없음</td><td>42.4–48.4초</td></tr>
<tr><td>0.12 + 평활화 + 0.2초 공백</td><td>{intervals([old_event])}; 안에 관찰 불가 0.2초</td><td>{intervals([dance_event])}; 사람 표시 구간 끝은 약 51초</td></tr></table></div>
<p class="note">0.12는 개발 영상의 정답을 회복했지만 다른 개발 영상 27.4–33.2초에도 정지 사건을 새로 만들었다. 그 장면은 손으로 얼굴을 가리는 행동과 겹친다. 두 감점의 중복 처리도 정해지지 않았으며, 이 한두 영상만으로 임계값 0.12가 더 정확하다고 말할 수 없다.</p>
<figure><img src="{dance_img}" alt="새 손동작 시범 영상의 39~58초 1초 간격 장면"><figcaption>대략 43–51초에는 손목 위치가 유지되고 손가락 모양은 변한다. 이 시범은 발표가 아니므로 발표 점수 검증 자료는 아니다. 출처: <a href="https://commons.wikimedia.org/wiki/File:Double_hand_gestures_lesson_in_Bharatanatyam_dance_(2019).webm">ANTARA BHADRA - SRADDHANJALI, CC BY 3.0</a>.</figcaption></figure>
<h3>손짓 횟수</h3><p>새 시범의 1초 간격 장면에서 사람이 표시한 <strong>명확한 손 위치 전환은 최소 11개</strong>다. 기존 시험용 계수는 11회, 새 시작·종료 상태 표시 코드는 완료 12회·미완료 1회를 냈다. 그러나 기존 사건 <code>16.6–27.4초</code>와 <code>28.0–39.6초</code>는 각각 여러 위치 전환을 하나로 합쳤고, <code>44.4–46.0초</code>는 유지 자세 안에서 잡혔다. <strong>총횟수가 비슷한 것은 사건별 정확도의 증거가 아니다.</strong></p><p>이전에 사용한 공개 수어 60초 영상에서는 손 움직임이 55.4초 감지됐지만 완료 0회·미완료 4구간이었다. 0회를 ‘손짓 없음’으로 보내지 않고 <code>OBSERVATION_LOST</code>/<code>VIDEO_END</code>처럼 종료 이유를 함께 보내는 방향은 유용하다. 분당 8회 초과의 발표용 정확도는 미검증이다.</p></section>
<section><h2>③ 얼굴 소실 후 후보 추적</h2><p>기존 가림 영상에서 <code>HAND_FACE_OVERLAP_CANDIDATE</code>는 22.4–26.0초였다. 마지막 얼굴 박스를 몸의 어깨 중심·너비 변화에 맞춰 1초까지만 예측한 시험은 26.2–27.4초 후보를 추가했다. 7초까지 늘리면 26.2–33.4초가 나오지만, 얼굴을 7초간 보지 못한 채 박스를 예측하므로 실제 가림 확정 근거가 아니다.</p><p>새 사람의 짧은 얼굴 가림 영상에서 사람이 표시한 1.8–3.4초의 8개 양성 표본 중 현재 사건은 <strong>0개</strong>, 1초 추적 후보는 <strong>{face_recall['shortOneSecond']}개</strong>, 7초 탐색 추적은 <strong>{face_recall['longSevenSeconds']}개</strong>를 포함했다. 명확한 비가림 0–1.4초의 7개 음성 표본에서 잘못 잡은 표본은 각각 <strong>{face_false_positives['baseline']}/{len(face_negative)}, {face_false_positives['shortOneSecond']}/{len(face_negative)}, {face_false_positives['longSevenSeconds']}/{len(face_negative)}</strong>이었다. 1.4–1.8초 전환 구간은 정답 계산에서 제외했다. 손이 얼굴을 가리는 동안 시선은 계속 관찰 불가로 둔다.</p><figure><img src="{face_img}" alt="새 사람의 손으로 얼굴 가리기 장면 0.2초 표본"><figcaption>Facepalm 영상: 1.8초부터 손이 얼굴을 가린다. 출처: <a href="https://commons.wikimedia.org/wiki/File:Facepalm.webm">Rattyexalt, CC BY-SA 4.0</a>. 발표 영상은 아니며 시각적 양성 대조군이다.</figcaption></figure><p class="note">손동작 시범의 32.6–34.4초에도 기존 모델이 손·얼굴 겹침을 냈다. 최초 1초 간격 검토에서는 가림이 아니라고 적었으나, <strong>모델 결과를 본 뒤</strong> 고해상도 장면에서 손이 입을 일부 가리는 것을 확인해 라벨을 수정했다. 이 사례는 독립 정확도 수치에 넣지 않았다.</p></section>
<section><h2>④ 새 사람·촬영 조건에서 드러난 문제</h2><p>공개 발표 영상은 <a href="https://commons.wikimedia.org/wiki/File:Wikimedia_Malaysia_presentation_at_17th_Asia-Pacific_RCE_Regional_Meeting_in_Zhejiang,_China.webm">Lee Woo Jin의 CC0 촬영 영상</a> 첫 60초다. 발표자와 앞줄 관객이 함께 찍혔다. 300개 표본 중 현재 코드가 몸을 반환한 것은 5개뿐이고, 그 5개도 모두 <strong>발표자가 아닌 앞줄 관객</strong>이었다. 얼굴·손 출력은 각각 0개다.</p><figure><img src="{stage_img}" alt="공개 발표 영상에서 관객을 발표자로 잘못 선택한 첫 장면"><figcaption>빨간 박스는 현재 코드가 선택한 사람. 실제 발표자는 화면 중앙 뒤쪽에 있다. 원본: Lee Woo Jin, CC0.</figcaption></figure><p class="bad">이 영상의 빈 제스처·시선 사건은 ‘행동이 없었다’는 뜻이 아니다. 발표자 추적에 실패해 <strong>관찰 자체가 성립하지 않았다</strong>. 첫 프레임에서 YOLO pose는 발표자를 두 번째 사람 박스로 검출했지만, 현재 코드는 큰 사람을 우선해 관객을 골랐다. 다른 프레임은 다중 인물 모호성 때문에 몸을 반환하지 않았다.</p><p>또 다른 새 사람의 59초 얼굴 중심 발표 영상에서는 얼굴 295/295표본이 보였으나 손 정지 판정 가능 시간은 0초였다. 이는 손이 화면 밖인 촬영 조건에서는 손 점수 판단을 보류해야 한다는 사례다. 출처: <a href="https://commons.wikimedia.org/wiki/File:Ian_Wachtmeister_presentation_2014.webm">Albin Olsson, CC BY-SA 3.0</a>.</p></section>
<section><h2>결정 및 다음 검증</h2><ol><li><strong>백엔드 규칙 채택 보류:</strong> 0.12 완화, 1초 얼굴 추적은 시험 후보로만 유지한다. 보이는 영상에서 일부 회복됐지만 발표 영상의 오검출률과 사건 경계가 확인되지 않았다.</li><li><strong>발표자 선택부터 고침:</strong> 가장 큰 사람 대신 발표자 지정·초기 ROI·시간 추적 중 한 방법을 시험해야 한다. 이 공개 발표 영상은 변경 전 기준선으로 기록하고, 변경 뒤 평가에는 별도 공개 영상을 쓴다.</li><li><strong>정답 자료:</strong> 새 고정 카메라 발표 영상에서 손목 정지 시작·끝, 손짓 이동→정지 사건, 실제 얼굴 가림과 비가림, 화면 밖 구간을 사람이 0.2초 단위로 표시한다. 이번 단일 검토자는 독립된 다중 평가자가 아니다.</li><li><strong>채택 기준:</strong> 새 영상에서 누락과 잘못 잡은 사건을 함께 세고, 관찰 가능 시간·사건 시작/끝 오차·CPU 처리시간을 보고한다. 한 영상의 총횟수 일치만으로 분당 8회 규칙을 채택하지 않는다.</li></ol>
<p>실험 파일: <a href="trial_metrics.json">전체 시험 집계 JSON</a>, <a href="report_summary.json">핵심 결과 JSON</a>, <a href="holdout_labels.json">사람 장면 검토 라벨과 수정 기록</a>. 현재 출력의 <code>isScoringReady</code>는 계속 <code>false</code>다.</p><h3>핵심 결과 JSON</h3><pre>{code(summary)}</pre></section>
</main></body></html>'''
(ROOT / "report.html").write_text(html_text)
print(ROOT / "report.html")
