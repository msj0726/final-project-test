"""Report fixed-input VLM results without inventing unlabelled accuracy."""
import base64
import html
import json
from pathlib import Path
from compare_vlm import PROMPT_V2, validate

ROOT=Path(__file__).resolve().parent/'results/vlm_comparison'
manifest=json.loads((ROOT/'manifest.json').read_text())
labels=json.loads((ROOT/'evaluation_labels.json').read_text())
names={'baseline':'현재 모델 · CPU','openai':'GPT-6.1 Sol · API','qwen':'Qwen3.5-9B 4bit · MLX · 원본 지침','qwen_prompt_v2':'Qwen3.5-9B 4bit · MLX · 수정 지침'}
criteria={'bothWristsStillIntervals':'5초 이상 양손 정지','nonFrontFacingIntervals':'비정면 얼굴 방향','handFaceCoverIntervals':'손의 얼굴 가림','bothWristsVisibleIntervals':'양손목 관찰 가능'}

def contains(intervals,t):return any(a<=t<b-1e-6 for a,b in intervals)
def escape(x):return html.escape(str(x))
def dump(x):return escape(json.dumps(x,ensure_ascii=False,indent=2))
def load(provider,clip):
    p=ROOT/clip/f'{provider}.json'
    return json.loads(p.read_text()) if p.exists() else {'status':'NOT_RUN'}

def metrics(provider):
    output={}
    for key,items in labels['criteria'].items():
        counts=dict(tp=0,fn=0,fp=0,tn=0,missingPositive=0,missingNegative=0)
        for item in items:
            prediction=load(provider,item['clipId'])
            for positive,field in [(True,'positive'),(False,'negative')]:
                for start,end in item[field]:
                    for i in range(round((end-start)*5)):
                        if prediction['status']!='OK':counts['missingPositive' if positive else 'missingNegative']+=1;continue
                        detected=contains(prediction['result'][key],round(start+i*.2,3))
                        counts['tp' if positive and detected else 'fn' if positive else 'fp' if detected else 'tn']+=1
        output[key]=counts
    return output

assert contains([[1,2]],1) and not contains([[1,2]],2)
results={p:metrics(p) for p in names}
summary={}
for provider in names:
    runs=[load(provider,c['clipId']) for c in manifest['clips']]
    valid=[r for r in runs if r['status']=='OK']
    format_issues=[]
    for clip,run in zip(manifest['clips'],runs):
        try:
            raw=run.get('rawResponse')
            parsed=json.loads(raw.strip().removeprefix('```json').removesuffix('```').strip()) if raw is not None else run['result']
            validate(parsed,clip)
        except (ValueError,TypeError,KeyError) as error:
            format_issues.append({'clipId':clip['clipId'],'reason':str(error)})
    conflicts=[]
    for clip,run in zip(manifest['clips'],runs):
        if run['status']!='OK':continue
        overlap=sum(contains(run['result']['nonFrontFacingIntervals'],f['timestamp']) and contains(run['result']['gazeUnobservableIntervals'],f['timestamp']) for f in clip['frames'])
        if overlap:conflicts.append({'clipId':clip['clipId'],'overlapSeconds':round(overlap*.2,2)})
    semantic_issues=[]
    for clip,run in zip(manifest['clips'],runs):
        if run['status']!='OK':continue
        for interval in run['result']['bothWristsStillIntervals']:
            if interval[1]-interval[0]<5-1e-6:semantic_issues.append({'clipId':clip['clipId'],'kind':'STILLNESS_UNDER_5_SECONDS','interval':interval})
            if any(not contains(run['result']['bothWristsVisibleIntervals'],round(interval[0]+i*.2,3)) for i in range(round((interval[1]-interval[0])*5))):semantic_issues.append({'clipId':clip['clipId'],'kind':'STILLNESS_WITHOUT_VISIBLE_WRISTS','interval':interval})
    summary[provider]={'completed':len(valid),'total':len(runs),'jsonFormatValid':len(runs)-len(format_issues),'jsonFormatIssues':format_issues,'totalInferenceSeconds':round(sum(r.get('elapsedSeconds',0) for r in runs),2),'apiCostUsdUpperBound':round(sum(r.get('costUsdUpperBound',0) for r in runs),6),'gazeExclusionOverlap':conflicts,'semanticIssues':semantic_issues,'metrics':results[provider]}
(ROOT/'comparison_metrics.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
rows=''
for key,title in criteria.items():
    cells=[]
    for provider in names:
        m=results[provider][key];pos=m['tp']+m['fn']+m['missingPositive'];neg=m['fp']+m['tn']+m['missingNegative']
        text=f"양성 포착 {m['tp']}/{pos} ({m['tp']/pos*100:.1f}%)" if pos else '양성 정답 없음'
        text+=f"<br>음성 오검출 {m['fp']}/{neg}" if neg else '<br>음성 정답 없음 → 오검출률 미확인'
        if m['missingPositive'] or m['missingNegative']:text+=f"<br>출력 실패로 평가 불가: 양성 {m['missingPositive']}, 음성 {m['missingNegative']}표본"
        cells.append('<td>'+text+'</td>')
    rows+='<tr><th>'+title+'</th>'+''.join(cells)+'</tr>'
speed_rows=''.join(f"<tr><th>{names[p]}</th><td>{s['jsonFormatValid']}/{s['total']}</td><td>{s['totalInferenceSeconds']}초</td><td>${s['apiCostUsdUpperBound']:.5f}</td><td>{len(s['semanticIssues'])}건</td><td>{escape(s['gazeExclusionOverlap'])}</td></tr>" for p,s in summary.items())
details=''
for clip in manifest['clips']:
    images=''.join('<img alt="시각 '+str(f['timestamp'])+'초" src="data:image/jpeg;base64,'+base64.b64encode(Path(f['path']).read_bytes()).decode()+'">' for f in clip['frames'][::max(1,len(clip['frames'])//4)][:4])
    blocks=''.join(f"<details><summary>{names[p]} · {load(p,clip['clipId'])['status']}</summary><pre>{dump(load(p,clip['clipId']))}</pre></details>" for p in names)
    details+=f"<article><h3>{clip['clipId']} · {clip['startSec']}–{clip['endSec']}초</h3><div class='frames'>{images}</div>{blocks}</article>"
recommendation=(ROOT/'recommendation.txt').read_text() if (ROOT/'recommendation.txt').exists() else '로컬 실행 진행 중: 최종 모델 추천은 아직 확정하지 않았습니다.'
page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>현재 Vision·Qwen·GPT 실측 비교</title><style>
body{{background:#f3f5fa;color:#1e293b;font:16px/1.7 system-ui;margin:0;overflow-wrap:anywhere}}main{{max-width:1160px;margin:auto;padding:24px}}section,article{{background:white;padding:24px;border-radius:16px;margin:20px 0}}header{{background:#152d48;color:white;padding:30px;border-radius:18px}}h1,h2{{line-height:1.3}}table{{border-collapse:collapse;width:100%;min-width:700px}}td,th{{padding:12px;border:1px solid #d8e1ec;text-align:left;vertical-align:top}}th{{background:#edf3fa}}.scroll{{overflow:auto}}.note{{background:#fff5de;padding:16px;border-left:4px solid #bf7e1b}}pre{{white-space:pre-wrap;background:#172a40;color:#e6effa;padding:18px;font-size:13px;overflow-wrap:anywhere}}.frames{{display:flex;gap:8px;overflow:auto}}.frames img{{width:24%;object-fit:contain}}summary{{cursor:pointer;padding:10px;font-weight:600}}a{{color:#1265a8}}</style><main>
<header><h1>현재 Vision · 로컬 Qwen · GPT 비교 결과</h1><p>{escape(recommendation)}</p><p>2026-11-12 · 테스트 환경 · 같은 337개 프레임 · 총 API 예산 $5 · Anthropic은 사용자 요청으로 제외</p></header>
<section><h2>1. 결과 먼저</h2><div class="scroll"><table><tr><th>항목</th>{''.join('<th>'+n+'</th>' for n in names.values())}</tr>{rows}</table></div><p class="note">위 수치는 0.2초 단위의 <strong>정답이 있는 구간에서의 포착</strong>이다. 정지와 비정면에는 명확한 음성 정답이 없어서 Precision·F1·전체 Accuracy를 계산하지 않았다. 얼굴 가림의 음성도 한 짧은 영상 7표본뿐이다. 이 작은 결과를 전체 발표 정확도로 해석하면 안 된다.</p></section>
<section><h2>2. 시간·비용·출력 오류</h2><div class="scroll"><table><tr><th>구성</th><th>형식에 맞는 JSON</th><th>추론 합계</th><th>API 비용 상한 추정</th><th>정지 규칙 위반</th><th>비정면·관찰 불가 중복(후처리 필요)</th></tr>{speed_rows}</table></div><p>JSON 형식은 원문을 다시 파싱해 정확한 7개 필드, 숫자 두 개짜리 시간 구간, 시간 범위, 움직임 횟수·제한사항의 자료형을 확인했다. 형식 오류: {escape({p:s['jsonFormatIssues'] for p,s in summary.items() if s['jsonFormatIssues']})}. 형식 통과와 행동 판정의 정확도는 별개다. 정지 규칙 위반은 5초 미만 사건이나 양손목을 관찰할 수 없는 정지 사건을 센 것이다. 같은 사건에 두 사유가 있으면 두 건으로 센다. 정확도 표에는 원출력을 그대로 사용했다.</p><p>추론 합계는 모델 로딩·다운로드·영상 프레임 추출을 제외한다. API는 네트워크 대기까지 포함한다. CPU와 Mac GPU, 클라우드 하드웨어가 달라 같은 하드웨어의 속도 순위는 아니다. 중복된 영상 구간을 포함한 입력 분량은 67.4초이며 전체 길이 영상의 처리속도 예측치는 아니다.</p><p>GPT 비용은 기존 비교의 반환 토큰에 적용한 상한 추정이다. 이번 지침 수정 시험에서는 GPT API를 다시 호출하지 않아 추가 API 비용은 $0이다. Qwen과 기존 모델의 API 비용은 $0이지만 전력·기기·실행 시간 비용이 무료라는 뜻은 아니다. <a href="https://developers.openai.com/api/docs/pricing">OpenAI 공식 가격</a>.</p></section>
<section><h2>3. 입력 변경과 비교 한계</h2><p>로컬 모델은 16GB Apple M5에서 Qwen3.5-9B의 사전 4비트 양자화본을 MLX로 실행했다. PyTorch MPS의 로딩 중 메모리 압박으로 중단한 뒤 사용자 동의를 받아 전환했다. MLX_METAL_GPU_ARCH=agx16g로 호환 커널 경로를 사용했다. 큰 모델은 이번 비교에 포함하지 않았다.</p><p>9개 구간의 동일한 337개 JPEG 프레임과 시간표시, 모델, 700 출력 토큰 제한을 유지했다. 수정 Qwen에는 손목이 실제 보일 때만 관찰 구간을 출력하고, 가려진 얼굴은 비정면 대신 관찰 불가로 표시하며, 정확한 JSON 구조를 자체 확인하도록 영어 지침을 바꿨다. 영상 프레임 자체는 바꾸지 않았다. 기존 Vision과 GPT 결과는 이전 시험값을 재사용했다. 정답 시각이나 기존 예측은 새 지침에 넣지 않았다. <details><summary>Qwen 수정 지침 전문</summary><pre>{escape(PROMPT_V2)}</pre></details></p><p>이 실험은 원본 영상 직접 입력 방식이 아닌 다중 이미지 방식이다. GPT 비교에는 사용자 영상에서 뽑은 JPEG 프레임이 OpenAI API로 전송됐다. 요청에 store=false를 지정했지만 제공자의 보관 정책을 이 설정만으로 확인한 것은 아니다.</p><p>기존 모델도 같은 축소 이미지로 새로 실행했으므로 예전 원본 해상도 실험과 숫자가 달라질 수 있다. 현재 모델은 YOLO11n-pose·YOLO5Face·YOLO11n-seg·MediaPipe Hands와 기존 사건 규칙이다. 손 가림의 현재 모델 출력은 기하학적 겹침 후보이고 VLM은 의미적 가림을 추정한다.</p><p>수정 지침은 기존 Qwen 실패 사례를 본 뒤 만들었고, 모든 영상은 이미 여러 번 살펴본 개발 자료다. 따라서 같은 자료에서 개선되어도 독립 검증이나 일반화 성능 향상으로 해석하지 않는다. 정지 21–27초와 비정면 6–14초는 사용자 지정, 공개 영상 라벨은 이전 AI의 화면 검토다. 독립된 사람 평가자가 새로 정답을 만든 평가가 아니다. 무용 영상의 정지 라벨은 1초 간격 검토로 경계 오차가 있다.</p></section>
<section><h2>4. 아직 모델 순위를 정할 수 없는 항목</h2><ul><li>분당 손짓 8회: 정확한 이동→멈춤 정답 횟수가 없어 이번에는 정확도를 산출하지 않았다. 8초 출력 횟수를 1분으로 외삽하지 않는다.</li><li>얼굴이 정확히 60도 돌아간 비율: 각도 정답·카메라 보정이 없어 평가하지 않았다. 비정면은 눈동자 시선 접촉과도 다르다.</li><li>발표와 무관한 물건: 이번 입력에는 STT·발표 맥락과 해당 정답이 없어 평가하지 않았다.</li><li>여러 인물 중 발표자 선택: 정성 검토 구간이다. VLM이 JSON을 냈다는 이유만으로 올바른 사람을 선택했다고 확정하지 않는다.</li><li>눈이 가려져도 머리가 돌아간 모습은 보일 수 있어 비정면과 관찰 불가의 중복 자체를 오인식으로 단정할 수 없다. 다만 현재 시선 정책에서는 관찰 불가를 먼저 제외해야 한다. 프롬프트도 중복 금지를 명시하지 않았으므로 이 중복을 모델 정확도 감점으로 사용하지 않았다.</li></ul></section>
<section><h2>5. 장면별 실제 전체 JSON</h2><p>아래는 실측 응답과 토큰·시간이다. 각 항목을 펼쳐 확인할 수 있다. interval은 원본 영상의 절대 초 단위 [시작,끝)이며, 정지 배열은 5초 이상 후보만 포함한다. hand motion count의 null은 판단 불가, 0은 완료된 움직임을 출력하지 않았다는 의미다. 이 실험 JSON은 모델 비교용이며 백엔드 공용 계약을 변경하지 않았다.</p>{details}</section>
<section><h2>6. 재현 자료</h2><p><a href="comparison_metrics.json">비교 집계 JSON</a> · <a href="evaluation_labels.json">정답 출처와 평가 범위</a> · <a href="local_attempts.json">로컬 실행 시도 기록</a></p><p>Qwen 모델과 런타임: <a href="https://huggingface.co/Qwen/Qwen3.5-9B">공식 모델 카드</a>, <a href="https://huggingface.co/mlx-community/Qwen3.5-9B-4bit">9B MLX 양자화 모델</a>. 현재 모델의 원본 실험 자료와 공개 영상 출처는 <a href="../followup_rule_evaluation/report.html">이전 보고서</a>에서 확인할 수 있다. 코드·결과는 visual_test 안에서만 생성했고 Git 업로드는 하지 않았다.</p></section></main></html>'''
(ROOT/'report.html').write_text(page)
print(json.dumps(summary,ensure_ascii=False,indent=2))
