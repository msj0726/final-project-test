"""Reproduce tracking comparison on the same cached observations; no inference."""
import copy,json
from collections import Counter
from vision_decision_study import OUT
from vision_study import dump
from process_vision_decisions import track_and_measure,make_events
rows=json.loads((OUT/'observations.json').read_text())
comparison={}
for key,gap,minimum in [('strict',0,6),('gap04SixSamples',.4,6),('gap04FourSamples',.4,4)]:
 data=[]
 for clip in dict.fromkeys(r['clipId'] for r in rows):
  data+=track_and_measure(copy.deepcopy([r for r in rows if r['clipId']==clip]),minimum_samples=minimum,max_gap_seconds=gap)
 near=[o for r in data for o in r['objectsStandard'] if o['isWristNearObject'] is True]
 events=[]
 for clip in dict.fromkeys(r['clipId'] for r in data):
  found,_=make_events([r for r in data if r['clipId']==clip],clip);events+=found
 comparison[key]=dict(trackCount=len({o['objectTrackId'] for r in data for o in r['objectsStandard']}),nearDetectionCount=len(near),reasons=dict(Counter(o['comotionReason'] for o in near)),interactionCandidates=sum(e['kind']=='OBJECT_INTERACTION_CANDIDATE' for e in events))
comparison['note']='Same cached selected-model outputs. Gap-ID retention and 4-of-6 temporal observations separated in three variants; no coordinate interpolation.'
dump(OUT/'tracking_comparison.json',comparison)
print(json.dumps(comparison,indent=2))
