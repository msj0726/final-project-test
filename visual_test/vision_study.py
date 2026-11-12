"""Exploratory CPU study; not a production scoring module or accuracy benchmark."""
import json
import math
import platform
import time
from collections import Counter
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import torch
import ultralytics
from ultralytics import YOLO, YOLOE
from realtime_yolo_benchmark import OLD_ROOT, attempt_load, letterbox, non_max_suppression_face

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results/vision_study'
MODELS = ROOT / 'models'
SAMPLE_FPS = 5
DT = 1 / SAMPLE_FPS
CLIPS = [('erik_10', 'erik_hanberg_lightning_2024', 10), ('erik_60', 'erik_hanberg_lightning_2024', 60)] + [(f'jack_{s}', 'jack_andraka_talk_2013', s) for s in (5, 65, 105, 165, 225, 325, 385)]
CONFIG = dict(sampleFps=5, clipSeconds=10, bodyConfidence=0.5, faceConfidence=0.5,
              objectConfidence=0.25, wristMotionRange=0.04, stillWindowSeconds=1,
              stillMinimumSeconds=2, gazeHorizontalLimit=0.18,
              gazeNoseFractionRange=[0.2, 0.8], gazeFaceAspectRange=[0.3, 1.3],
              gazeRollLimitDegrees=20, objectHandDistanceShoulderWidths=0.12,
              faceOverlapCandidateRatio=0.10)


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False))


def face_infer(model, frame):
    h, w = frame.shape[:2]
    scale = min(640 / max(h, w), 1)
    small = cv2.resize(frame, (round(w*scale), round(h*scale)))
    image, ratio, pad = letterbox(small, new_shape=640)
    tensor = torch.from_numpy(image[:, :, ::-1].transpose(2, 0, 1).copy()).float()[None] / 255
    with torch.inference_mode():
        detections = non_max_suppression_face(model(tensor)[0], 0.5, 0.45)[0].cpu().numpy()
    result = []
    for det in detections:
        xy = det[5:15].reshape(5, 2).copy()
        xy[:, 0] = (xy[:, 0]-pad[0]) / ratio[0] * w / small.shape[1]
        xy[:, 1] = (xy[:, 1]-pad[1]) / ratio[1] * h / small.shape[0]
        box = det[:4].copy()
        box[[0,2]] = (box[[0,2]]-pad[0]) / ratio[0] * w / small.shape[1]
        box[[1,3]] = (box[[1,3]]-pad[1]) / ratio[1] * h / small.shape[0]
        result.append(dict(box=box.tolist(), points=xy.tolist(), confidence=float(det[4])))
    return result


def gaze(face):
    if face is None:
        return None, 'NO_ASSOCIATED_FACE', None
    p = np.array(face['points'], dtype=float)
    eyes = sorted(p[:2], key=lambda a: a[0])
    eye_mid = (eyes[0]+eyes[1])/2
    axis = eyes[1]-eyes[0]
    dist = np.linalg.norm(axis)
    if dist < 12:
        return None, 'FACE_TOO_SMALL', None
    axis /= dist
    vertical = np.array([-axis[1], axis[0]])
    mouth_mid = (p[3]+p[4])/2
    height = float(np.dot(mouth_mid-eye_mid, vertical))
    if height <= 3:
        return None, 'INVALID_LANDMARK_GEOMETRY', None
    x = float(np.dot(p[2]-eye_mid, axis)/dist)
    y = float(np.dot(p[2]-eye_mid, vertical)/height)
    aspect = height/dist
    roll = math.degrees(math.atan2(axis[1], axis[0]))
    metrics = dict(horizontalOffset=x, noseFraction=y, faceAspect=aspect, rollDegrees=roll)
    return bool(abs(x)<=.18 and .2<=y<=.8 and .3<=aspect<=1.3 and abs(roll)<=20), None, metrics


def choose_person(pred):
    if len(pred.boxes)==0:
        return None, 'NO_PERSON'
    boxes = pred.boxes.xyxy.cpu().numpy()
    areas = (boxes[:,2]-boxes[:,0])*(boxes[:,3]-boxes[:,1])
    order = np.argsort(areas)[::-1]
    if len(order)>1 and areas[order[1]]/areas[order[0]]>.5:
        return None, 'MULTIPLE_SIMILAR_PEOPLE'
    i = order[0]
    return dict(box=boxes[i].tolist(), points=pred.keypoints.xy[i].cpu().numpy().tolist(), confidence=pred.keypoints.conf[i].cpu().numpy().tolist()), None


def associate_face(faces, body):
    if body is None:
        return None
    x1,y1,x2,y2=body['box']
    candidates=[f for f in faces if x1<=(f['box'][0]+f['box'][2])/2<=x2 and y1<=(f['box'][1]+f['box'][3])/2<=y1+(y2-y1)*.45]
    return max(candidates, key=lambda f:f['confidence'],default=None)


def object_infer(model, frame):
    r=model.predict(frame,device='cpu',imgsz=640,conf=.25,verbose=False)[0]
    objects=[]
    for i,b in enumerate(r.boxes):
        label=r.names[int(b.cls.item())]
        if label in ('person','human','man','woman','boy','girl'):
            continue
        polygon=r.masks.xy[i].tolist() if r.masks is not None else []
        objects.append(dict(label=label,confidence=float(b.conf.item()),box=b.xyxy[0].cpu().numpy().tolist(),polygon=polygon))
    return objects


def extract_frames():
    (OUT/'frames').mkdir(parents=True,exist_ok=True)
    manifest=[]
    for video in sorted(set(c[1] for c in CLIPS)):
        cap=cv2.VideoCapture(str(ROOT.parent/'data/open_presentations'/f'{video}.webm'))
        assert cap.isOpened()
        targets=sorted((s+i*DT,name,s,i) for name,v,s in CLIPS if v==video for i in range(50))
        target_index=0
        index=0
        previous_time=-1
        # WebM advertises 1000 FPS in OpenCV; use decoded timestamps, never nominal FPS.
        while target_index<len(targets):
            ok,frame=cap.read()
            if not ok:
                raise RuntimeError(f'Video ended at {index}, next target {targets[target_index]}')
            actual_time=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            assert actual_time>=previous_time
            previous_time=actual_time
            if actual_time+1e-6>=targets[target_index][0]:
                target,name,start,i=targets[target_index]
                assert actual_time-target<.1, (actual_time,target)
                h,w=frame.shape[:2]
                frame=cv2.resize(frame,(960,round(h*960/w)))
                path=OUT/'frames'/f'{name}_{i:03}.jpg'
                assert cv2.imwrite(str(path),frame)
                manifest.append(dict(clipId=name,sourceVideo=video,sourceFrame=index,sourceTimeSec=actual_time,
                                     startSec=target,endSec=target+DT,image=path.name))
                target_index+=1
            index+=1
        cap.release()
    assert len(manifest)==450
    dump(OUT/'frame_manifest.json',manifest)
    return manifest


def timed(fn):
    t=time.perf_counter(); result=fn(); return result,(time.perf_counter()-t)*1000


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=extract_frames()
    torch.set_num_threads(1)
    pose=YOLO(str(OLD_ROOT/'models/yolo11n-pose.pt'))
    face=attempt_load(str(OLD_ROOT/'models/yolov5n-face.pt'),map_location='cpu').eval()
    standard=YOLO(str(MODELS/'yolo11n-seg.pt'))
    open_model=YOLOE(str(MODELS/'yoloe-11s-seg-pf.pt'))
    hand=mp.tasks.vision.HandLandmarker.create_from_options(mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODELS/'hand_landmarker.task')),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,num_hands=2,
        min_hand_detection_confidence=.5,min_hand_presence_confidence=.5))
    warm=cv2.imread(str(OUT/'frames'/manifest[0]['image']))
    for _ in range(2):
        pose.predict(warm,device='cpu',verbose=False)
        face_infer(face,warm)
        object_infer(standard,warm); object_infer(open_model,warm)
        hand.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(warm,cv2.COLOR_BGR2RGB)))
    rows=[]
    for i,m in enumerate(manifest):
        frame=cv2.imread(str(OUT/'frames'/m['image']))
        pred,pose_ms=timed(lambda:pose.predict(frame,device='cpu',imgsz=640,conf=.5,verbose=False)[0])
        body,reason=choose_person(pred)
        faces,face_ms=timed(lambda:face_infer(face,frame))
        selected=associate_face(faces,body)
        facing,gaze_reason,geometry=gaze(selected)
        hands,hand_ms=timed(lambda:hand.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))))
        hand_points=[[[p.x*frame.shape[1],p.y*frame.shape[0]] for p in pts] for pts in hands.hand_landmarks]
        objects_a,a_ms=timed(lambda:object_infer(standard,frame))
        objects_b,b_ms=timed(lambda:object_infer(open_model,frame))
        rows.append(dict(**m,body=body,bodyReason=reason,face=selected,isCameraFacing=facing,gazeReason=gaze_reason,gazeGeometry=geometry,
                         hands=hand_points,objectsStandard=objects_a,objectsOpen=objects_b,
                         timingMs=dict(pose=pose_ms,face=face_ms,hand=hand_ms,standard=a_ms,openVocabulary=b_ms)))
        if (i+1)%25==0:
            print(f'{i+1}/{len(manifest)} frames',flush=True)
            dump(OUT/'raw_observations.partial.json',rows)
    hand.close()
    dump(OUT/'raw_observations.json',rows)
    dump(OUT/'setup.json',dict(config=CONFIG,hardware=platform.platform(),torch=torch.__version__,ultralytics=ultralytics.__version__,mediapipe=mp.__version__,device='CPU',torchThreads=1,warmupFramesPerModel=2,handMode='IMAGE',clips=CLIPS,studyType='Exploratory reused public video; no independent ground truth',objectModels=['yolo11n-seg.pt','yoloe-11s-seg-pf.pt']))
    (OUT/'raw_observations.partial.json').unlink(missing_ok=True)
    print('DONE raw observations',flush=True)


if __name__=='__main__':
    run()
