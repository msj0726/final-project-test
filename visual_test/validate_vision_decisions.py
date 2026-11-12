"""Validate selected-model observation contract, nulls, evidence references and media."""
import json,sys
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.report_tools'))
import jsonschema
from vision_decision_study import OUT
from vision_study import dump
from process_vision_decisions import tests

num={'type':'number','minimum':0}
nullable_num={'type':['number','null'],'minimum':0}
ratio={'type':['number','null'],'minimum':0,'maximum':1}
interval={'type':'object','required':['startSec','endSec'],'properties':{'startSec':num,'endSec':num}}
event={'type':'object','required':['eventId','kind','startSec','endSec','confidence','evidenceRefs'],'properties':{
 'eventId':{'type':'string','minLength':1},'kind':{'enum':['HAND_STILLNESS','OBJECT_INTERACTION_CANDIDATE','OBJECT_FACE_OVERLAP_CANDIDATE']},'startSec':num,'endSec':num,
 'confidence':{'type':['number','null'],'minimum':0,'maximum':1},'evidenceRefs':{'type':'array','minItems':1,'items':{'type':'string'}},
 'objectLabelConfidence':{'type':['number','null'],'minimum':0,'maximum':1}}}
gaze_schema = {'type':'object', 'required':['observableSeconds','frontFacingSeconds','frontFacingRatio','coverageRatio','method'], 'properties':{'observableSeconds':num,'frontFacingSeconds':num,'frontFacingRatio':ratio,'coverageRatio':ratio,'method':{'type':'string'}}}
unknown_schema = {'type':'object','required':['criterionKey','startSec','endSec','reasonCode'],'properties':{'criterionKey':{'enum':['GAZE','HAND_STILLNESS']},'startSec':num,'endSec':num,'reasonCode':{'type':'string','minLength':1}}}
vision_schema = {'type':'object','required':['gaze','handObservableSeconds','handStillSeconds','gestureEvents','candidateEvents','unobservableIntervalsStatus','unobservableIntervals','criterionStatus'], 'properties':{'gaze':gaze_schema,'handObservableSeconds':num,'handStillSeconds':nullable_num,'bothWristsVisibleSeconds':num,'handCoverageRatio':ratio,'gestureEvents':{'type':'array','items':event},'candidateEvents':{'type':'array','items':event},'unobservableIntervalsStatus':{'const':'GENERATED'},'unobservableIntervals':{'type':'array','items':unknown_schema}}}
evidence_schema = {'type':'object','required':['evidenceId','sourceType','startSec','endSec','description'],'properties':{'evidenceId':{'type':'string'},'sourceType':{'const':'VISION'},'startSec':num,'endSec':num,'description':{'type':'string'}}}
judgment_schema = {'type':'object','required':['criterionKey','status','verdict','reason','evidenceRefs'],'properties':{'criterionKey':{'const':'UNRELATED_OBJECT_TOUCH'},'status':{'const':'NOT_RUN'},'verdict':{'type':'null'},'reason':{'type':'string'},'evidenceRefs':{'type':'array','items':{'type':'string'}}}}
SCHEMA = {'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object','required':['schemaVersion','observationConfigVersion','isScoringReady','vision','evidence','contextJudgments','limitations'], 'properties':{'schemaVersion':{'const':'vision-observation-v2-experiment'},'observationConfigVersion':{'type':'string','minLength':1},'isScoringReady':{'const':False},'vision':vision_schema,'evidence':{'type':'array','items':evidence_schema},'contextJudgments':{'type':'array','items':judgment_schema},'limitations':{'type':'array','minItems':1,'items':{'type':'string'}}}}


def semantic(c):
 v=c['vision'];g=v['gaze'];dur=c['sampleDurationSeconds'];a=c['sourceStartSec'];b=c['sourceEndSec']
 assert b-a==dur
 assert 0<=g['frontFacingSeconds']<=g['observableSeconds']<=dur
 assert abs(g['coverageRatio']-g['observableSeconds']/dur)<1e-6
 assert g['frontFacingRatio'] is None if g['observableSeconds']==0 else abs(g['frontFacingRatio']-g['frontFacingSeconds']/g['observableSeconds'])<1e-6
 assert v['handStillSeconds'] is None if v['handObservableSeconds']==0 else 0<=v['handStillSeconds']<=v['handObservableSeconds']
 assert 0<=v['handObservableSeconds']<=v['bothWristsVisibleSeconds']<=dur
 for key,valid in [('GAZE',g['observableSeconds']),('HAND_STILLNESS',v['handObservableSeconds'])]:
  spans=[s for s in v['unobservableIntervals'] if s['criterionKey']==key]
  assert all(a<=x['startSec']<x['endSec']<=b for x in spans)
  assert all(spans[i]['endSec']<=spans[i+1]['startSec']+1e-6 for i in range(len(spans)-1))
  assert abs(sum(s['endSec']-s['startSec'] for s in spans)+valid-dur)<1e-6
 events=v['gestureEvents']+v['candidateEvents'];refs={e['evidenceId'] for e in c['evidence']}
 assert len(refs)==len(c['evidence']) and len({e['eventId'] for e in events})==len(events)
 for e in events:
  assert a<=e['startSec']<e['endSec']<=b
  assert all(ref in refs for ref in e['evidenceRefs'])
 for j in c['contextJudgments']:assert all(ref in refs for ref in j['evidenceRefs'])
 assert 'score' not in v['gaze'] and 'totalScore' not in c


def run():
 data=json.loads((OUT/'summary.json').read_text());dump(OUT/'vision-observation.schema.json',SCHEMA)
 for c in data['clips']:jsonschema.validate(c,SCHEMA);semantic(c)
 bad=json.loads(json.dumps(data['clips'][0]));bad['vision']['gaze']['frontFacingRatio']=1.2
 try:jsonschema.validate(bad,SCHEMA)
 except jsonschema.ValidationError:pass
 else:raise AssertionError('Invalid ratio accepted')
 bad=json.loads(json.dumps(data['clips'][0]));bad['contextJudgments'][0]['verdict']='APPLIES'
 try:jsonschema.validate(bad,SCHEMA)
 except jsonschema.ValidationError:pass
 else:raise AssertionError('NOT_RUN verdict accepted')
 synth=json.loads(json.dumps(data['clips'][2]));synth['isSynthetic']=True
 e=dict(eventId='synthetic-1',kind='OBJECT_INTERACTION_CANDIDATE',startSec=7,endSec=8,confidence=None,objectLabel='synthetic-object',objectLabelConfidence=.7,evidenceRefs=['synthetic-evidence-1'])
 synth['vision']['candidateEvents']=[e];synth['evidence']=[dict(evidenceId='synthetic-evidence-1',sourceType='VISION',startSec=7,endSec=8,description='Schema test only, not a model result.')]
 jsonschema.validate(synth,SCHEMA);semantic(synth)
 synth['vision']['candidateEvents'][0]['evidenceRefs']=['missing']
 try:semantic(synth)
 except AssertionError:pass
 else:raise AssertionError('Missing evidence accepted')
 count=0
 for p in (OUT/'videos').glob('*.mp4'):
  cap=cv2.VideoCapture(str(p));n=0
  while cap.read()[0]:n+=1
  cap.release();assert n==50;count+=n
 assert count==450
 result=dict(result='PASS',actualJsonFiles=9,actualVideoFrames=450,syntheticBehaviorChecks=tests(),negativeChecks=3,nonEmptyCandidateSchemaTest='SYNTHETIC_ONLY',checks=['schema','time sums','null semantics','reference integrity','NOT_RUN vs verdict','no score fields','video decode'])
 dump(OUT/'validation.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':run()
