"""Versioned experimental observations after explicit user decisions. No scores."""
import json,math,sys
from pathlib import Path
import cv2
import numpy as np
from vision_decision_study import ROOT,PREVIOUS,OUT
from vision_study import dump
from summarize_vision_study import annotate_rows,continuous_events,rect_distance,polygon_overlap,draw
sys.path.insert(0,str(ROOT/'.report_tools'))
import jsonschema

CONFIG={
 'observationConfigVersion':'vision-20261111-v2-gap04-min6',
 'models':['yolo11n-pose.pt','yolov5n-face.pt','yolo11n-seg.pt'],
 'userDecisions':{'stillMinimumSeconds':5,'scoreConversion':'WITHHELD','interactionRule':'WRIST_PROXIMITY_AND_COMOTION','faceOverlap':'SEPARATE_CANDIDATE','trackMissingGapSeconds':.4},
 'experimentalParameters':{'sampleFps':5,'motionWindowSeconds':1,'wristStillRangeShoulderWidths':.04,
  'objectConfidence':.25,'trackMinIou':.3,'wristsToBoxDistanceShoulderWidths':.12,
  'comotionWindowSeconds':1,'minimumMotionShoulderWidths':.03,'minimumMotionCosine':.8,
  'maximumMotionResidualShoulderWidths':.05,'minimumObservedSamplesInOneSecond':6,'missingCoordinatesImputed':False,'candidateMinimumSeconds':.4,'faceOverlapFraction':.1},
 'parameterStatus':'EXPERIMENTAL_NOT_OPTIMIZED_OR_ACCURACY_VALIDATED'
}


def iou(a,b):
 x1,y1=np.maximum(a[:2],b[:2]);x2,y2=np.minimum(a[2:],b[2:]);inter=max(0,x2-x1)*max(0,y2-y1)
 return inter/max(1,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)


def comotion(points,min_samples=6):
 if len(points)<min_samples:return None,'TEMPORAL_WARMUP',None
 wrist=np.array([x[0] for x in points]);obj=np.array([x[1] for x in points])
 w=wrist-wrist[0];o=obj-obj[0]
 wrange=float(np.linalg.norm(w,axis=1).max());orange=float(np.linalg.norm(o,axis=1).max())
 residual=float(np.sqrt(np.mean(np.sum((w-o)**2,axis=1))))
 denom=float(np.linalg.norm(w)*np.linalg.norm(o));cosine=float(np.sum(w*o)/denom) if denom else None
 metrics=dict(wristMotion=wrange,objectMotion=orange,motionCosine=cosine,motionResidual=residual)
 if wrange<.03 or orange<.03:return False,'INSUFFICIENT_MOTION',metrics
 if cosine<.8 or residual>.05:return False,'MOTION_MISMATCH',metrics
 return True,None,metrics


def intervals(rows,criterion,value_key,reason_key):
 result=[]
 for r in rows:
  if r[value_key] is not None:continue
  reason=r[reason_key]
  if result and result[-1]['reasonCode']==reason and abs(result[-1]['endSec']-r['startSec'])<1e-6:
   result[-1]['endSec']=r['endSec']
  else:result.append(dict(criterionKey=criterion,startSec=r['startSec'],endSec=r['endSec'],reasonCode=reason))
 return result


def track_and_measure(rows, minimum_samples=6, max_gap_seconds=.4):
 tracks={};counter=0;previous_scene=None
 for r in rows:
  if r['sceneCut']:tracks={}
  current={k:v for k,v in tracks.items() if r['startSec']-v['lastSeenSec']<=max_gap_seconds+1e-6};used=set();body=r['body'];facebox=r['face']['box'] if r['face'] else None
  width=0;anchor=None;wrists={}
  if body:
   p=np.array(body['points']);c=body['confidence'];width=float(np.linalg.norm(p[5]-p[6]))
   if width>=20 and c[5]>=.5 and c[6]>=.5:
    anchor=(p[5]+p[6])/2
    for j in (9,10):
     if c[j]>=.5 and 0<p[j,0]<959 and 0<p[j,1]<539:wrists[j]=p[j]
  for o in r['objectsStandard']:
   matches=[(iou(o['box'],v['box']),k) for k,v in tracks.items() if v['label']==o['label'] and k not in used and r['startSec']-v['lastSeenSec']-.2<=max_gap_seconds+1e-6]
   best=max(matches,default=(0,None))
   if best[0]>=.3:tid=best[1];track=tracks[tid];used.add(tid)
   else:
    counter+=1;tid=f"{r['clipId']}-object-{counter}";track={'history':[],'historyTimes':[],'wristSide':None}
   wrist_side=min(wrists,key=lambda j:rect_distance(wrists[j],o['box']),default=None)
   near=None if wrist_side is None else rect_distance(wrists[wrist_side],o['box'])<=width*.12
   if near:
    if track['wristSide']!=wrist_side:track['history']=[];track['historyTimes']=[]
    track['wristSide']=wrist_side
    center=(np.array(o['box'][:2])+np.array(o['box'][2:]))/2
    track['history'].append(((wrists[wrist_side]-anchor)/width,(center-anchor)/width));track['historyTimes'].append(r['startSec'])
    while track['historyTimes'] and r['startSec']-track['historyTimes'][0]>1+1e-6:
     track['historyTimes'].pop(0);track['history'].pop(0)
    if track['historyTimes'] and r['startSec']-track['historyTimes'][0]>=1-1e-6:
     together,reason,metrics=comotion(track['history'],minimum_samples)
    else:together,reason,metrics=None,'TEMPORAL_WARMUP',None
   else:
    track['history']=[];track['historyTimes']=[];together=None if near is None else False
    reason='WRIST_UNOBSERVABLE' if near is None else 'NOT_NEAR_WRIST';metrics=None
   overlap=polygon_overlap(o['polygon'],facebox,(540,960))
   o.update(objectTrackId=tid,isWristNearObject=near,isComoving=together,comotionReason=reason,comotionMetrics=metrics,
            faceOverlapRatio=overlap,isFaceOverlapCandidate=None if overlap is None else overlap>=.1)
   track.update(box=o['box'],label=o['label'],lastSeenSec=r['startSec']);current[tid]=track
  tracks=current
 return rows


def make_events(rows,clip):
 events=[];evidence=[]
 for tid in dict.fromkeys(o['objectTrackId'] for r in rows for o in r['objectsStandard']):
  for kind,flag,method in [('OBJECT_INTERACTION_CANDIDATE','isComoving','WRIST_BOX_PROXIMITY_AND_BODY_RELATIVE_COMOTION'),('OBJECT_FACE_OVERLAP_CANDIDATE','isFaceOverlapCandidate','OBJECT_MASK_FACE_BOX_OVERLAP')]:
   flags=[any(o['objectTrackId']==tid and o[flag] is True for o in r['objectsStandard']) for r in rows]
   new=continuous_events(rows,flags,kind,.4,f'{tid}-{kind}')
   for event in new:
    associated=[(r,o) for r in rows if event['startSec']<=r['startSec']<event['endSec'] for o in r['objectsStandard'] if o['objectTrackId']==tid and o[flag] is True]
    event.update(objectTrackId=tid,objectLabel=associated[0][1]['label'],objectLabelConfidence=float(np.median([o['confidence'] for r,o in associated])),
       observationMethod=method,sourceModel='yolo11n-seg.pt',evidenceRefs=[event['eventId']+'-evidence'])
    evidence.append(dict(evidenceId=event['evidenceRefs'][0],sourceType='VISION',startSec=event['startSec'],endSec=event['endSec'],
      frameTimesSec=[r['sourceTimeSec'] for r,o in associated],
      description='동반 이동·근접의 규칙상 후보. 실제 접촉/발표 관련성 미확정.' if flag=='isComoving' else '물건 마스크와 얼굴 박스의 겹침 후보. 실제 가림 미확정.',
      detectionConfidenceAggregation='MEDIAN_OF_ELIGIBLE_FRAME_DETECTIONS'))
    events.append(event)
 return events,evidence


def tests():
 still=[dict(startSec=i*.2,endSec=(i+1)*.2) for i in range(30)]
 assert len(continuous_events(still,[True]*25+[False]*5,'HAND_STILLNESS',5))==1
 assert not continuous_events(still,[True]*24+[False]*6,'HAND_STILLNESS',5)
 assert not continuous_events(still,[True]*15+[None]+[True]*14,'HAND_STILLNESS',5)
 stationary=[([0,0],[0,0])]*6;assert comotion(stationary)[0] is False
 moving=[([i*.02,0],[i*.02,0]) for i in range(6)];assert comotion(moving)[0] is True
 static_obj=[([i*.02,0],[0,0]) for i in range(6)];assert comotion(static_obj)[0] is False
 opposite=[([i*.02,0],[-i*.02,0]) for i in range(6)];assert comotion(opposite)[0] is False
 assert comotion(moving[:5])[0] is None
 assert iou([0,0,10,10],[0,0,10,10])==1
 assert iou([0,0,10,10],[20,20,30,30])==0
 def fake_rows(missing):
  result=[]
  for i in range(6):
   p=np.zeros((17,2));p[5]=[100,200];p[6]=[200,200];p[9]=[140+i*2,250];p[10]=[300,250]
   obj=dict(label='synthetic-object',box=[130+i*2,240,150+i*2,260],polygon=[],confidence=.8)
   result.append(dict(clipId='SYNTHETIC',startSec=i*.2,sceneCut=False,body=dict(points=p.tolist(),confidence=[1]*17),face=None,objectsStandard=[] if i in missing else [obj]))
  return track_and_measure(result,minimum_samples=4)
 gap=fake_rows({2,3})
 assert gap[0]['objectsStandard'][0]['objectTrackId']==gap[4]['objectsStandard'][0]['objectTrackId']
 assert gap[2]['objectsStandard']==[] and gap[3]['objectsStandard']==[]
 assert gap[5]['objectsStandard'][0]['isComoving'] is True
 long_gap=fake_rows({2,3,4})
 assert long_gap[0]['objectsStandard'][0]['objectTrackId']!=long_gap[5]['objectsStandard'][0]['objectTrackId']
 return 14


def process():
 tests_passed=tests()
 raw=json.loads((OUT/'raw_observations.json').read_text());summaries=[];observations=[];baseline_events=0
 (OUT/'json').mkdir(exist_ok=True);(OUT/'videos').mkdir(exist_ok=True);(OUT/'review').mkdir(exist_ok=True)
 for clip in dict.fromkeys(r['clipId'] for r in raw):
  frames=[r for r in raw if r['clipId']==clip]
  for r in frames:r.update(hands=[],objectsStandard=r.pop('objects'),objectsOpen=[])
  # Reuse tested body-relative motion, discontinuity handling, and tri-state rules; no hand inference.
  frames=track_and_measure(annotate_rows(frames));observations+=frames
  gesture=continuous_events(frames,[r['isBothHandsStill'] for r in frames],'HAND_STILLNESS',5,clip+'-still')
  candidates,evidence=make_events(frames,clip)
  for e in gesture:
   e['evidenceRefs']=[e['eventId']+'-evidence']
   evidence.append(dict(evidenceId=e['evidenceRefs'][0],sourceType='VISION',startSec=e['startSec'],endSec=e['endSec'],description='양손목의 몸통 상대 위치가 실험 경계 내에서 5초 이상 연속 정지.'))
  for tid in {o['objectTrackId'] for r in frames for o in r['objectsStandard']}:
   baseline_events+=len(continuous_events(frames,[any(o['objectTrackId']==tid and o['isWristNearObject'] is True for o in r['objectsStandard']) for r in frames],'PROXIMITY_ONLY',.4))
  obs=round(sum(r['isCameraFacing'] is not None for r in frames)*.2,3);front=round(sum(r['isCameraFacing'] is True for r in frames)*.2,3)
  handobs=round(sum(r['handObservable'] for r in frames)*.2,3)
  unknown=intervals(frames,'GAZE','isCameraFacing','gazeReason')+intervals(frames,'HAND_STILLNESS','isBothHandsStill','handStillReason')
  interaction=[e for e in candidates if e['kind']=='OBJECT_INTERACTION_CANDIDATE']
  near_objects=[o for r in frames for o in r['objectsStandard'] if o['isWristNearObject'] is True]
  diagnostics=dict(nearWristDetectionCount=len(near_objects),insufficientHistoryCount=sum(o['comotionReason']=='TEMPORAL_WARMUP' for o in near_objects),motionMismatchCount=sum(o['comotionReason']=='MOTION_MISMATCH' for o in near_objects),insufficientMotionCount=sum(o['comotionReason']=='INSUFFICIENT_MOTION' for o in near_objects),comovingDetectionCount=sum(o['isComoving'] is True for o in near_objects),unit='DETECTION_INSTANCES_NOT_EVENTS')
  summary=dict(schemaVersion='vision-observation-v2-experiment',observationConfigVersion=CONFIG['observationConfigVersion'],
   clipId=clip,sourceVideo=frames[0]['sourceVideo'],sourceStartSec=frames[0]['startSec'],sourceEndSec=frames[-1]['endSec'],sampleDurationSeconds=10,isScoringReady=False,
   vision=dict(gaze=dict(observableSeconds=obs,frontFacingSeconds=front,frontFacingRatio=front/obs if obs else None,coverageRatio=obs/10,method='EXPERIMENTAL_5_POINT_FACE_GEOMETRY'),
    handObservableSeconds=handobs,handStillSeconds=round(sum(e['endSec']-e['startSec'] for e in gesture),3) if handobs else None,bothWristsVisibleSeconds=round(sum(r['bothWristsVisible'] for r in frames)*.2,3),handCoverageRatio=handobs/10,
    gestureEvents=gesture,candidateEvents=candidates,interactionDiagnostics=diagnostics,unobservableIntervalsStatus='GENERATED',unobservableIntervals=unknown,
    criterionStatus=dict(HAND_STILLNESS='EVALUATED' if handobs else 'UNOBSERVABLE',FACE_OCCLUSION='CANDIDATE_ONLY',UNRELATED_OBJECT_TOUCH='NOT_EVALUATED')),
   evidence=evidence,contextJudgments=[dict(criterionKey='UNRELATED_OBJECT_TOUCH',status='NOT_RUN',verdict=None,reason='LLM_NOT_EXECUTED',evidenceRefs=[ref for e in interaction for ref in e['evidenceRefs']])],
   limitations=['사용자 결정으로 점수 환산 보류. 실제 점수 필드 없음.','양손 정지는 손목 기준 5초, 손가락 전용 모델 미사용.','5 FPS·기존에 본 공개 영상 재사용, 독립 정확도 평가 아님.','1초 동반 이동 규칙은 실험자가 정한 미검증 설정. 정지 상태로 물건을 든 행동은 포착하지 못함.','같은 라벨·IoU로 임시 추적. 0.4초 누락까지 ID만 유지하고 빈 프레임의 좌표·사건을 보간하지 않음.','물건 미검출은 물건이 없다는 뜻이 아님. 물건 사건의 recall 및 관찰률은 계산하지 않음.','머리 방향과 물건 가림·접촉의 정확도 미검증. LLM 관련성 판단 미실행.'])
  assert abs(sum(x['endSec']-x['startSec'] for x in unknown if x['criterionKey']=='GAZE')+obs-10)<1e-6
  assert abs(sum(x['endSec']-x['startSec'] for x in unknown if x['criterionKey']=='HAND_STILLNESS')+handobs-10)<1e-6
  assert 0<=front<=obs<=10 and 0<=handobs<=10
  assert (summary['vision']['handStillSeconds'] is None)==(handobs==0)
  assert len({e['eventId'] for e in gesture+candidates})==len(gesture+candidates)
  refs={e['evidenceId'] for e in evidence}
  assert all(ref in refs for e in gesture+candidates for ref in e['evidenceRefs'])
  for e in gesture+candidates:assert summary['sourceStartSec']<=e['startSec']<e['endSec']<=summary['sourceEndSec']
  assert all(j['status']=='NOT_RUN' and j['verdict'] is None for j in summary['contextJudgments'])
  summaries.append(summary);dump(OUT/'json'/f'{clip}.json',summary)
  writer=None
  for i,r in enumerate(frames):
   frame=draw(r,'standard')[:540]
   panel=np.zeros((120,960,3),np.uint8)
   near=sum(o['isWristNearObject'] is True for o in r['objectsStandard']);moving=sum(o['isComoving'] is True for o in r['objectsStandard'])
   def state(x):return 'UNKNOWN' if x is None else 'YES' if x else 'NO'
   lines=[f"{clip} | source {r['sourceTimeSec']:.3f}s | YOLO pose + face + seg only | NO SCORE",f"Camera-facing {state(r['isCameraFacing'])} | wrist still-window {state(r['isBothHandsStill'])} | event minimum 5s",f"Objects {len(r['objectsStandard'])} | proximity {near} | comotion candidates {moving}",f"Gaze: {r['gazeReason'] or '-'} | Hands: {r['handStillReason'] or '-'} | LLM NOT_RUN"]
   for j,line in enumerate(lines):cv2.putText(panel,line,(10,22+j*27),0,.46,(240,240,240),1)
   frame=np.vstack([frame,panel])
   if writer is None:
    writer=cv2.VideoWriter(str(OUT/'videos'/f'{clip}.mp4'),cv2.VideoWriter_fourcc(*'avc1'),5,(960,660));assert writer.isOpened()
   writer.write(frame)
   if i in (0,12,25,37,49):cv2.imwrite(str(OUT/'review'/r['image']),frame)
  writer.release()
 times={k:{'medianMs':float(np.median([r['timingMs'][k] for r in raw])),'p95Ms':float(np.percentile([r['timingMs'][k] for r in raw],95)),'totalSeconds':sum(r['timingMs'][k] for r in raw)/1000} for k in raw[0]['timingMs']}
 counts=dict(frames=450,clips=9,seconds=90,gazeObservableSeconds=round(sum(c['vision']['gaze']['observableSeconds'] for c in summaries),3),frontFacingSeconds=round(sum(c['vision']['gaze']['frontFacingSeconds'] for c in summaries),3),handObservableSeconds=round(sum(c['vision']['handObservableSeconds'] for c in summaries),3),stillEvents=sum(len(c['vision']['gestureEvents']) for c in summaries),proximityOnlyEvents=baseline_events,interactionCandidates=sum(e['kind']=='OBJECT_INTERACTION_CANDIDATE' for c in summaries for e in c['vision']['candidateEvents']),faceOverlapCandidates=sum(e['kind']=='OBJECT_FACE_OVERLAP_CANDIDATE' for c in summaries for e in c['vision']['candidateEvents']),unobservableIntervals=sum(len(c['vision']['unobservableIntervals']) for c in summaries))
 dump(OUT/'config.json',CONFIG);dump(OUT/'observations.json',observations)
 dump(OUT/'summary.json',dict(config=CONFIG,counts=counts,timings=times,clips=summaries,validation=dict(syntheticChecks=tests_passed,semanticClips=9)))
 print(json.dumps(dict(counts=counts,timings=times),ensure_ascii=False,indent=2))


if __name__=='__main__':process()
