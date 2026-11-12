"""Build a self-contained review of the user's staged negative-behavior video."""

import base64
import html
import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent / "results/negative_behavior_sample"
RESULT = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
FRAMES = json.loads((OUT / "frame_observations.json").read_text(encoding="utf-8"))
RUNTIME = json.loads((OUT / "runtime.json").read_text(encoding="utf-8"))


def image(second):
    data = (OUT / "frames" / f"frame_{second:02d}.jpg").read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(data).decode()


def scene(second, title, expected, actual, verdict):
    return f"""<article class="scene">
      <img src="{image(second)}" alt="{second}초 모델 검출 결과">
      <div><span class="time">{second}초</span><h3>{html.escape(title)}</h3>
      <p><b>기대:</b> {html.escape(expected)}</p>
      <p><b>실제:</b> {html.escape(actual)}</p>
      <p class="verdict"><b>판단:</b> {html.escape(verdict)}</p></div>
    </article>"""


def window(start, end):
    frames = [frame for frame in FRAMES if start <= frame["second"] < end]
    labels = Counter(obj["label"] for frame in frames for obj in frame["objects"])
    return {
        "count": len(frames),
        "faces": sum(frame["hasAssociatedFace"] for frame in frames),
        "frontal": sum(frame["isCameraFacing"] is True for frame in frames),
        "gaze_observable": sum(frame["isCameraFacing"] is not None for frame in frames),
        "both_wrists": sum(
            all(confidence is not None and confidence >= .5 for confidence in frame["wristConfidence"])
            for frame in frames
        ),
        "labels": labels,
    }


hand = window(0, 10)
phone = window(11, 17)
still = window(22, 26)
cup = window(28, 32)
small = window(34, 40)
gaze = RESULT["vision"]["gaze"]
events = RESULT["vision"]["candidateEvents"]
raw_json = html.escape(json.dumps(RESULT, ensure_ascii=False, indent=2))

scenes = "".join(
    [
        scene(4, "손이 얼굴을 가림", "손 가림 후보와 이 구간의 시선 관찰 불가", "얼굴 박스·5점은 계속 출력, 손 가림 사건 없음", "실패: 손 영역을 측정하지 못하고 얼굴 방향을 계속 판정"),
        scene(8, "손 가림이 다시 나타남", "손 가림 후보", "손은 보이지만 손목 신뢰도 낮음; 후보 0건", "실패: 손목만으로 실제 가림을 찾지 못함"),
        scene(12, "휴대폰으로 얼굴 가림", "휴대폰 인식과 물건·얼굴 겹침 후보", "cell phone 출력; 12.0–12.6초에는 얼굴 미연결", "부분 성공: 물건은 인식, 사건은 검출 단절로 둘로 나뉨"),
        scene(14, "휴대폰 가림 지속", "겹침 후보를 유지하고 가려진 얼굴의 시선은 미평가", "겹침 후보는 유지, 얼굴 특징점으로 카메라 정면도 판정", "부분 성공: 가림 후보는 나왔으나 시선 관찰률은 과대평가"),
        scene(22, "양손을 들고 잠시 멈춤", "보이는 손목 관찰; 5초 미만이면 정지 사건 없음", "양손목 판정 불가, handStillSeconds=null", "정지 사건의 정답은 이 장면만으로 확정 불가; 손목 검출은 실패"),
        scene(24, "의자를 휴대폰으로 오인", "물건 없음", "의자 부분에 cell phone 0.42 검출", "오검출: 이 구간 20표본 중 18표본에서 같은 잘못된 라벨"),
        scene(28, "음료 컵을 듦", "물건 존재와 손 상호작용 후보", "wine glass로 검출, 상호작용 후보 0건", "부분 성공: 물건은 찾았지만 종류가 틀리고 접촉 후보는 누락"),
        scene(36, "작은 흰 물건을 듦", "물건 영역과 손 상호작용 후보", "지속 검출 없음; 34–40초에 산발적 다른 라벨", "실패: 임의의 작은 물건까지 인식하지 못함"),
    ]
)

html_text = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ProPitch Vision · 안 되는 행동 예시 실험</title>
<style>
:root{{--ink:#18283a;--muted:#526273;--paper:#f4f7f9;--line:#d7e1e8;--blue:#095ca4;--red:#9d2635;--amber:#925a05;--green:#0d7659}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.7 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}}
header{{background:linear-gradient(130deg,#102e48,#193e52);color:white;padding:48px max(22px,calc((100vw - 1160px)/2)) 42px}}header p{{color:#d9e8f0;max-width:900px}}header h1{{font-size:clamp(30px,4vw,48px);line-height:1.25;margin:10px 0 16px;letter-spacing:-.04em}}
.eyebrow{{font-size:13px;font-weight:800;letter-spacing:.14em;color:#8fe0d6}}nav{{display:flex;flex-wrap:wrap;gap:8px;margin-top:25px}}nav a{{color:white;text-decoration:none;border:1px solid #9fb6c4;border-radius:20px;padding:5px 13px;font-size:14px}}
main{{max-width:1200px;margin:auto;padding:10px 20px 60px}}section{{background:white;border:1px solid var(--line);border-radius:14px;margin-top:24px;padding:28px}}h2{{font-size:25px;margin:0 0 14px;letter-spacing:-.025em}}h3{{margin:4px 0 10px;font-size:19px}}p{{margin:8px 0}}.lead{{font-size:18px}}.muted{{color:var(--muted)}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}}.card{{background:#edf4f8;border-radius:10px;padding:18px}}.card strong{{display:block;font-size:29px;line-height:1.1;color:var(--blue)}}.card span{{font-size:13px;color:var(--muted)}}.notice{{border-left:4px solid #df9e38;background:#fff8e9;border-radius:6px;padding:13px 16px;margin:18px 0}}.danger{{border-color:#d14b58;background:#fff0f1}}
table{{border-collapse:collapse;width:100%;min-width:650px;font-size:14px}}th,td{{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}}th{{background:#edf2f5;white-space:nowrap}}.table-wrap{{overflow-x:auto}}.badge{{display:inline-block;padding:2px 9px;border-radius:14px;font-size:12px;font-weight:800;white-space:nowrap}}.bad{{background:#ffe1e4;color:var(--red)}}.partial{{background:#fff0d2;color:var(--amber)}}.unknown{{background:#e9eef1;color:#4b5e69}}.ok{{background:#dff3e9;color:var(--green)}}code{{font:13px ui-monospace,SFMono-Regular,monospace;background:#ecf2f6;padding:2px 5px;border-radius:4px}}pre{{background:#10283b;color:#e6f2f8;padding:20px;border-radius:10px;overflow:auto;font:12px/1.55 ui-monospace,SFMono-Regular,monospace;max-height:550px}}
.scene-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.scene{{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fcfdfd}}.scene img{{width:100%;display:block}}.scene>div{{padding:14px 16px}}.scene p{{font-size:14px}}.time{{font-size:13px;font-weight:800;color:var(--blue)}}.verdict{{color:var(--red)}}.legend{{font-size:13px;color:var(--muted)}}.steps li{{margin:8px 0}}details summary{{cursor:pointer;font-weight:700}}footer{{text-align:center;color:var(--muted);font-size:13px;padding:20px}}
@media(max-width:850px){{.cards{{grid-template-columns:1fr 1fr}}.scene-grid{{grid-template-columns:1fr}}section{{padding:20px}}}}@media(max-width:480px){{.cards{{grid-template-columns:1fr 1fr}}.card strong{{font-size:24px}}main{{padding:8px}}header{{padding:32px 20px}}}}
</style></head><body>
<header><div class="eyebrow">PROPITCH / VISION FIELD CHECK / 2026-11-11</div><h1>휴대폰 가림 후보는 잡았습니다.<br>손 기반 판정은 이번 영상에서 실패했습니다.</h1>
<p>사용자가 제공한 40.2초 MOV를 승인한 YOLO11n-pose + YOLO5Face + YOLO11n-seg 조합으로 5 FPS, 201표본 분석했습니다. 화면을 보고 기록한 대표 장면과 실제 모델 JSON을 맞춰 보았습니다. 사람의 전 구간 정답 주석은 없으므로 정확도 수치는 제시하지 않습니다.</p>
<nav><a href="#result">결론</a><a href="#comparison">기대와 실제</a><a href="#scenes">장면</a><a href="#json">JSON 해설</a><a href="#next">판단·다음 단계</a></nav></header><main>
<section id="result"><h2>01 · 결과 먼저</h2><p class="lead"><b>이 영상으로 세 가지 금지 행동을 모두 검증할 수는 없었습니다.</b> 휴대폰이 얼굴을 가리는 장면의 물건 겹침 후보만 부분적으로 나왔습니다. 손 가림·양손 정지·물건 접촉 후보는 생성되지 않았습니다.</p>
<div class="cards"><div class="card"><strong>194 / 201</strong><span>발표자와 연결된 얼굴 출력 표본<br>가림 상태의 정확도를 뜻하지 않음</span></div><div class="card"><strong>0 / 201</strong><span>양쪽 손목 신뢰도 0.5 이상 표본</span></div><div class="card"><strong>2건</strong><span>휴대폰·얼굴 겹침 후보<br>11.6–12.0초 / 12.6–16.2초</span></div><div class="card"><strong>{RUNTIME['wallSeconds']:.1f}초</strong><span>40.2초 영상의 이번 CPU 전체 실행 시간</span></div></div>
<div class="notice danger"><b>가장 큰 오류:</b> 두 손을 든 22–26초에 의자 부분을 <code>cell phone</code>으로 {still['labels']['cell phone']}/{still['count']}표본 검출했습니다. 반대로 실제 손목은 거의 검출하지 못해 물건을 손에 들었는지 판정할 근거가 없습니다.</div>
<p class="muted">모델 파일은 기존 실험의 로컬 가중치를 사용했습니다. 손 전용 모델·YOLOE·LLM은 실행하지 않았고 점수는 계산하지 않았습니다. YOLO11n-seg 가중치의 범주는 80개로, 임의의 모든 물건을 인식하는 모델이 아닙니다.</p></section>
<section id="comparison"><h2>02 · 기대한 관찰과 실제 JSON 비교</h2><div class="table-wrap"><table><thead><tr><th>장면 / 기준</th><th>화면 기준 기대</th><th>실제 출력</th><th>판단</th></tr></thead><tbody>
<tr><td>손으로 얼굴 가림<br>0–10초 중 여러 장면</td><td>손 가림 후보. 가려진 얼굴의 시선은 관찰 불가.</td><td>손 가림 사건 0건. 이 구간 얼굴 연결 {hand['faces']}/{hand['count']}표본, 정면 {hand['frontal']}/{hand['gaze_observable']}관찰표본.</td><td><span class="badge bad">실패</span> 손 영역 검출이 없음</td></tr>
<tr><td>휴대폰으로 얼굴 가림<br>약 11–17초</td><td>휴대폰 영역 + 얼굴 가림 후보가 대체로 이어져야 함.</td><td><code>cell phone</code> {phone['labels']['cell phone']}/{phone['count']}표본. 겹침 후보 11.6–12.0초, 12.6–16.2초. 12.0–12.6초 얼굴 미연결.</td><td><span class="badge partial">부분 성공</span> 확정 가림은 아님</td></tr>
<tr><td>양손 정지<br>22–26초</td><td>보이는 손은 관찰해야 함. 단, 이 대표 구간은 약 4초로 5초 사건의 정답이 아님.</td><td><code>handObservableSeconds=0</code>, <code>handStillSeconds=null</code>, 정지 사건 없음.</td><td><span class="badge unknown">판정 불가</span> 손목 검출 자체가 실패</td></tr>
<tr><td>손에 든 물건<br>휴대폰·컵·작은 물건</td><td>검출된 물건과 손의 상호작용 후보. 발표와 무관한지는 문맥 판단.</td><td><code>OBJECT_INTERACTION_CANDIDATE</code> 0건; LLM <code>NOT_RUN</code>.</td><td><span class="badge bad">후보 추출 실패</span> 관련성은 미평가</td></tr>
<tr><td>컵<br>28–32초</td><td>물건 영역과 컵에 가까운 라벨.</td><td><code>wine glass</code> {cup['labels']['wine glass']}/{cup['count']}표본, <code>bottle</code> 1표본.</td><td><span class="badge partial">영역만 부분 성공</span> 종류 오류</td></tr>
<tr><td>작은 흰 물건<br>34–40초</td><td>물건 영역을 안정적으로 검출.</td><td>일관된 물건 라벨 없음. 산발적 <code>chair</code>/<code>donut</code>/<code>apple</code>/<code>cell phone</code>.</td><td><span class="badge bad">실패</span> 임의 물건 인식 불가</td></tr>
<tr><td>카메라 정면 방향</td><td>가려진 얼굴은 분모에서 제외. 청중 시선 접촉은 별도 기준.</td><td><code>frontFacingRatio={gaze['frontFacingRatio']:.4f}</code> ({gaze['frontFacingRatio']*100:.1f}%), <code>coverageRatio={gaze['coverageRatio']:.4f}</code>.</td><td><span class="badge bad">과대평가 위험</span> 가림 중에도 얼굴 특징점 출력</td></tr>
</tbody></table></div><p class="legend">표본 수는 5 FPS 검출 인스턴스 수입니다. 사람이 전 프레임에 붙인 정답이 아니므로 precision·recall로 읽지 마세요. 특히 실제 물건의 발표 관련성은 영상 제목만으로 확정하지 않았습니다.</p></section>
<section id="scenes"><h2>03 · 실제 장면과 모델 표시</h2><p class="legend">초록: 선택된 몸 박스·신뢰도 높은 관절. 빨강: 신뢰도 0.5 미만 손목. 노랑: 얼굴 박스·특징점. 파랑: YOLO11n-seg 물건 검출. 표본 하나는 0.2초를 대표합니다.</p><div class="scene-grid">{scenes}</div></section>
<section id="json"><h2>04 · 실제 JSON은 무엇을 말하는가</h2><div class="table-wrap"><table><thead><tr><th>필드</th><th>이번 값</th><th>해석과 기대 차이</th></tr></thead><tbody>
<tr><td><code>sourceEndSec</code></td><td>40.2</td><td>분석 시간축. 원본 메타데이터 약 40.17초를 0.2초 표본 단위로 표현.</td></tr>
<tr><td><code>isScoringReady</code></td><td>false</td><td>정확한 상태. 이 결과로 제스처·시선 점수를 만들면 안 됨.</td></tr>
<tr><td><code>gaze.observableSeconds</code></td><td>{gaze['observableSeconds']:.1f}</td><td>얼굴 5점 기하 판정 가능 시간. 손·휴대폰 가림 중 일부도 포함돼 실제 유효 시간보다 클 수 있음.</td></tr>
<tr><td><code>gaze.frontFacingSeconds</code></td><td>{gaze['frontFacingSeconds']:.1f}</td><td>그중 얼굴이 카메라 정면이라는 규칙의 시간. 눈동자·Zoom 화면 속 청중 응시의 정답 아님.</td></tr>
<tr><td><code>gaze.frontFacingRatio</code></td><td>{gaze['frontFacingRatio']:.4f}</td><td>{gaze['frontFacingSeconds']:.1f}/{gaze['observableSeconds']:.1f}. 가림 장면까지 세므로 이번 영상의 실제 시선 접촉률로 쓰면 안 됨.</td></tr>
<tr><td><code>gaze.coverageRatio</code></td><td>{gaze['coverageRatio']:.4f}</td><td>{gaze['observableSeconds']:.1f}/40.2. 얼굴 박스가 보인다는 이유로 관찰률이 과대평가될 수 있음.</td></tr>
<tr><td><code>handObservableSeconds</code> / <code>handCoverageRatio</code></td><td>0 / 0</td><td>양손목·어깨와 1초 이력이 충족된 시간이 없음. 화면에는 손이 보이는 구간이 있어 모델 관찰 실패를 드러냄.</td></tr>
<tr><td><code>handStillSeconds</code></td><td>null</td><td>손의 움직임을 판단할 수 없다는 뜻. 0초 또는 ‘정지하지 않음’이 아님.</td></tr>
<tr><td><code>gestureEvents</code></td><td>[]</td><td>5초 이상 연속 정지 사건 없음. 양손 관찰이 0이므로 정상 행동 근거가 아님.</td></tr>
<tr><td><code>candidateEvents</code></td><td>{len(events)}건</td><td>둘 다 <code>OBJECT_FACE_OVERLAP_CANDIDATE</code> / <code>cell phone</code>. 손 가림·물건 접촉 후보는 없음.</td></tr>
<tr><td><code>interactionDiagnostics.nearWristDetectionCount</code></td><td>0</td><td>손목이 관찰되지 않아 물건과 함께 움직였는지 계산되지 않음.</td></tr>
<tr><td><code>criterionStatus</code></td><td>UNOBSERVABLE / CANDIDATE_ONLY / NOT_EVALUATED</td><td>순서대로 양손 정지 / 얼굴 가림 / 무관 물건. 보류 상태를 명시한 것은 타당함.</td></tr>
<tr><td><code>unobservableIntervals</code></td><td>손 0–40.2초 대부분</td><td>양손 정지의 관찰 불가 사유 기록. 얼굴 가림을 시선 관찰 불가로 반영하지 못한 구간이 남음.</td></tr>
<tr><td><code>evidence</code> / <code>contextJudgments</code></td><td>겹침 근거 2개 / LLM NOT_RUN</td><td>근거 연결은 유효하나 발표 관련성 판정은 실행되지 않음.</td></tr>
</tbody></table></div><details><summary>실제 생성된 JSON 전체 보기</summary><pre>{raw_json}</pre></details></section>
<section id="next"><h2>05 · 판단과 다음 실험</h2><ol class="steps"><li><b>현재 결과:</b> 휴대폰 얼굴 겹침 후보만 연구용으로 유지합니다. 손 가림·정지·접촉 부재나 시선 접촉 88.1%로 발표 점수를 만들지 않습니다.</li><li><b>손 모델 문제:</b> 이 구도에서 YOLO11n-pose 손목은 거의 신뢰되지 않았습니다. 현재 모델의 입력 해상도·자르기 조건을 바꾸는 별도 비교나 손 전용 모델 재검토가 필요합니다. 이번 보고서에서 개선을 주장하지 않습니다.</li><li><b>물건 범위:</b> COCO 80종 검출만으로 임의 물건을 보장할 수 없습니다. 휴대폰 참검출과 의자 휴대폰 오검출을 함께 평가해야 합니다. 관련성 LLM에는 검출 라벨만 보내지 말고 위치·시간·프레임 근거와 발표 문맥을 함께 줘야 합니다.</li><li><b>시선:</b> 손·물건 가림을 먼저 식별해 가려진 구간을 관찰 불가로 처리해야 합니다. Zoom 화면 속 청중 응시까지 Y로 볼 경우, 카메라 위치와 화면 배치가 알려진 별도 Zoom 영상 및 사람의 Y/N/판정 불가 라벨이 필요합니다.</li><li><b>검증 범위:</b> 이번 영상은 사용자가 제시한 단일 예시이며 대표 장면을 사후 시각 검토했습니다. 임계값 선택과 최종 품질 평가에 같은 영상을 반복 사용하면 독립 검증이 아닙니다.</li></ol><div class="notice"><b>정답과 평가 범위:</b> 휴대폰이 얼굴을 가리고 손·컵·작은 물건이 보이는 대표 장면은 사람이 화면을 보고 기록했습니다. 정확한 행동 시작·끝과 발표 관련성은 전 구간에 독립 라벨을 붙이지 않았으므로 정밀도·재현율·실제 시선 접촉률을 계산하지 않았습니다.</div></section>
<footer>로컬 실험 결과 · 공개 API/DB/루브릭은 변경하지 않음 · 원본 MOV를 보고서에 복제하지 않음</footer></main></body></html>"""

(OUT / "report.html").write_text(html_text, encoding="utf-8")
print(OUT / "report.html")
