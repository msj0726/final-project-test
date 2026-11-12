import sys,json,html,base64,copy
from pathlib import Path
import cv2,numpy as np
sys.path.insert(0,str(Path.cwd()/'backend'))
from analysis.modules.vision.observation import _polygon_overlap,_face_direction,_events
root=Path('visual_test/results/example_video_comparison')
rows=json.loads((root/'raw.json').read_text()); result=json.loads((root/'yolo_hand.json').read_text())
def dump(x):return html.escape(json.dumps(x,ensure_ascii=False,indent=2))
def embed(p):return 'data:image/jpeg;base64,'+base64.b64encode(p.read_bytes()).decode()
flags=[]; excluded=[]; remaining=[]
for r in rows:
 face=r['face']; hand=bool(face) and any((_polygon_overlap(cv2.convexHull(np.array(h,dtype=np.float32)).reshape(-1,2).tolist(),face['box']) or 0)>=.1 for h in r['hands'])
 obj=bool(face) and any((_polygon_overlap(o.get('polygon',[]),face['box']) or 0)>=.1 for o in r['objects'])
 flags.append(hand); direction,_=_face_direction(face)
 if direction is not None and (hand or obj):excluded.append(r)
 elif direction is not None:remaining.append((r,direction))
extension={'schemaVersion':'vision-occlusion-extension-proposal','isProductionContract':False,'handFaceOverlapCandidates':_events(rows,flags,'HAND_FACE_OVERLAP_CANDIDATE',.4),'gazeExclusionExperiment':{'method':'HAND_HULL_OR_OBJECT_POLYGON_FACE_OVERLAP_GE_0_1','excludedObservableSeconds':round(len(excluded)*.2,2),'observableSeconds':round(len(remaining)*.2,2),'frontFacingSeconds':round(sum(v for _,v in remaining)*.2,2),'frontFacingRatio':sum(v for _,v in remaining)/len(remaining) if remaining else None}}
(root/'occlusion_extension.json').write_text(json.dumps(extension,ensure_ascii=False,indent=2))
# shortcut: projected hand hull is a candidate, not depth-tested occlusion; upgrade after labeled validation.
assert all(e['endSec']>e['startSec'] for e in extension['handFaceOverlapCandidates'])
assert len(remaining)+len(excluded)==round(result['vision']['gaze']['observableSeconds']/.2)
import unicodedata
video=next(p for p in Path('/Users/minseojang/Downloads').glob('*.mov') if unicodedata.normalize('NFC',p.name)=='예시.mov')
cap=cv2.VideoCapture(str(video)); scenes=[]
notes={10:'손이 얼굴을 덮는 장면. 손 검출과 얼굴 검출이 동시에 남아도 실제 시선은 판정하기 어렵다.',23:'양손을 턱 아래에 둔 장면. cell phone 0.39가 검출되지만 이 장면에서 휴대폰으로 볼 근거가 없다. 정지 여부는 연속 5초 라벨이 필요하다.',32:'뒤 사람의 손도 등장한다. 발표자 몸통을 선택하지 못해 얼굴도 연결되지 않았다. 검출한 두 손이 발표자 양손이라는 보장이 없다.',36:'컵을 들고 있지만 wine glass로 분류. 물건 검출과 정확한 종류 판정은 별개이며 발표자 연결도 실패했다.',46:'휴대폰이 얼굴을 가리는 장면. cell phone 검출과 44.8–49.0초 얼굴 겹침 후보가 생성되어 이 사례는 포착했다.',55:'초록색 포장 물건을 휴대폰으로 오인. YOLOE도 iphone 등 여러 이름을 출력해 종류 안정성이 확인되지 않았다.',58:'펜으로 보이는 가는 물건을 들고 있지만 해당 표본에서 기존 물건 모델은 검출하지 못했다.'}
for t,note in notes.items():
 r=min(rows,key=lambda x:abs(x['startSec']-t));cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,im=cap.read();assert ok
 if r['face']:
  x1,y1,x2,y2=map(int,r['face']['box']);cv2.rectangle(im,(x1,y1),(x2,y2),(0,220,0),3)
  for p in r['face']['points']:cv2.circle(im,tuple(map(int,p)),5,(0,220,0),-1)
 if r['body']:
  for i in (5,6,9,10):
   if r['body']['confidence'][i]>=.5:cv2.circle(im,tuple(map(int,r['body']['points'][i])),9,(255,100,0),-1)
 for hand in r['hands']:
  for p in hand:cv2.circle(im,tuple(map(int,p)),4,(255,0,255),-1)
 for o in r['objects']:
  x1,y1,x2,y2=map(int,o['box']);cv2.rectangle(im,(x1,y1),(x2,y2),(0,180,255),3);cv2.putText(im,o['label'],(x1,max(25,y1)),cv2.FONT_HERSHEY_SIMPLEX,1,(0,120,255),2)
 p=root/f'scene_{t}.jpg';cv2.imwrite(str(p),cv2.resize(im,(810,540)))
 scenes.append(f'<article><h3>{t}초</h3><img src="{embed(p)}"><p>{note}</p><p>손 {len(r["hands"])}개 · 연결된 얼굴 {bool(r["face"])} · 연결된 몸통 {bool(r["body"])}</p></article>')
cap.release()
meaning={
'schemaVersion':'출력 구조의 버전. 정식 Report API가 아닌 실험 관찰 계약이다.','observationConfigVersion':'정지·추적 등 계산 규칙 버전. 손 모델 추가 여부를 모두 표현하지 못하므로 실행 조합도 별도 보관해야 한다.','sourceStartSec':'분석 시작 시각(초).','sourceEndSec':'표본 구간 종료(초). 원본 약 62.74초보다 마지막 0.2초 표본 때문에 약 0.06초 길다.','sampleDurationSeconds':'현재 계산 분모인 표본 길이. 마지막 구간을 원본 길이에 맞춰 자르는 후속 수정이 필요하다.','isScoringReady':'false: 점수로 확정하지 않고 루브릭에 관찰 근거만 전달한다.',
'observableSeconds':'얼굴 5점으로 방향 판정이 가능했던 시간. 현재 JSON에는 가림 후보 제외가 아직 적용되지 않았다.','frontFacingSeconds':'판정 가능한 시간 중 얼굴 기하가 정면 조건을 만족한 시간.','frontFacingRatio':'frontFacingSeconds / observableSeconds. 실제 청중 또는 Zoom 화면을 보는 비율이 아니다.','coverageRatio':'얼굴 판정 가능 시간 / 62.8초.','method':'눈동자가 아닌 얼굴 5점의 기하로 정면을 추정한 방법.',
'handObservableSeconds':'양쪽 손목·어깨를 관찰하고 시간 이력을 확보해 정지 여부를 계산한 시간.','handStillSeconds':'연속 5초 조건을 통과한 양손 정지 사건의 합. 0은 관찰한 범위의 사건 없음이며 영상 전체에 정지가 없다는 뜻이 아니다.','bothWristsVisibleSeconds':'시간 이력 준비 전도 포함한 양손목 관찰 시간.','handCoverageRatio':'handObservableSeconds / sampleDurationSeconds.','gestureEvents':'확정 규칙을 충족한 정지 사건 목록. 이번에는 빈 배열이다.','candidateEvents':'가림·물건 상호작용의 미확정 후보 목록.',
'eventId':'사건 식별자.','kind':'사건 종류. OBJECT_FACE_OVERLAP_CANDIDATE는 물건 마스크와 얼굴 박스의 2차원 겹침이다.','startSec':'해당 사건 또는 관찰 불가 구간의 시작(초).','endSec':'해당 구간의 끝(초, 종료 경계).','confidence':'행동 확률을 보정하지 않았으므로 null. 물건 분류 신뢰도와 다르다.','evidenceRefs':'evidence 배열의 근거 ID 연결.','objectTrackId':'이번 분석 내부의 물건 추적 ID. 전역 ID나 사람 ID가 아니다.','objectLabel':'YOLO가 예측한 물건 종류. 실제 물건 정답으로 취급하면 안 된다.','objectLabelConfidence':'해당 사건의 물건 검출 confidence 중앙값. 0.577은 행동이 57.7% 확실하다는 뜻이 아니다.',
'nearWristDetectionCount':'손목 근처로 분류된 개별 물건 검출 건수.','insufficientHistoryCount':'근접 검출 중 동반 이동 이력이 부족한 건수.','motionMismatchCount':'손목과 물건 이동이 맞지 않은 건수.','insufficientMotionCount':'함께 움직이는지 계산하기에 이동량이 부족한 건수.','comovingDetectionCount':'동반 이동 조건을 만족한 검출 건수.','unit':'시간·사건 수가 아닌 검출 인스턴스 수라는 명시.',
'unobservableIntervalsStatus':'관찰 불가 구간 목록이 생성됐음을 표시.','criterionKey':'구간 또는 판단이 속한 평가 기준.','reasonCode':'NO_ASSOCIATED_FACE: 발표자 얼굴 연결 실패; NO_BODY: 몸통 선택 실패; WRISTS_OR_SHOULDERS_UNOBSERVABLE: 손목/어깨 관찰 부족; TEMPORAL_WARMUP: 시간 이력 부족.',
'HAND_STILLNESS':'EVALUATED는 일부 관찰 구간을 계산했다는 뜻이며 전체 영상 검증 완료가 아니다.','FACE_OCCLUSION':'CANDIDATE_ONLY: 겹침 후보만 제공한다.','UNRELATED_OBJECT_TOUCH':'NOT_EVALUATED: 발표 관련성은 아직 판정하지 않았다.','evidenceId':'사건이 참조하는 근거 식별자.','sourceType':'VISION: 영상에서 나온 근거.','description':'이 근거가 무엇을 관찰했고 무엇을 확정하지 않았는지 설명.','status':'NOT_RUN: LLM 판단을 실행하지 않았다.','verdict':'null: 관련/무관 결론이 없다.','reason':'LLM_NOT_EXECUTED: 문맥 판단을 실행하지 않음.','limitations':'점수 보류, 손목 기준, 실제 시선·가림·관련성 미확정, 추적 누락 비보간 및 손 연결 실험의 한계.'}
fields=[]
def walk(v,path=''):
 if isinstance(v,dict):
  for k,x in v.items():walk(x,path+'.'+k if path else k)
 elif isinstance(v,list) and v:
  if isinstance(v[0],dict):
   for i,x in enumerate(v):walk(x,f'{path}[{i}]')
  else:fields.append((path,v))
 else:fields.append((path,v))
walk(result)
def glossary():
 out=[]
 for p,v in fields:
  key=p.split('.')[-1].split('[')[0];out.append('<tr><td>'+html.escape(p)+'</td><td>'+dump(v)+'</td><td>'+meaning.get(key,'빈 목록: 이번 실행에서 해당 근거 또는 사건이 생성되지 않았다.')+'</td></tr>')
 return ''.join(out)
comparisons=[]
for name,label in [('baseline','기존 YOLO 조합'),('yolo_hand','기존 + MediaPipe Hands'),('mp_pose_hand','몸 관절 대체 + Hands (기존 몸통 선택 유지)')]:
 d=json.loads((root/(name+'.json')).read_text())['vision'];comparisons.append(f'<tr><td>{label}</td><td>{d["handObservableSeconds"]}</td><td>{d["bothWristsVisibleSeconds"]}</td><td>{d["handStillSeconds"]}</td><td>{len(d["gestureEvents"])}</td></tr>')
report='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>예시 영상 모델 비교 실험</title><style>body{overflow-wrap:anywhere;font:16px/1.7 system-ui,sans-serif;background:#f2f5fa;color:#172338;margin:0}main{max-width:1100px;margin:auto;padding:24px}section,article{background:white;padding:24px;margin:20px 0;border-radius:14px}h1,h2,h3{line-height:1.35}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#102039;color:#dcecff;padding:20px;border-radius:10px;font-size:13px}img{max-width:100%;height:auto}table{table-layout:fixed;border-collapse:collapse;width:100%;font-size:14px}td,th{padding:10px;border:1px solid #d5dfea;text-align:left;overflow-wrap:anywhere}td:first-child{max-width:350px}.scroll{overflow:auto}.notice{border-left:5px solid #e29436;padding:15px;background:#fff3df}a{color:#075db7}</style><main><h1>예시.mov — 추가 모델과 행동 판정 실험</h1><p>결론: 손 검출은 늘었지만 세 행동을 모두 신뢰성 있게 판정하는 수준은 아니다. 휴대폰 얼굴 겹침은 포착했고, 정지 사건은 0건이며, 발표 무관 물건 판단은 실행하지 않았다.</p><section><h2>1. 실제 JSON 전체 — 기존 조합 + MediaPipe Hands</h2><p>314개 표본, 5 FPS, 표본 길이 62.8초. 아래는 실제 yolo_hand.json이며 생략하지 않았다. 손 가림·시선 제외 확장 제안은 5절에 별도로 표시한다.</p><pre>'''+dump(result)+'''</pre></section><section><h2>2. 결과를 어떻게 읽어야 하나</h2><div class="scroll"><table><tr><th>조합</th><th>양손 판정 시간(초)</th><th>양손목 관찰(초)</th><th>5초 정지 합(초)</th><th>정지 사건</th></tr>'''+''.join(comparisons)+'''</table></div><p class="notice"><strong>사용자 확인 정답: 21–27초는 양손 정지 구간.</strong> 해당 30개 표본 중 현재 규칙의 정지 판정은 11개(21.6–23.8초, 2.2초 연속)뿐이다. 23.8–27.0초는 손목의 어깨 대비 이동이 임계값 0.04를 넘는 것으로 계산되어 false였다. 따라서 5초 사건 0건은 이 정답 구간의 명백한 누락이다. 임계값·손 연결·미세 움직임의 기여는 추가 확인이 필요하다.</p><p>MediaPipe는 한 손 이상 257/314프레임(81.8%), 두 손 81/314프레임(25.8%)에서 검출했다. 이 수치는 정확도나 발표자 손 검출 재현율이 아니다. 손을 찾더라도 발표자 몸통·어깨·양손 연결과 시간 이력이 있어야 정지를 계산한다. 손 추가로 판정 시간이 1.2초 늘었지만 정확도가 좋아졌다는 증거는 아니다.</p><p>얼굴 방향은 49.4초 중 42초가 정면 조건을 만족해 85.02%이다. 화면 속 청중을 보는지도 Y로 인정하는 사용자 기준과 이 수치는 같지 않다. 손·휴대폰에 가려진 얼굴에서도 특징점이 출력될 수 있어 가림 제외 전 값은 시선 접촉 점수로 사용할 수 없다.</p><p>물건 상호작용 후보는 0건. 손목 근처 검출 1건도 이력 부족으로 탈락했다. 따라서 휴대폰·컵·포장·펜을 들거나 만지는 행동 전체를 잡았다고 말할 수 없다. LLM 발표 관련성은 NOT_RUN이다.</p><p class="notice">새로 확인한 주요 실패: 뒤 사람이 등장하면 몸통 선택이 중단되고, MediaPipe의 손 두 개가 서로 다른 사람에게 속할 수 있다. 현재 손 연결은 화면 x좌표로 정렬하는 실험용 방식이다. confidence=1은 내부 존재 표시이며 보정된 신뢰도가 아니다. mp_pose_hand도 YOLO 몸통이 있을 때만 관절을 대체하므로 순수 MediaPipe 단독 성능이 아니다.</p></section><section><h2>3. 장면별 실제 검출과 기대 결과</h2><p>초록: 얼굴·특징점 / 보라: MediaPipe 손 21점 / 파랑: 신뢰도 조건을 만족한 YOLO 어깨·손목 / 주황: YOLO 물건. 아래 장면은 수동 확인 표본이며 프레임 전체 정답 라벨은 아니다.</p>'''+''.join(scenes)+'''</section><section><h2>4. 기존 JSON에서 무엇이 늘었나</h2><p>손 모델 추가만으로 기존 v2 JSON의 필드가 새로 생긴 것은 아니다. 동일한 필드에 들어가는 관찰 시간 등이 달라졌다. 처음의 단순 JSON과 비교하면 아래 정보가 이미 확장되어 있다.</p><ul><li>schemaVersion·observationConfigVersion·시간 범위: 어떤 구조와 기준으로 계산했는지 추적.</li><li>coverageRatio·handCoverageRatio·bothWristsVisibleSeconds: 관찰 부족을 높은 점수나 정상 행동으로 오해하지 않기 위한 정보.</li><li>candidateEvents·evidence·evidenceRefs: 미확정 후보와 근거 구간을 연결하여 루브릭이 최종 판단하도록 분리.</li><li>unobservableIntervals·reasonCode: 왜 판정하지 못했는지 시간별로 설명.</li><li>interactionDiagnostics: 물건 후보가 없는 이유가 검출·이력·이동 중 어디에 있는지 진단.</li><li>contextJudgments·isScoringReady·limitations: LLM 미실행과 점수 보류를 명시.</li></ul><h3>44.8–49.0초 예시</h3><pre>'''+dump(result['vision']['candidateEvents'][0])+'''</pre><p>휴대폰 마스크와 얼굴 박스가 연속 겹쳐 후보가 생겼다. confidence:null은 가림 확률을 계산하지 않았다는 뜻이고, 0.577은 물건 검출 신뢰도 중앙값이다. 화면 겹침만으로 실제 깊이 관계나 가림 정도를 확정하지 않는다.</p></section><section><h2>5. 손 가림·시선 제외: 실측한 확장 제안</h2><p>아래는 저장된 검출 좌표로 추가 계산한 실험 결과이다. 정식 API에 반영된 형식이 아니며, 기존 JSON의 시선 값을 바꾸지 않았다. 손 21점의 볼록껍질 또는 물건 polygon이 얼굴 박스 면적의 10% 이상 겹치면 제외하는 비교 규칙이다. 손가락 사이 빈 공간도 볼록껍질에 포함돼 과잉 제외할 수 있다. 얼굴이 미검출되면 이 겹침 계산도 불가능하다.</p><pre>'''+dump(extension)+'''</pre><p>handFaceOverlapCandidates는 0.4초 이상 이어진 손 겹침 후보다. eventId·kind·시작/끝·confidence·evidenceRefs의 의미는 기존 사건과 같지만 이 보조 파일의 evidenceRefs는 제안용이며 완전한 evidence 저장 계약은 아직 없다. gazeExclusionExperiment의 excludedObservableSeconds는 기존에 판정 가능했던 시간 중 제외한 시간이다. observableSeconds·frontFacingSeconds·frontFacingRatio는 제외 후 다시 계산한 값이다. 비율이 올라가도 정확도 향상을 의미하지 않는다.</p><p>정식 반영 시 candidateEvents.kind에 HAND_FACE_OVERLAP_CANDIDATE를 추가하고, unobservableIntervals.reasonCode에 HAND_FACE_OVERLAP_CANDIDATE 및 OBJECT_FACE_OVERLAP_CANDIDATE를 추가하는 안이 적절하다. 제외 구간은 중복 합산하지 않고, 원인과 근거 ID를 연결해야 한다. 계약 모델·스키마·샘플·소비 팀 테스트를 함께 바꿔야 하며 이번 실험에서는 변경하지 않았다.</p></section><section><h2>6. 실제 JSON 모든 값의 의미</h2><p>배열 원소까지 모든 말단 필드와 실측 값을 표시했다. 초 단위이며 null·0·빈 배열의 의미를 구분해야 한다.</p><div class="scroll"><table><tr><th>필드 경로</th><th>실제 값</th><th>의미와 산출 이유</th></tr>'''+glossary()+'''</table></div></section><section><h2>7. 물건 모델 비교와 다음 결정</h2><p>YOLOE-11s-seg-pf도 동일 표본에 CPU로 실행했다. iphone 56건·smartphone 43건처럼 휴대폰 후보를 냈지만, 컵은 beer glass·champagne flute 등으로 흔들렸고 옷·장신구 관련 다수 라벨도 출력했다. 박스별 정답 대응 없이 종류 출력 건수만으로 기존 YOLO11n-seg보다 낫다고 결론낼 수 없다. YOLOE는 이번에 라벨과 시간만 저장했으므로 위치 정확도와 후속 사건 생성 비교는 완료하지 못했다.</p><p>우선 수정 대상은 큰 모델 교체보다 발표자 고정 추적과 손-사람 연결이다. 손을 x좌표로 배정하지 않고 발표자 관절·영역과 연결한 뒤, 정지/가림/물건 접촉을 다시 확인해야 한다. 정지 0건은 손을 모은 구간의 미세 움직임·좌표 흔들림·이력 단절을 분리해 확인해야 하며 지금 임계값을 임의로 완화하면 안 된다.</p><p>발표 무관 물건은 영상 검출과 별개로 발표 문맥 또는 사용자 정답이 필요하다. 이번 영상의 컵·휴대폰·포장·펜이 모두 무관한 물건으로 의도된 것인지 확인 후 관련성 평가 정답을 정해야 한다.</p><p>이번 영상은 이전 영상과 다른 추가 확인 자료다. 그러나 전체 행동 정답 라벨이 없고, 이 결과를 본 이후 조정에 사용하면 미사용 최종 평가 영상으로 부를 수 없다. Precision·Recall·정확도는 계산하지 않았다. 최종 모델 교체는 보류한다.</p></section><section><h2>8. 실행·검증 범위</h2><p>모든 비교는 기존 가중치와 기존 기준으로 실행했다. 공용 백엔드와 API는 수정하지 않았다. 원본 약 62.74초의 마지막 표본은 62.8초로 반올림된 구간을 사용한 한계가 있다. 전체 파이프라인 CPU 시간은 계측하지 않았고 아래는 YOLOE 추론만의 실측이다.</p>'''+f'<p>YOLOE 추론 합 {sum(r["openSeconds"] for r in rows):.2f}초, 표본당 평균 {sum(r["openSeconds"] for r in rows)/len(rows):.3f}초. 디코딩·나머지 모델·모델 로딩은 제외.</p>'+'''<p>전체 원시 검출은 raw.json, 조합별 출력은 baseline.json·yolo_hand.json·mp_pose_hand.json, 확장 비교는 occlusion_extension.json에 저장했다. 원본 영상이나 보고서를 외부 서비스로 전송하지 않았다.</p></section></main></html>'''
(root/'report.html').write_text(report)
print(json.dumps(extension['gazeExclusionExperiment'],ensure_ascii=False));print(root/'report.html')
