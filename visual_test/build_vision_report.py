"""Build a self-contained Korean HTML experiment report and portable evidence bundle."""
import base64
import hashlib
import html
import json
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.report_tools'))
import jsonschema
import cv2
from summarize_vision_study import self_check,validate,draw
from vision_study import OUT

s=json.loads((OUT/'summary.json').read_text())
rows=json.loads((OUT/'observations.json').read_text())
setup=json.loads((OUT/'setup.json').read_text())
manifest=json.loads((ROOT.parent/'data/open_presentations/manifest.json').read_text())

schema={
 '$schema':'https://json-schema.org/draft/2020-12/schema', 'title':'Vision experiment output v1',
 'type':'object','required':['schemaVersion','clipId','sourceStartSec','sourceEndSec','sampleDurationSeconds','vision','limitations','isScoringReady'],
 'properties':{
  'schemaVersion':{'const':'vision-experiment-v1'},'isScoringReady':{'const':False},
  'clipId':{'type':'string'},'sourceStartSec':{'type':'number','minimum':0},'sourceEndSec':{'type':'number','minimum':0},'sampleDurationSeconds':{'type':'number','exclusiveMinimum':0},
  'vision':{'type':'object','required':['gaze','handObservableSeconds','handStillSeconds','gestureEvents','criterionStatus','candidateEvents','bothWristsVisibleSeconds'],
    'properties':{
      'gaze':{'type':'object','required':['observableSeconds','frontFacingSeconds','frontFacingRatio','coverageRatio','method'],'properties':{
        'observableSeconds':{'type':'number','minimum':0},'frontFacingSeconds':{'type':'number','minimum':0},
        'frontFacingRatio':{'type':['number','null'],'minimum':0,'maximum':1},'coverageRatio':{'type':'number','minimum':0,'maximum':1},'method':{'type':'string'}}},
      'handObservableSeconds':{'type':'number','minimum':0},'handStillSeconds':{'type':['number','null'],'minimum':0},'bothWristsVisibleSeconds':{'type':'number','minimum':0},
      'gestureEvents':{'type':'array','items':{'$ref':'#/$defs/event'}},
      'candidateEvents':{'type':'array','items':{'$ref':'#/$defs/event'}},
      'criterionStatus':{'type':'object','required':['HAND_STILLNESS','FACE_OCCLUSION','UNRELATED_OBJECT_TOUCH'],'properties':{
         'HAND_STILLNESS':{'enum':['EVALUATED','UNOBSERVABLE']},'FACE_OCCLUSION':{'const':'CANDIDATE_ONLY'},'UNRELATED_OBJECT_TOUCH':{'const':'PENDING_CONTEXT_JUDGMENT'}}}}},
  'limitations':{'type':'array','minItems':1,'items':{'type':'string'}}},
 '$defs':{'event':{'type':'object','required':['eventId','kind','startSec','endSec','confidence'],'properties':{
   'eventId':{'type':'string','minLength':1},'kind':{'type':'string'},'startSec':{'type':'number','minimum':0},'endSec':{'type':'number','minimum':0},'confidence':{'type':['number','null'],'minimum':0,'maximum':1}}}}
}
(OUT/'vision-experiment.schema.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2))
for clip in s['clips']:
 clip['isScoringReady']=False
 jsonschema.validate(clip,schema)
 validate(clip,[r for r in rows if r['clipId']==clip['clipId']])
 (OUT/'json'/f"{clip['clipId']}.json").write_text(json.dumps(clip,ensure_ascii=False,indent=2,allow_nan=False))
# Negative checks ensure the schema does reject malformed data.
for value in (-.1,1.1,'0.75'):
 bad=json.loads(json.dumps(s['clips'][0]));bad['vision']['gaze']['frontFacingRatio']=value
 try:jsonschema.validate(bad,schema)
 except jsonschema.ValidationError:pass
 else:raise AssertionError('Invalid ratio accepted')
checks=dict(schemaValidFiles=9,negativeSchemaChecks=3,syntheticBehaviorChecks=self_check(),semanticChecksFrames=len(rows),videos=0,decodedVideoFrames=0)
for clip in s['clips']:
 for mode in ('baseline','hands','standard','open'):
  path=OUT/'videos'/f"{clip['clipId']}_{mode}.mp4"
  cap=cv2.VideoCapture(str(path));assert cap.isOpened();n=0
  while cap.read()[0]:n+=1
  cap.release();assert n==50
  checks['videos']+=1;checks['decodedVideoFrames']+=n
checks['result']='PASS'
(OUT/'validation.json').write_text(json.dumps(checks,indent=2))
(OUT/'summary.json').write_text(json.dumps(s,ensure_ascii=False,indent=2,allow_nan=False))

errors=[
 dict(id='T01',severity='수정 완료',frame='jack_325_000.jpg',title='WebM FPS 메타데이터로 잘못된 위치를 탐색',detail='Jack 원본의 OpenCV 명목 FPS는 1000이지만 실제 PTS 간격은 약 33ms다. 이전 출력 확인의 175초 미검출은 해당 시점의 증거로 사용할 수 없다. 이번 실행은 전체 순차 디코딩 후 PTS로 5 FPS 표본을 선택했다.',action='sourceTimeSec에 실제 디코딩 시각을 저장하고 목표 시각과 차이 0.1초 미만을 검사했다.'),
 dict(id='V01',severity='정상 제외 확인',frame='erik_10_000.jpg',title='손이 화면 밖인 구간을 정지 0초로 오해하지 않음',detail='Erik 상반신 영상에서 손목이 보이지 않는다. 프레임 정지 판정은 null이며, 클립 handObservableSeconds=0, handStillSeconds=null이다. EVALUATED와 무사건 0초로 처리하지 않았다.',action='관찰 불가 null + 사유를 유지. 양손을 촬영하지 않으면 제스처 점수를 제공하지 않는 정책 필요.'),
 dict(id='G01',severity='오판 위험 · 정답 미확정',frame='jack_105_000.jpg',title='고개를 숙인 장면에도 정면 YES가 나옴',detail='105.005초 화면에서 얼굴은 아래쪽으로 숙여 보이지만 5점 기하 규칙은 정면으로 출력했다. 정확한 머리 각도 정답은 없으므로 확정 FP 수로 세지 않았다. 좌우 대칭만으로 카메라 방향을 대변하기 어려운 사례다.',action='별도 고개 방향 정답을 붙여 pitch 경계를 검증. 현재 비율을 확정 시선 점수로 사용하지 않음.'),
 dict(id='O01',severity='육안 오검출 확인',frame='jack_65_025.jpg',title='YOLO11n-seg가 무대 영역을 umbrella로 출력',detail='70.003초의 초록 umbrella 영역에는 우산이 보이지 않고 무대 장식과 배경이 포함된다. 이 물건 박스를 접촉 근거로 바로 사용하면 잘못된 사건이 생길 수 있다.',action='물건 검출 정확도와 손 주변 영역을 따로 검증. 이번 후보에서 자동 감점 금지.'),
 dict(id='O02',severity='육안 오검출 확인',frame='jack_165_025.jpg',title='일반 YOLO의 kite·umbrella 오검출과 손목 오차',detail='170.003초의 초록 kite·umbrella 출력은 무대 배경에 걸쳐 있다. 화면 오른쪽 손의 손목 점도 실제 손보다 팔 아래에 있어, 손목만으로 손과 얼굴 거리를 재면 오차가 생긴다.',action='손 전용 모델의 보완 가능성은 있으나 이 표본에서 개선률을 계산할 라벨은 없다.'),
 dict(id='O03',severity='후보 생성 규칙의 문제',frame='erik_10_000.jpg',title='YOLOE의 얼굴·안경·수염 영역이 가림 후보로 섞임',detail='프롬프트 없는 YOLOE는 외부 휴대 물건뿐 아니라 얼굴 주변과 의복·장면 범주도 출력한다. 얼굴 상자와의 겹침만으로 이를 물건 가림으로 해석하는 것은 잘못이다. 원시 후보를 보존해 문제를 드러냈다.',action='휴대 가능한 외부 물체 여부와 얼굴 가림 의미를 구분해야 한다. 152개 후보는 실제 행동 건수가 아니다.'),
 dict(id='O04',severity='종류 판별 불확실',frame='jack_5_000.jpg',title='작은 손 안 물건에 iphone 계열 라벨',detail='5.005초 YOLOE는 손 안의 작은 어두운 물건에 iphone 라벨을 붙였다. 위치 후보는 얻었지만 화면만으로 물건 종류를 확정하지 않았다. LLM에 라벨을 사실로 전달하면 문맥 판단까지 잘못될 수 있다.',action='objectLabel은 추정값으로 전달하고 실제 이미지 근거·불확실성을 함께 제공. LLM은 이번 실험에서 실행하지 않음.'),
 dict(id='Q01',severity='관찰량 부족',frame='jack_325_000.jpg',title='정면 비율 100%라도 관찰 시간은 0.6초',detail='325–335초 구간은 10초 중 0.6초만 정면 방향 판정이 가능했다. 비율은 1.0이지만 전체의 6%만 관찰한 값이다. 관찰 불가를 비정면으로 처리하지 않은 대신, 분모 선택에 따른 편향이 남는다.',action='coverageRatio를 비율과 함께 표시하고 최소 관찰 기준을 확정하기 전 점수 공개 금지.'),
 dict(id='Q02',severity='발표자 연결 한계',frame='jack_385_049.jpg',title='청중·카메라 전환 구간의 발표자 추적 미완성',detail='394.828초처럼 무대와 청중이 함께 보이는 장면에서는 발표자 관절과 얼굴 연결이 불가능했다. 큰 박스 선택과 다인물 제외는 신원 추적을 보장하지 않는다.',action='UNKNOWN 처리 유지. 다중 인물 환경을 지원하려면 발표자 추적 검증 필요.')]
(OUT/'error_review.json').write_text(json.dumps(dict(reviewType='Assistant visual spot review; not independent human ground truth',items=errors),ensure_ascii=False,indent=2))


def uri(path,mime):return 'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()
posters={}
for c in s['clips']:
 row=next(r for r in rows if r['clipId']==c['clipId'])
 posters[c['clipId']]={}
 for mode in ('baseline','hands','standard','open'):
  ok,buffer=cv2.imencode('.jpg',draw(row,mode),[cv2.IMWRITE_JPEG_QUALITY,80]);assert ok
  posters[c['clipId']][mode]='data:image/jpeg;base64,'+base64.b64encode(buffer).decode()
media={c['clipId']:{mode:uri(OUT/'videos'/f"{c['clipId']}_{mode}.mp4",'video/mp4') for mode in ('baseline','hands','standard','open')} for c in s['clips']}
error_html=''.join('<article class="error"><div><span class="pill">'+html.escape(e['severity'])+'</span><h3>'+e['id']+' · '+html.escape(e['title'])+'</h3><p>'+html.escape(e['detail'])+'</p><p class="action">'+html.escape(e['action'])+'</p></div><img loading="lazy" alt="'+html.escape(e['title'])+' 판정 표시 프레임" src="'+uri(OUT/'review'/e['frame'],'image/jpeg')+'"></article>' for e in errors)
clip_rows=''.join(f"<tr><td>{c['clipId']}</td><td>{c['sourceStartSec']:.0f}–{c['sourceEndSec']:.0f}s</td><td>{c['vision']['gaze']['observableSeconds']:.1f}s</td><td>{c['vision']['gaze']['frontFacingSeconds']:.1f}s</td><td>{c['vision']['gaze']['frontFacingRatio']*100:.1f}%</td><td>{c['vision']['handObservableSeconds']:.1f}s</td><td>{'null' if c['vision']['handStillSeconds'] is None else str(c['vision']['handStillSeconds'])+'s'}</td></tr>" for c in s['clips'])
time_rows=''.join(f'<tr><td>{name}</td><td>{s["timings"][key]["medianMs"]:.2f}</td><td>{s["timings"][key]["p95Ms"]:.2f}</td><td>{s["timings"][key]["totalSeconds"]:.2f}</td></tr>' for key,name in [('pose','YOLO11n-pose'),('face','YOLO5Face'),('hand','Hand Landmarker'),('standard','YOLO11n-seg'),('openVocabulary','YOLOE-11s-seg-pf')])
label_rows=''.join('<tr><td>'+html.escape(k)+'</td><td>'+str(v)+'</td></tr>' for k,v in sorted(s['counts']['openLabels'].items(),key=lambda x:-x[1])[:10])
source_html=''.join('<li><a href="'+x['commons_page']+'">'+html.escape(x['title'])+'</a> — '+x['creator']+' · <a href="'+x['license_url']+'">'+x['license']+'</a>. 이번 산출물은 발췌·축소·표본화 및 분석 표시를 추가한 무음 파생 영상.</li>' for x in manifest['items'])
hand_obs=sum(c['vision']['handObservableSeconds'] for c in s['clips'])
gaze_obs=sum(c['vision']['gaze']['observableSeconds'] for c in s['clips'])
front=sum(c['vision']['gaze']['frontFacingSeconds'] for c in s['clips'])
settings=html.escape(json.dumps(setup,ensure_ascii=False,indent=2))
clip_data=[dict(summary=c,frames=[{k:r[k] for k in ('startSec','sourceTimeSec','isCameraFacing','isBothHandsStill','handStillReason','gazeReason')} for r in rows if r['clipId']==c['clipId']]) for c in s['clips']]

page='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ProPitch Vision · 실측 실험 보고서</title><style>
:root{--ink:#182534;--muted:#586877;--paper:#f3f5f6;--line:#dbe3e8;--teal:#007c78;--amber:#a44a09;--red:#af3340}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;line-height:1.75}a{color:var(--teal)}header{background:#122a3a;color:white;padding:58px max(5vw,calc((100vw - 1160px)/2));}header .eyebrow{color:#77d9cd;letter-spacing:.16em;font-size:13px;font-weight:700}h1{font-size:clamp(30px,4vw,48px);line-height:1.25;letter-spacing:-.045em;margin:18px 0}header p{max-width:860px;color:#c9d7df}nav{display:flex;flex-wrap:wrap;gap:8px;margin-top:24px}nav a{color:white;text-decoration:none;border:1px solid #567181;border-radius:24px;padding:7px 15px;font-size:14px}main{max-width:1160px;padding:0 24px 60px;margin:auto}section{margin-top:38px;background:white;border:1px solid var(--line);border-radius:16px;padding:30px}h2{font-size:25px;letter-spacing:-.035em;margin:0 0 16px}h3{font-size:18px;margin:15px 0 8px}p{margin:10px 0}small,.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0}.card{background:#edf6f5;padding:20px;border-radius:12px}.card strong{display:block;font-size:30px;color:var(--teal)}.card span{font-size:13px}.notice{background:#fff4e9;border-left:4px solid #d77a30;border-radius:5px;padding:15px 18px;margin:18px 0}.good{background:#eaf6f3;border-color:var(--teal)}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:11px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}th{background:#eff3f5;white-space:nowrap}code{font-family:ui-monospace,monospace;font-size:.9em;background:#eef2f4;padding:2px 4px;border-radius:4px}pre{background:#142736;color:#d9e9ee;padding:20px;border-radius:10px;overflow:auto;max-height:500px;font-size:12px;line-height:1.6}.controls{display:flex;flex-wrap:wrap;align-items:end;gap:14px;margin:18px 0}label{font-weight:600;font-size:14px}select,button{font:inherit;padding:9px 12px;border:1px solid #aabac3;background:white;border-radius:7px;cursor:pointer;color:var(--ink)}select{display:block;margin-top:5px}button.primary{background:var(--teal);color:white;border-color:var(--teal)}button:focus-visible,select:focus-visible,a:focus-visible{outline:3px solid #efae42;outline-offset:3px}video{width:100%;max-height:680px;background:#0b1721;border-radius:10px}.pill{display:inline-block;padding:3px 10px;background:#fff1e4;color:#87460a;font-size:12px;border-radius:20px}.error{display:grid;grid-template-columns:1fr 1.1fr;gap:24px;border-top:1px solid var(--line);padding:25px 0}.error img{width:100%;height:auto;border-radius:8px}.action{color:var(--teal);font-size:14px}.timeline{display:flex;gap:2px;margin:8px 0 16px}.timeline button{padding:0;flex:1;height:25px;border:0;border-radius:2px;min-width:0}.yes{background:#00887e!important}.no{background:#c57935!important}.unknown{background:#d8dfe5!important}.legend{font-size:13px;color:var(--muted)}.flow{background:#eef5f6;padding:20px;border-radius:9px;font-weight:600;text-align:center}.two{display:grid;grid-template-columns:1fr 1fr;gap:22px}footer{padding:30px;text-align:center;color:var(--muted);font-size:13px}details{margin:15px 0}summary{cursor:pointer;font-weight:600}.key{font-size:13px;color:#4f6071}ul,ol{padding-left:24px}li{margin:7px 0}@media(max-width:740px){header{padding:32px 22px}main{padding:0 12px 30px}section{padding:20px 16px}.grid{grid-template-columns:1fr 1fr}.error,.two{grid-template-columns:1fr}h2{font-size:22px}.controls>*{width:100%}select{width:100%}.card strong{font-size:25px}}@media print{header{background:white;color:#182534}header p{color:#586877}nav,.controls,video,.timeline{display:none}section{break-inside:avoid;border:none}pre{max-height:none}.error{break-inside:avoid}}
</style></head><body><header><div class="eyebrow">PROPITCH / VISION EXPERIMENT 01–03</div><h1>실제로 무엇을 측정했고,<br>어디까지 믿을 수 있는가</h1><p>발표 영상에서 카메라 정면 방향과 양손 정지를 집계하고, 손·물건 모델의 추가 효과를 살펴본 CPU 실험입니다. 초보 독자도 측정값, 후보 사건, 확정 점수를 구분할 수 있도록 구성했습니다.</p><p>2026-11-10 · 공개 영상 2개 · 9개 구간 · 90초 / 450표본 · LLM 미실행</p><nav><a href="#findings">결과 요약</a><a href="#method">실험 방법</a><a href="#viewer">영상·JSON</a><a href="#models">모델 비교</a><a href="#errors">오류 검토</a><a href="#contract">백엔드 연결</a><a href="#validation">검증·재현</a></nav></header><main>
<section id="findings"><h2>01 · JSON 생성은 확인. 자동 채점 준비는 아직 아닙니다.</h2><div class="grid"><div class="card"><strong>9 / 9</strong><span>실측 클립 JSON 형식·의미 검증</span></div><div class="card"><strong>67.4초</strong><span>90초 중 얼굴 방향 관찰 가능</span></div><div class="card"><strong>31.0초</strong><span>양손목 + 연속 이력으로 정지 판정 가능</span></div><div class="card"><strong>0건</strong><span>실험 규칙상 양손 정지 사건</span></div></div><div class="notice"><b>0건은 “발표가 좋았다”는 뜻이 아닙니다.</b> 손을 관찰하지 못한 구간이 있고, 장시간 정지 양성의 독립 정답도 없습니다. 얼굴 가림·물건 접촉 후보 152개는 오검출을 포함하며 실제 행동 건수가 아닙니다. 모든 JSON에 <code>isScoringReady: false</code>를 명시했습니다.</div><ul><li><b>기존 YOLO:</b> 정면 비율·관찰 시간·사건 집계 경로를 구현했습니다. 손이 화면 밖인 경우에는 정지 0초 대신 null로 구분했습니다.</li><li><b>손 모델:</b> 손가락 위치가 추가되었으나 손목 기반 정지 판정 31.0초에 비해 손 전용 모델까지 평가 가능한 시간은 7.2초뿐입니다. 이번 표본으로 정확도 개선을 확인하지 못했습니다.</li><li><b>물건 모델:</b> 일반 YOLO는 무대 영역을 우산·연으로 잘못 출력했고, YOLOE는 의복·신체·장면 라벨까지 출력했습니다. 두 모델 모두 원시 출력을 곧바로 감점에 사용하기 어렵습니다.</li><li><b>시선:</b> 유효 시간 가중 집계는 53.8 / 67.4 = 79.8%입니다. 서로 다른 두 발표의 탐색 표본을 묶은 수치로, 개인의 시선 점수나 전체 영상 점수가 아닙니다.</li></ul></section>
<section id="method"><h2>02 · 처음 보는 분을 위한 실험 설명</h2><p>이 프로젝트는 발표 영상의 비언어 행동을 관찰하고, 그 근거를 JSON으로 채점 서버에 전달하는 기능을 만듭니다. YOLO Pose는 몸 관절, YOLO5Face는 얼굴 박스와 5개 특징점을 출력합니다. 이번에 손 21점 모델과 물건 분할 모델 2종을 추가로 실행했습니다.</p><div class="flow">영상 → 5 FPS 표본 → 몸·얼굴·손·물건 관찰 → 시간·후보 사건 집계 → JSON 검증<br><span class="muted">실제 감점·LLM 관련성 판단·공용 API 저장은 이번 실험 범위 밖</span></div><h3>입력과 비교 조건</h3><ul><li>Erik: 10–20초, 60–70초. Jack: 5–15초, 65–75초, 105–115초, 165–175초, 225–235초, 325–335초, 385–395초.</li><li>같은 450개 프레임을 모든 모델에 적용. 원본 종횡비 유지, 폭 960px로 저장. YOLO 입력은 640px. CPU, PyTorch 1스레드, 모델별 준비 실행 2회.</li><li>영상을 순차 디코딩하고 실제 프레임 시각(PTS)으로 표본 선택. 표본 시각과 목표 시각 차이는 0.1초 미만 검사. 0.2초 단위 시간 집계이므로 정확한 행동 경계는 아닙니다.</li><li>Hand Landmarker는 IMAGE 모드입니다. VIDEO 추적 모드의 속도·안정성을 평가한 결과가 아닙니다.</li><li>기존에 살펴본 영상과 썸네일 모음을 이용해 조건별 구간을 선택했습니다. 독립 holdout이 아니며, 새 정답 라벨 없이 전체 F1·정확도를 계산하지 않았습니다.</li></ul><h3>이번에 고정한 실험용 규칙</h3><div class="table-wrap"><table><thead><tr><th>항목</th><th>계산 방식</th><th>한계</th></tr></thead><tbody><tr><td>정면 방향</td><td>눈 사이 거리로 정규화한 코 좌우 편차 ≤0.18, 코의 눈–입 수직 위치 0.2–0.8, 얼굴 비율 0.3–1.3, 눈 선 기울기 ≤20°. 눈 사이 &lt;12px면 관찰 불가.</td><td>실제 yaw·pitch 각도나 눈동자 시선이 아님. 고개 숙임 오판 위험.</td></tr><tr><td>양손 정지</td><td>양 어깨·손목 신뢰도 ≥0.5. 최근 1초 6표본의 몸통 상대 손목 위치에서 최대 이동 범위 ≤어깨 너비의 0.04. 이 상태가 2초 이상 연속이면 사건.</td><td>손가락만의 움직임은 기본 규칙에 미반영. 관찰 누락·장면 전환에서 이력 초기화.</td></tr><tr><td>손 추가 비교</td><td>손 전용 모델의 손목과 몸 Pose 손목이 어깨 너비의 0.35 이내면 연결. 두 손 21점에 같은 1초 이동 규칙 적용.</td><td>관절 연결 오류·작은 손 미검출 가능. 추가 모델을 필수화하면 관찰량 감소.</td></tr><tr><td>가림 후보</td><td>손 특징점 볼록껍질 또는 물건 마스크가 얼굴 박스의 10% 이상 겹치는 구간, 0.4초 이상.</td><td>손 볼록껍질은 실제 손 마스크가 아님. 깊이·실제 가림 확정 불가.</td></tr><tr><td>물건 상호작용 후보</td><td>손 점이 물건 박스에서 어깨 너비의 0.12 이내인 구간, 0.4초 이상. 모델·종류별로 연속 구간 병합.</td><td>함께 움직임·접촉의 검증은 미구현. 같은 종류의 다른 물건을 분리 추적하지 않음.</td></tr></tbody></table></div><p class="muted">출력을 본 후 좋은 결과가 나오도록 임계값을 재탐색하지 않았습니다. 관찰 불가 null 처리와 정수 좌표 입력 오류 등 구현 버그만 수정했습니다. 이 설정은 승인된 ACTIVE 루브릭이 아닙니다.</p></section>
<section id="viewer"><h2>03 · 실측 영상과 JSON 직접 확인</h2><p>구간과 표시 모델을 선택하세요. 영상은 원본의 10초를 5 FPS로 표본화한 무음 확인용 영상입니다. JSON의 시간은 원본 기준이고, 플레이어의 0초는 선택 구간의 시작입니다. 영상은 이 HTML 안에 포함되어 인터넷 연결 없이 재생할 수 있습니다.</p><div class="controls"><label>구간<select id="clipSelect"></select></label><label>표시 모델<select id="modeSelect"><option value="baseline">기존 몸·얼굴만</option><option value="hands">기존 + 손 특징점</option><option value="standard">기존 + 손 + YOLO11n-seg</option><option value="open">기존 + 손 + YOLOE</option></select></label><button id="downloadJson" class="primary">선택 구간 JSON 저장</button></div><video id="player" controls playsinline preload="metadata" aria-label="모델 판정 표시 영상"></video><p class="key">청록: 몸 관절 · 노랑: 얼굴 5점 · 자홍 점: 손 21점 · 초록 N: 일반 물건 모델 · 연자홍 E: YOLOE. 영상 하단의 NO SCORE는 실제 점수를 계산하지 않았다는 뜻입니다.</p><div id="clipStats" aria-live="polite"></div><p class="legend">시간별 판정 — 청록 YES / 주황 NO / 회색 관찰 불가. 막대를 누르면 해당 시점으로 이동합니다. 양손 정지 YES는 후보 창 상태이며, 2초 사건 조건은 별도로 적용합니다.</p><b>카메라 정면</b><div id="gazeTimeline" class="timeline"></div><b>양손 정지</b><div id="handTimeline" class="timeline"></div><details><summary>선택 구간 전체 JSON 펼치기</summary><pre id="jsonView"></pre></details><h3>구간별 실측 요약</h3><div class="table-wrap"><table><thead><tr><th>구간</th><th>원본 시간</th><th>얼굴 유효</th><th>정면</th><th>정면 비율</th><th>손 정지 판정 가능</th><th>정지 사건 시간</th></tr></thead><tbody>__CLIP_ROWS__</tbody></table></div><p class="muted">예: jack_325의 100%는 0.6초 / 0.6초입니다. 전체 10초 중 관찰률은 6%이므로 이를 100점으로 공개하면 안 됩니다. 빈 gestureEvents는 관찰 여부와 함께 해석해야 합니다.</p></section>
<section id="models"><h2>04 · 손 모델과 물건 모델 비교</h2><h3>실험 2 — 손 모델은 정보를 추가했지만 개선은 입증하지 못함</h3><div class="table-wrap"><table><thead><tr><th>관찰</th><th>결과</th><th>해석</th></tr></thead><tbody><tr><td>손 모델 출력이 있는 프레임</td><td>184 / 450 (40.9%)</td><td>검출 정답률이 아니라 출력 빈도</td></tr><tr><td>몸 손목과 연결된 손이 있는 프레임</td><td>157 / 450 (34.9%)</td><td>손·발표자 연결 규칙의 통과 수</td></tr><tr><td>양손이 모두 연결된 프레임</td><td>103 / 450 (22.9%)</td><td>시간 이력을 갖추기 전의 양손 관찰</td></tr><tr><td>두 방법 모두 정지 판정 가능</td><td>36프레임 = 7.2초</td><td>기본 손목 방식 31.0초보다 관찰 범위 작음</td></tr><tr><td>공통 판정의 불일치</td><td>0 / 36</td><td>둘 다 움직임으로 판단. 정지 양성 성능을 확인하지 못함</td></tr><tr><td>얼굴 접근 YES</td><td>손목 1프레임 / 손 모델 0프레임</td><td>관찰 분모가 다르고 정답이 없어 성능 우열로 해석 불가</td></tr></tbody></table></div><p><b>판단:</b> 기본 손목 정지를 유지하고 손 모델을 보조 관찰로만 사용할 근거는 있습니다. 손 모델이 정확도를 높였다는 결론은 낼 수 없습니다. 특히 손이 잘린 영상에는 모델을 추가해도 정보가 생기지 않습니다.</p><h3>실험 3 — 특정 물건 이름을 지정하지 않는 YOLOE도 자동 해답은 아님</h3><p>YOLO11n-seg는 COCO 80종, YOLOE-11s-seg-pf는 프롬프트 없는 4,585개 이름 어휘를 사용했습니다. 물건 후보는 신뢰도 0.25 이상으로 동일하게 실행했습니다. 사람의 기본 라벨 일부만 제외했으며 의복·신체·장면 범주를 완전히 분리하지 못하는 문제를 그대로 기록했습니다. 두 모델은 크기·어휘·구조가 달라 공정한 아키텍처 우열 실험은 아닙니다.</p><div class="two"><div><h3>YOLO11n-seg</h3><p>이번 출력에는 remote·mouse·microphone이 없습니다. 기본 클래스 자체에 microphone이 없고, 손 안의 작은 물건도 안정적으로 잡지 못했습니다. 무대 배경의 umbrella·kite 오검출을 육안 확인했습니다.</p><p><b>현재 결정:</b> CPU 기준선으로 유지 가능. 물건 가림·접촉 자동 감점에는 채택 보류.</p></div><div><h3>YOLOE-11s-seg-pf</h3><p>작은 손 안 물건 후보와 다양한 영역을 찾았지만 neckband·haircut·장면 이름 등의 출력이 많았습니다. microphone 출력 2회도 올바른 마이크 검출이라고 검증한 수치가 아닙니다.</p><p><b>현재 결정:</b> 검출 범위가 넓다는 이유만으로 선택하지 않음. 후보 정제와 별도 정답 평가가 필요.</p></div></div><details><summary>YOLOE 상위 원시 라벨 빈도 — 실제 물건 수가 아님</summary><table><thead><tr><th>라벨</th><th>모든 프레임의 검출 인스턴스 합</th></tr></thead><tbody>__LABEL_ROWS__</tbody></table></details><h3>CPU 처리시간</h3><div class="table-wrap"><table><thead><tr><th>모듈</th><th>중앙값 ms / 표본</th><th>P95 ms / 표본</th><th>450표본 합계 초</th></tr></thead><tbody>__TIME_ROWS__</tbody></table></div><p>측정은 모델 호출의 전처리·추론·출력 변환을 포함합니다. 영상 디코딩, JPEG 읽기·쓰기, 모델 로딩, 집계와 영상 인코딩은 제외했습니다. Apple M5 CPU에서 고정 순서로 한 번 실행한 관측값이며 반복 실행의 변동·GPU·서버 환경을 검증하지 않았습니다. 5 FPS 표본 처리 속도를 원본 30 FPS 실시간 처리 보장으로 해석하면 안 됩니다.</p></section>
<section id="errors"><h2>05 · 실제 오류·오감점 위험 검토</h2><p>아래는 조수가 출력을 본 뒤 선택한 장면의 육안 검토입니다. 독립된 사람 정답 주석이 아니므로 정밀도·재현율·F1의 근거로 사용하지 않습니다. 확정 오검출과 미확정 위험, 정상 관찰 불가 처리를 구분했습니다.</p>__ERRORS__</section>
<section id="contract"><h2>06 · JSON과 백엔드 규칙의 연결</h2><p>기존 제안의 <code>vision.gaze</code>, <code>handObservableSeconds</code>, <code>handStillSeconds</code>, <code>gestureEvents</code>, <code>criterionStatus</code>, <code>limitations</code>를 유지했습니다. 새 값은 이번 실험 스키마에만 추가했으며 공용 API의 승인된 필드로 간주하지 않습니다.</p><div class="table-wrap"><table><thead><tr><th>필드</th><th>의미·추가 이유</th></tr></thead><tbody><tr><td><code>sourceStartSec / sourceEndSec</code></td><td>원본 영상 구간. 사건 시각과 플레이어 상대 시각의 혼동 방지.</td></tr><tr><td><code>gaze.coverageRatio</code></td><td>클립 전체 중 방향을 판정할 수 있었던 시간 비율. 정면 비율과 반드시 함께 표시.</td></tr><tr><td><code>bothWristsVisibleSeconds</code></td><td>양손목·어깨가 보이는 시간. 1초 이력을 확보한 handObservableSeconds와 구분.</td></tr><tr><td><code>handStillSeconds: null</code></td><td>정지 판정 가능 시간이 0일 때. 관찰한 결과 정지 사건이 없는 0초와 구별.</td></tr><tr><td><code>candidateEvents</code></td><td>얼굴 겹침·물건 근접 후보. 실제 감점 gestureEvents와 분리. 물건 관련성 LLM에 넘기기 전 검증이 필요.</td></tr><tr><td><code>CANDIDATE_ONLY</code></td><td>모델 출력 후보는 있으나 실제 가림 판정은 미검증.</td></tr><tr><td><code>PENDING_CONTEXT_JUDGMENT</code></td><td>물건의 발표 관련성 판단을 실행하지 않음. 해당함·해당하지 않음 어느 쪽도 아님.</td></tr><tr><td><code>isScoringReady: false</code></td><td>검증되지 않은 실험 관찰값을 최종 점수로 공개하지 않도록 명시.</td></tr><tr><td><code>observations.json</code></td><td>450표본의 관찰값·null 사유·박스·특징점·모델별 시간. 재검토용 원자료이며 서비스 DB 전량 저장 제안이 아님.</td></tr></tbody></table></div><div class="notice good"><b>백엔드 원칙 유지:</b> analysis가 서비스 DB를 직접 쓰지 않음 · 관찰과 점수 분리 · 규칙 점수를 LLM이 변경하지 않음 · 관찰 불가를 0점/100점으로 대체하지 않음 · 실제 영상·전사 외부 전송 없음 · 공용 코드·계약·의존성 변경 없음.</div><p>현재 최종 Report는 네 항목 정수 점수가 모두 필요합니다. 이 실험 JSON은 worker 내부 관찰 초안이며 DONE 리포트로 직접 제출할 수 없습니다. 채점 임계값·최소 관찰량·필수/선택 정책을 먼저 확정하고 모델·Schema·예시·테스트를 함께 반영해야 합니다.</p></section>
<section id="validation"><h2>07 · 검증 범위와 재현 방법</h2><div class="notice good"><b>통과:</b> JSON Schema 9개 · 잘못된 비율 입력 거부 3개 · 합성 경계 검사 10개 · 실제 450프레임의 null 사유·시간 합계 검사 · H.264 영상 36개 / 1,800프레임 디코딩.</div><p>합성 검사는 관찰 끊김이 정지 사건을 분리하는지, 2초 미만 사건이 제외되는지, 손이 움직였다 돌아와도 정지로 처리하지 않는지, 정면 기하 계산과 영역 계산을 확인했습니다. 이는 실제 행동의 정확도 검증을 대신하지 않습니다.</p><h3>지금 확인하지 못한 것</h3><ul><li>사람이 주석한 정면·정지·가림·접촉의 독립 정답과 구간별 F1.</li><li>확실한 장시간 양손 정지, 물건으로 실제 얼굴을 가리는 양성 장면. 현재 자료에 충분한 양성이 있는지조차 확정하지 않음.</li><li>발표와 무관한 물건의 의미 판단, LLM 호출, 실제 감점과 종합 점수.</li><li>안정적인 발표자 ID 추적, 실제 물건 접촉/들기 판정, 손·물건의 공통 3D 깊이.</li><li>다른 발표자·카메라·조명에서의 일반화, 서버·GPU 성능.</li></ul><h3>다음 실험의 우선순위</h3><ol><li>고정 카메라에서 정면/고개 숙임, 양손 정지/손가락만 움직임, 손·물건 얼굴 가림/얼굴 옆 제스처를 분리한 짧은 촬영 자료 확보.</li><li>조정용과 최종 확인용을 분리해 사람이 사건 구간과 관찰 불가를 표시. 정지·가림 양성이 없는 현재 자료만으로 임계값을 맞추지 않음.</li><li>물건은 무제한 원시 라벨을 LLM에 넘기기보다 실제 손에 연결된 외부 물체 후보인지 먼저 검증. YOLOE의 텍스트/시각 프롬프트 변형은 아직 미시험.</li><li>정제된 후보와 허용된 문맥을 LLM에 전달하는 계약을 합성 데이터로 먼저 검증. 실제 전사·영상 프롬프트 사용 규칙은 별도 합의.</li></ol><details><summary>실행 설정 전체</summary><pre>__SETUP__</pre></details><p>번들에는 원시 관찰 JSON, 클립별 JSON, JSON Schema, 검증 기록, 오류 검토, 실행 스크립트, 확인 영상이 포함됩니다. 모델 가중치·원본 영상·라이브러리는 포함하지 않습니다. HTML 안의 동영상은 별도 파일 없이 재생되며, 아래 버튼으로 집계 JSON과 스키마를 저장할 수 있습니다.</p><div class="controls"><button id="downloadSummary">전체 집계 JSON 저장</button><button id="downloadSchema">JSON Schema 저장</button></div><pre>기존 실험 Python 환경에서 실행 (저장소 루트 기준):
python visual_test/vision_study.py
python visual_test/summarize_vision_study.py
python visual_test/build_vision_report.py

주의: 기존 OLD_ROOT 가중치·YOLO5Face vendor 경로가 필요합니다.
Hand Landmarker, YOLO11n-seg, YOLOE-11s-seg-pf 가중치는 visual_test/models에 둡니다.
report 빌드에는 격리 설치한 jsonschema가 필요합니다.</pre><h3>영상 출처와 모델 근거</h3><ul>__SOURCES__<li><a href="https://docs.ultralytics.com/models/yolo11/">Ultralytics YOLO11</a> · <a href="https://github.com/deepcam-cn/yolov5-face">YOLO5Face</a> · <a href="https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker">Hand Landmarker</a> · <a href="https://docs.ultralytics.com/models/yoloe/">YOLOE</a></li></ul><p class="muted">출처·라이선스 표시는 기존 다운로드 manifest를 기준으로 보존했습니다. Erik 파생 확인 영상에는 CC BY-SA 4.0, Jack 파생 확인 영상에는 CC BY 2.5 출처 조건을 유지합니다.</p></section></main><footer>ProPitch · Vision 실험 기록 · 실측 출력과 검증되지 않은 판단을 분리합니다.</footer>
<script>
const clips=__CLIPS__,media=__MEDIA__,posters=__POSTERS__,summaryData=__SUMMARY__,schemaData=__SCHEMA__;
const select=document.getElementById('clipSelect'),mode=document.getElementById('modeSelect'),player=document.getElementById('player');
for(const c of clips){const o=document.createElement('option');o.value=c.summary.clipId;o.textContent=`${c.summary.clipId} · ${c.summary.sourceStartSec}–${c.summary.sourceEndSec}s`;select.appendChild(o)}
select.value='jack_5';
function save(name,data){const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}
function selected(){return clips.find(c=>c.summary.clipId===select.value)}
function update(){const c=selected(),s=c.summary,v=s.vision,g=v.gaze;player.poster=posters[s.clipId][mode.value];player.src=media[s.clipId][mode.value];document.getElementById('jsonView').textContent=JSON.stringify(s,null,2);document.getElementById('clipStats').textContent=`正面 비율 ${(g.frontFacingRatio*100).toFixed(1)}% · 얼굴 관찰률 ${(g.coverageRatio*100).toFixed(0)}% · 손 판정 가능 ${v.handObservableSeconds.toFixed(1)}초 · 정지 ${v.handStillSeconds===null?'관찰 불가':v.handStillSeconds+'초'} · 감점 사건 ${v.gestureEvents.length}개 · 후보 ${v.candidateEvents.length}개`;
for(const [id,key] of [['gazeTimeline','isCameraFacing'],['handTimeline','isBothHandsStill']]){const el=document.getElementById(id);el.replaceChildren();for(const f of c.frames){const b=document.createElement('button'),state=f[key]===null?'관찰 불가':f[key]?'YES':'NO';b.className=f[key]===null?'unknown':f[key]?'yes':'no';b.title=`원본 ${f.sourceTimeSec.toFixed(3)}초: ${state}`;b.setAttribute('aria-label',b.title);b.onclick=()=>{player.currentTime=f.startSec-s.sourceStartSec;};el.appendChild(b)}}}
select.onchange=update;mode.onchange=update;document.getElementById('downloadJson').onclick=()=>save(select.value+'.json',selected().summary);document.getElementById('downloadSummary').onclick=()=>save('summary.json',summaryData);document.getElementById('downloadSchema').onclick=()=>save('vision-experiment.schema.json',schemaData);update();
</script></body></html>'''
replacements={'__CLIP_ROWS__':clip_rows,'__TIME_ROWS__':time_rows,'__LABEL_ROWS__':label_rows,'__ERRORS__':error_html,'__SETUP__':settings,'__SOURCES__':source_html,'__CLIPS__':json.dumps(clip_data,ensure_ascii=False),'__POSTERS__':json.dumps(posters),'__MEDIA__':json.dumps(media),'__SUMMARY__':json.dumps(s,ensure_ascii=False),'__SCHEMA__':json.dumps(schema,ensure_ascii=False)}
for token,value in replacements.items():page=page.replace(token,value)
page=page.replace('正面 비율','정면 비율')
example=s['clips'][2]
assert example['clipId']=='jack_5'
actual=json.loads(json.dumps(example))
chosen=next(e for e in actual['vision']['candidateEvents'] if e.get('objectLabel')=='smartphone')
excerpt={'vision':{**actual['vision'],'candidateEvents':[chosen]},'isScoringReady':actual['isScoringReady']}
proposal={
 'schemaVersion':'VISION_CONTRACT_DRAFT_NOT_IMPLEMENTED',
 'observationConfigVersion':None,
 'isScoringReady':False,
 'vision':{
  'gaze':actual['vision']['gaze'],
  'handObservableSeconds':6.4,'handStillSeconds':0,'bothWristsVisibleSeconds':7.4,
  'gestureEvents':[],
  'unobservableIntervalsStatus':'NOT_GENERATED','unobservableIntervals':[],
  'candidateEvents':[{'eventId':chosen['eventId'],'kind':'OBJECT_INTERACTION_CANDIDATE',
   'startSec':chosen['startSec'],'endSec':chosen['endSec'],
   'objectLabel':chosen['objectLabel'],'objectLabelConfidence':None,
   'confidence':None,'observationMethod':'HAND_POINTS_TO_OBJECT_BOX_PROXIMITY',
   'evidenceRefs':['evidence-example-1']}]
 },
 'evidence':[{'evidenceId':'evidence-example-1','sourceType':'VISION',
  'startSec':chosen['startSec'],'endSec':chosen['endSec'],
  'description':'기존 후보의 시간 참조만 제공. 물건 접촉·종류를 확정한 근거가 아님.'}],
 'contextJudgments':[{'criterionKey':'UNRELATED_OBJECT_TOUCH',
  'status':'NOT_RUN','verdict':None,'reason':'LLM_NOT_EXECUTED',
  'evidenceRefs':['evidence-example-1']}],
 'limitations':['신규 계약 설계 예시이며 실행 결과 아님','관찰 설정 버전과 물건 라벨 신뢰도 집계 미확정','LLM 문맥 전달 정책 미확정']
}
appendix=(ROOT/'vision_report_appendix.html').read_text()
for token,value in {
 '__EXAMPLE_IMAGE__':posters['jack_5']['baseline'],
 '__ACTUAL_EXCERPT__':html.escape(json.dumps(excerpt,ensure_ascii=False,indent=2)),
 '__ACTUAL_FULL__':html.escape(json.dumps(actual,ensure_ascii=False,indent=2)),
 '__PROPOSED_JSON__':html.escape(json.dumps(proposal,ensure_ascii=False,indent=2))
}.items():appendix=appendix.replace(token,value)
page=page.replace('</main>',appendix+'</main>')
page=page.replace('<a href="#validation">검증·재현</a>', '<a href="#validation">검증·재현</a><a href="#next-contract">실제 JSON·다음 결정</a>')
(OUT/'proposed_contract_example.json').write_text(json.dumps(proposal,ensure_ascii=False,indent=2))
report=OUT/'ProPitch_Vision_실측_실험보고서.html';report.write_text(page)
# Store checkpoint hashes rather than copying model binaries into the report bundle.
weights={}
for path in (ROOT/'models').glob('*'):
 if path.is_file():weights[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
(OUT/'model_hashes.json').write_text(json.dumps(weights,indent=2))
print(json.dumps(dict(report=str(report),bytes=report.stat().st_size,checks=checks),ensure_ascii=False,indent=2))
