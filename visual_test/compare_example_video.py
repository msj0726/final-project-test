import sys,json,time,copy
from pathlib import Path
import cv2,numpy as np,mediapipe as mp
sys.path.insert(0,str(Path.cwd()/'backend'))
sys.path.insert(0,str(Path.cwd()/'visual_test'))
from negative_behavior_sample import MODEL_PATHS
import unicodedata
VIDEO=next(p for p in Path("/Users/minseojang/Downloads").glob("*.mov") if unicodedata.normalize("NFC",p.name)=="예시.mov")
from analysis.modules.vision.models import VisionDetectors
from analysis.modules.vision.observation import build_observation,_polygon_overlap
from ultralytics import YOLOE
root=Path('visual_test/results/example_video_comparison');root.mkdir(exist_ok=True)
base=VisionDetectors(MODEL_PATHS)
hand=mp.tasks.vision.HandLandmarker.create_from_options(mp.tasks.vision.HandLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path='visual_test/models/hand_landmarker.task'),num_hands=2))
pose=mp.tasks.vision.PoseLandmarker.create_from_options(mp.tasks.vision.PoseLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATHS.pose.parent/'pose_landmarker_full.task'))))
obj=YOLOE('visual_test/models/yoloe-11s-seg-pf.pt')
cap=cv2.VideoCapture(str(VIDEO));rows=[];target=0
while True:
 ok,im=cap.read()
 if not ok:break
 if cap.get(cv2.CAP_PROP_POS_MSEC)/1000+.001<target:continue
 r=base.detect(im);image=mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(im,cv2.COLOR_BGR2RGB));h,w=im.shape[:2]
 hr=hand.detect(image);pr=pose.detect(image)
 hands=[[[p.x*w,p.y*h] for p in pts] for pts in hr.hand_landmarks]
 t=time.perf_counter();o=obj.predict(im,device='cpu',imgsz=640,conf=.25,verbose=False)[0];elapsed=time.perf_counter()-t
 labels=[o.names[int(b.cls.item())] for b in o.boxes]
 r.update(startSec=target,endSec=round(target+.2,3),hands=hands,mpPose=[[p.x*w,p.y*h,p.visibility] for p in pr.pose_landmarks[0]] if pr.pose_landmarks else [],openLabels=labels,openSeconds=elapsed)
 rows.append(r);target=round(target+.2,3)
 if len(rows)%50==0:print(len(rows),flush=True)
cap.release();(root/'raw.json').write_text(json.dumps(rows))
for name in ['baseline','yolo_hand','mp_pose_hand']:
 rs=copy.deepcopy(rows)
 for r in rs:
  if name=='mp_pose_hand' and r['mpPose'] and r['body']:
   for dst,src in [(5,11),(6,12),(9,15),(10,16)]:r['body']['points'][dst]=r['mpPose'][src][:2];r['body']['confidence'][dst]=r['mpPose'][src][2]
  if name!='baseline' and r['body'] and len(r['hands'])==2:
   # Exploratory assignment by image x; not identity validated.
   for dst,pts in zip((10,9),sorted(r['hands'],key=lambda x:x[0][0])):r['body']['points'][dst]=pts[0];r['body']['confidence'][dst]=1
 out=build_observation(rs,target);out['limitations'].append('Experimental image-x hand assignment; assignment confidence not calibrated')
 (root/(name+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2))
from collections import Counter
summary={'frames':len(rows),'anyHands':sum(bool(r['hands']) for r in rows),'twoHands':sum(len(r['hands'])==2 for r in rows),'mpPose':sum(bool(r['mpPose']) for r in rows),'openLabels':dict(Counter(x for r in rows for x in r['openLabels']))}
summary['occlusionCandidates']=sum(any((_polygon_overlap(cv2.convexHull(np.array(h,dtype=np.float32)).reshape(-1,2).tolist(),r['face']['box']) or 0)>=.1 for h in r['hands']) for r in rows if r['face'])
(root/'summary.json').write_text(json.dumps(summary,indent=2));print(summary)
