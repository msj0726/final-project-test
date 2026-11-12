"""Aggregate observations, validate JSON, and render review videos without scoring."""
import json
from collections import Counter
from pathlib import Path
import cv2
import numpy as np
from vision_study import OUT, CONFIG, DT, dump, gaze


def continuous_events(rows, flags, kind, minimum=0, prefix='event'):
    events=[]; start=None; end=None
    for row,value in list(zip(rows,flags))+[(None,False)]:
        if value is True:
            if start is None:start=row['startSec']
            end=row['endSec']
        elif start is not None:
            if end-start>=minimum-1e-6:
                events.append(dict(eventId=f'{prefix}-{len(events)+1}',kind=kind,startSec=round(start,3),endSec=round(end,3),confidence=None))
            start=None
    return events


def rect_distance(point,box):
    x,y=point;x1,y1,x2,y2=box
    return float(np.hypot(max(x1-x,0,x-x2),max(y1-y,0,y-y2)))


def polygon_overlap(polygon, box, shape):
    if len(polygon)<3 or box is None:return None
    h,w=shape
    mask=np.zeros((h,w),np.uint8)
    cv2.fillPoly(mask,[np.round(polygon).astype(np.int32)],1)
    x1,y1,x2,y2=np.round(box).astype(int)
    x1=max(0,x1);y1=max(0,y1);x2=min(w,x2);y2=min(h,y2)
    if x2<=x1 or y2<=y1:return None
    return float(mask[y1:y2,x1:x2].mean())


def motion_range(history):
    a=np.array(history)
    return float(max(np.linalg.norm(a[i]-a[j],axis=-1).max() for i in range(len(a)) for j in range(i)))


def annotate_rows(rows):
    history=[]; hand_history=[]; previous_box=None;previous_hist=None
    for r in rows:
        image=cv2.imread(str(OUT/'frames'/r['image']))
        hist=cv2.calcHist([cv2.cvtColor(image,cv2.COLOR_BGR2HSV)],[0,1],None,[16,16],[0,180,0,256]);cv2.normalize(hist,hist)
        scene_cut=previous_hist is not None and cv2.compareHist(previous_hist,hist,cv2.HISTCMP_BHATTACHARYYA)>.6
        previous_hist=hist
        body=r['body']; facebox=r['face']['box'] if r['face'] else None
        r.update(isBothHandsStill=None,handStillReason='NO_BODY',isHandModelStill=None,handModelStillReason='NO_MATCHED_HANDS',
                 isWristNearFace=None,isHandNearFace=None,handFaceOverlapRatio=None,matchedHands=[],
                 handObservable=False,bothWristsVisible=False,sceneCut=bool(scene_cut))
        width=None;wrists=[];points=None
        if body:
            points=np.array(body['points']);conf=np.array(body['confidence']);width=float(np.linalg.norm(points[5]-points[6]))
            box=np.array(body['box'])
            if previous_box is not None:
                previous_width=max(1,previous_box[2]-previous_box[0])
                if np.linalg.norm((box[:2]+box[2:]-previous_box[:2]-previous_box[2:])/2)>previous_width*.5 or abs((box[2]-box[0])/previous_width-1)>.4:scene_cut=True
            previous_box=box
            valid=width>=20 and all(conf[j]>=.5 and 0<points[j,0]<image.shape[1]-1 and 0<points[j,1]<image.shape[0]-1 for j in (5,6,9,10))
            r['bothWristsVisible']=bool(valid)
            if valid:
                wrists=points[[9,10]]
                relative=(wrists-points[[5,6]])/width
                if scene_cut:history=[];hand_history=[]
                history.append(relative)
                history=history[-6:]
                r['handStillReason']='TEMPORAL_WARMUP'
                if len(history)==6:
                    r['handObservable']=True
                    r['wristMotionRange']=motion_range(history)
                    r['isBothHandsStill']=r['wristMotionRange']<=.04
                    r['handStillReason']=None
                available=list(range(len(r['hands'])))
                for wrist in wrists:
                    best=min(available,key=lambda j:np.linalg.norm(np.array(r['hands'][j][0])-wrist),default=None)
                    if best is not None and np.linalg.norm(np.array(r['hands'][best][0])-wrist)<=width*.35:
                        r['matchedHands'].append(r['hands'][best]);available.remove(best)
                if len(r['matchedHands'])==2:
                    relative_hands=(np.array(r['matchedHands'])-points[[5,6]][:,None,:])/width
                    hand_history.append(relative_hands.reshape(42,2));hand_history=hand_history[-6:]
                    r['handModelStillReason']='TEMPORAL_WARMUP'
                    if len(hand_history)==6:
                        r['isHandModelStill']=motion_range(hand_history)<=.04;r['handModelStillReason']=None
                else:hand_history=[]
            else:
                history=[];hand_history=[];r['handStillReason']='WRISTS_OR_SHOULDERS_UNOBSERVABLE'
                # A single valid wrist still supports an approach candidate, never a both-hands verdict.
                if width>=20:wrists=[points[j] for j in (9,10) if conf[j]>=.5]
            if width>=20:
                if facebox is not None and len(wrists):r['isWristNearFace']=any(rect_distance(p,facebox)<=width*.15 for p in wrists)
                # Associate each hand to any valid body wrist, including one-hand-visible frames.
                valid_wrists=[points[j] for j in (9,10) if conf[j]>=.5]
                usable=[h for h in r['hands'] if any(np.linalg.norm(np.array(h[0])-w)<=width*.35 for w in valid_wrists)]
                r['associatedHands']=usable
                if facebox is not None and usable:
                    overlaps=[polygon_overlap(cv2.convexHull(np.array(h,dtype=np.float32)).reshape(-1,2),facebox,image.shape[:2]) for h in usable]
                    r['handFaceOverlapRatio']=max(v for v in overlaps if v is not None)
                    r['isHandNearFace']=any(rect_distance(p,facebox)<=width*.15 for h in usable for p in h)
        else:history=[];hand_history=[];previous_box=None
        r['sceneCut']=bool(scene_cut)
        for key in ('objectsStandard','objectsOpen'):
            for obj in r[key]:
                obj['faceOverlapRatio']=polygon_overlap(obj['polygon'],facebox,image.shape[:2])
                obj['isFaceOverlapCandidate']=None if obj['faceOverlapRatio'] is None else obj['faceOverlapRatio']>=.1
                obj['isWristInteractionCandidate']=None if not len(wrists) or not width else any(rect_distance(p,obj['box'])<=width*.12 for p in wrists)
                hands=r.get('associatedHands',[])
                obj['isHandInteractionCandidate']=None if not hands or not width else any(rect_distance(p,obj['box'])<=width*.12 for h in hands for p in h)
                # shortcut: box proximity is a candidate only; upgrade to labeled temporal contact validation before scoring.
    return rows


def validate(summary, rows):
    v=summary['vision'];g=v['gaze'];duration=summary['sampleDurationSeconds']
    assert 0<=g['frontFacingSeconds']<=g['observableSeconds']<=duration+1e-6
    assert g['frontFacingRatio'] is None if g['observableSeconds']==0 else abs(g['frontFacingRatio']-g['frontFacingSeconds']/g['observableSeconds'])<1e-6
    assert 0<=v['handObservableSeconds']<=v['bothWristsVisibleSeconds']<=duration+1e-6
    assert v['handStillSeconds'] is None if v['handObservableSeconds']==0 else 0<=v['handStillSeconds']<=v['handObservableSeconds']
    assert abs(sum(e['endSec']-e['startSec'] for e in v['gestureEvents'])-(v['handStillSeconds'] or 0))<1e-6
    assert len({e['eventId'] for e in v['gestureEvents']})==len(v['gestureEvents'])
    for e in v['gestureEvents']:
        assert summary['sourceStartSec']<=e['startSec']<e['endSec']<=summary['sourceEndSec']
        assert e['confidence'] is None and e['kind']=='HAND_STILLNESS'
    for r in rows:
        if not r['handObservable']:assert r['isBothHandsStill'] is None
        if r['isBothHandsStill'] is None:assert r['handStillReason']
        if r['isCameraFacing'] is None:assert r['gazeReason']
    json.loads(json.dumps(summary,allow_nan=False))


def self_check():
    fake=[dict(startSec=i*.2,endSec=(i+1)*.2) for i in range(20)]
    assert len(continuous_events(fake,[True]*10+[None]+[True]*9,'HAND_STILLNESS',2))==1
    assert continuous_events(fake,[None]*20,'HAND_STILLNESS',2)==[]
    assert continuous_events(fake,[True]*9+[False]*11,'HAND_STILLNESS',2)==[]
    assert motion_range([np.zeros((2,2))]*6)==0
    excursion=[np.zeros((2,2)) for _ in range(6)];excursion[2][0,0]=.1
    assert motion_range(excursion)>.04 # Out-and-back movement must not become stillness.
    assert gaze(None)[0] is None
    face=dict(points=[[0,0],[40,0],[20,15],[10,30],[30,30]])
    assert gaze(face)[0] is True
    face['points'][2]=[38,15];assert gaze(face)[0] is False
    assert polygon_overlap([[0,0],[10,0],[10,10],[0,10]],[0,0,10,10],(20,20))==1
    assert rect_distance([5,5],[0,0,10,10])==0
    return 10


def draw(r, mode='combined'):
    im=cv2.imread(str(OUT/'frames'/r['image']))
    def box(b,color,label):
        x1,y1,x2,y2=np.array(b).astype(int);cv2.rectangle(im,(x1,y1),(x2,y2),color,2);cv2.putText(im,label[:35],(x1,max(14,y1-4)),0,.4,color,1)
    if r['body']:
        box(r['body']['box'],(230,160,0),'POSE')
        pts=np.array(r['body']['points']).astype(int);conf=r['body']['confidence']
        for a,b in ((5,6),(5,7),(7,9),(6,8),(8,10)):
            if conf[a]>=.5 and conf[b]>=.5:cv2.line(im,tuple(pts[a]),tuple(pts[b]),(255,180,0),2)
        for j in (5,6,7,8,9,10):
            if conf[j]>=.5:cv2.circle(im,tuple(pts[j]),4,(255,180,0),-1)
    if r['face']:
        box(r['face']['box'],(0,200,255),'FACE')
        for p in r['face']['points']:cv2.circle(im,tuple(np.array(p).astype(int)),3,(0,200,255),-1)
    for h in (r.get('associatedHands',[]) if mode!='baseline' else []):
        for p in h:cv2.circle(im,tuple(np.array(p).astype(int)),2,(255,0,255),-1)
    for key,color,prefix in [('objectsStandard',(0,200,0),'N'),('objectsOpen',(255,120,255),'E')]:
        if mode not in ('combined', 'standard' if key=='objectsStandard' else 'open'):continue
        for obj in r[key]:
            box(obj['box'],color,prefix+':'+obj['label'])
            if obj['polygon']:cv2.polylines(im,[np.array(obj['polygon'],np.int32)],True,color,1)
    panel=np.zeros((125,im.shape[1],3),dtype=np.uint8)
    def state(x):return 'UNKNOWN' if x is None else ('YES' if x else 'NO')
    labels=[f"{r['clipId']} | source {r['sourceTimeSec']:.3f}s | 5 FPS samples | NO SCORE",
            f"Camera-facing: {state(r['isCameraFacing'])} | wrist still: {state(r['isBothHandsStill'])} | hand model still: {state(r['isHandModelStill'])}",
            f"Wrist near face: {state(r['isWristNearFace'])} | hand near face: {state(r['isHandNearFace'])}",
            f"Objects: N={len(r['objectsStandard'])}, E={len(r['objectsOpen'])} | all overlap/contact outputs are CANDIDATES",
            f"Unknown: {r['gazeReason'] or '-'} / {r['handStillReason'] or '-'}"]
    for i,s in enumerate(labels):cv2.putText(panel,s,(10,20+i*23),0,.47,(240,240,240),1)
    return np.vstack([im,panel,np.zeros((1,im.shape[1],3),np.uint8)]) # even height for H264


def main():
    tests=self_check()
    raw=json.loads((OUT/'raw_observations.json').read_text());summaries=[];all_rows=[]
    (OUT/'videos').mkdir(exist_ok=True);(OUT/'review').mkdir(exist_ok=True);(OUT/'json').mkdir(exist_ok=True)
    for clip in dict.fromkeys(r['clipId'] for r in raw):
        rows=annotate_rows([r for r in raw if r['clipId']==clip]);all_rows+=rows
        events=continuous_events(rows,[r['isBothHandsStill'] for r in rows],'HAND_STILLNESS',2,clip+'-still')
        obs=round(sum(r['isCameraFacing'] is not None for r in rows)*DT,3)
        front=round(sum(r['isCameraFacing'] is True for r in rows)*DT,3)
        handobs=round(sum(r['handObservable'] for r in rows)*DT,3)
        candidates=[]
        for model,key in [('YOLO11N_SEG','objectsStandard'),('YOLOE11S_PF','objectsOpen')]:
            for kind,flag in [('OBJECT_FACE_OVERLAP_CANDIDATE','isFaceOverlapCandidate'),('OBJECT_INTERACTION_CANDIDATE','isHandInteractionCandidate')]:
                labels=sorted({o['label'] for r in rows for o in r[key] if o[flag] is True})
                for label in labels:
                    new=continuous_events(rows,[any(o['label']==label and o[flag] is True for o in r[key]) for r in rows],kind,.4,f'{clip}-{model}-{kind}-{label}')
                    for e in new:e.update(model=model,objectLabel=label,verdict='UNDETERMINED',reason='CANDIDATE_ONLY_NOT_CONTACT_OR_OCCLUSION_PROOF')
                    candidates+=new
        candidates+=continuous_events(rows,[None if r['handFaceOverlapRatio'] is None else r['handFaceOverlapRatio']>=.1 for r in rows],'HAND_FACE_OVERLAP_CANDIDATE',.4,clip+'-hand-face')
        summary=dict(schemaVersion='vision-experiment-v1',clipId=clip,sourceVideo=rows[0]['sourceVideo'],sourceStartSec=rows[0]['startSec'],sourceEndSec=rows[-1]['endSec'],sampleDurationSeconds=10,
          vision=dict(gaze=dict(observableSeconds=obs,frontFacingSeconds=front,frontFacingRatio=front/obs if obs else None,coverageRatio=obs/10,method='EXPERIMENTAL_5_POINT_FACE_GEOMETRY'),
            handObservableSeconds=handobs,handStillSeconds=round(sum(e['endSec']-e['startSec'] for e in events),3) if handobs else None,bothWristsVisibleSeconds=round(sum(r['bothWristsVisible'] for r in rows)*DT,3),
            gestureEvents=events,criterionStatus=dict(HAND_STILLNESS='EVALUATED' if handobs else 'UNOBSERVABLE',FACE_OCCLUSION='CANDIDATE_ONLY',UNRELATED_OBJECT_TOUCH='PENDING_CONTEXT_JUDGMENT'),
            candidateEvents=candidates),
          limitations=['실험용 임계값, 독립 정확도 검증 전, 실제 감점 없음','5 FPS 표본마다 0.2초를 대표하므로 시간은 표본 기반 추정','handObservableSeconds는 양손목·어깨 및 1초 연속 이력을 모두 확보한 시간','양손 정지는 손목 기준이며 손가락만의 움직임을 배제하지 못함','정면은 5개 얼굴 점의 기하학적 대리 지표, 실제 눈동자 시선 아님','물건/손 영역 겹침 및 근접은 가림/접촉의 확정 근거가 아님','LLM 미실행, 물건의 발표 관련성 미판정','가장 큰 단일 인물 선택은 발표자 신원을 보장하지 않음'])
        validate(summary,rows);summaries.append(summary);dump(OUT/'json'/f'{clip}.json',summary)
        writers={}
        for i,r in enumerate(rows):
            for mode in ('baseline','hands','standard','open'):
                frame=draw(r,mode)
                if mode not in writers:
                    writers[mode]=cv2.VideoWriter(str(OUT/'videos'/f'{clip}_{mode}.mp4'),cv2.VideoWriter_fourcc(*'avc1'),5,(frame.shape[1],frame.shape[0]));assert writers[mode].isOpened()
                writers[mode].write(frame)
            if i in (0,12,25,37,49):cv2.imwrite(str(OUT/'review'/f'{clip}_{i:03}.jpg'),draw(r))
        for writer in writers.values():writer.release()
        cap=cv2.VideoCapture(str(OUT/'videos'/f'{clip}_baseline.mp4'));count=0
        while cap.read()[0]:count+=1
        cap.release();assert count==50
    timings={k:dict(medianMs=float(np.median([r['timingMs'][k] for r in all_rows])),p95Ms=float(np.percentile([r['timingMs'][k] for r in all_rows],95)),totalSeconds=sum(r['timingMs'][k] for r in all_rows)/1000) for k in all_rows[0]['timingMs']}
    counts=dict(frames=len(all_rows),clips=len(summaries),sourceSeconds=90,handOutputFrames=sum(bool(r['hands']) for r in all_rows),associatedHandFrames=sum(bool(r.get('associatedHands')) for r in all_rows),bothMatchedHandFrames=sum(len(r['matchedHands'])==2 for r in all_rows),
      wristNearFaceTrue=sum(r['isWristNearFace'] is True for r in all_rows),handNearFaceTrue=sum(r['isHandNearFace'] is True for r in all_rows),wristStillTrue=sum(r['isBothHandsStill'] is True for r in all_rows),handStillTrue=sum(r['isHandModelStill'] is True for r in all_rows),
      stillPairedObservableFrames=sum(r['isBothHandsStill'] is not None and r['isHandModelStill'] is not None for r in all_rows),
      stillDisagreementFrames=sum(r['isBothHandsStill'] is not None and r['isHandModelStill'] is not None and r['isBothHandsStill']!=r['isHandModelStill'] for r in all_rows),
      standardLabels=dict(Counter(o['label'] for r in all_rows for o in r['objectsStandard'])),openLabels=dict(Counter(o['label'] for r in all_rows for o in r['objectsOpen'])))
    dump(OUT/'observations.json',all_rows);dump(OUT/'summary.json',dict(clips=summaries,counts=counts,timings=timings,validation=dict(syntheticChecks=tests,clipJsonValidated=len(summaries),observationFramesValidated=len(all_rows),videoFramesDecoded=450)))
    print(json.dumps(dict(counts=counts,timings=timings),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
