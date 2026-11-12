"""Selected-model rerun. Product thresholds are read from explicit user decisions."""
import json
import time
from pathlib import Path
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from vision_study import OLD_ROOT, face_infer, choose_person, associate_face, gaze, object_infer, dump

ROOT=Path(__file__).resolve().parent
PREVIOUS=ROOT/'results/vision_study'
OUT=ROOT/'results/vision_decision_study'


def collect():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((PREVIOUS/'frame_manifest.json').read_text())
    from realtime_yolo_benchmark import attempt_load
    torch.set_num_threads(1)
    pose=YOLO(str(OLD_ROOT/'models/yolo11n-pose.pt'))
    face=attempt_load(str(OLD_ROOT/'models/yolov5n-face.pt'),map_location='cpu').eval()
    objects=YOLO(str(ROOT/'models/yolo11n-seg.pt'))
    first=cv2.imread(str(PREVIOUS/'frames'/manifest[0]['image']))
    for _ in range(2):
        pose.predict(first,device='cpu',imgsz=640,conf=.5,verbose=False)
        face_infer(face,first);object_infer(objects,first)
    rows=[]
    for i,m in enumerate(manifest):
        frame=cv2.imread(str(PREVIOUS/'frames'/m['image']));assert frame is not None
        start=time.perf_counter()
        body,body_reason=choose_person(pose.predict(frame,device='cpu',imgsz=640,conf=.5,verbose=False)[0])
        pose_end=time.perf_counter()
        f=associate_face(face_infer(face,frame),body)
        facing,reason,geometry=gaze(f)
        face_end=time.perf_counter()
        detected=object_infer(objects,frame)
        end=time.perf_counter()
        rows.append(dict(**m,body=body,bodyReason=body_reason,face=f,isCameraFacing=facing,gazeReason=reason,gazeGeometry=geometry,
                         objects=detected,timingMs=dict(pose=(pose_end-start)*1000,face=(face_end-pose_end)*1000,objects=(end-face_end)*1000,pipeline=(end-start)*1000)))
        if (i+1)%50==0:print(f'{i+1}/450 selected-model CPU frames',flush=True)
    assert len(rows)==450
    dump(OUT/'raw_observations.json',rows)
    print('Selected model rerun complete',flush=True)


if __name__=='__main__':collect()
