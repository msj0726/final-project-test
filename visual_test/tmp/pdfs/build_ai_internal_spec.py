from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path('/Users/minseojang/Documents/ChatGPT/final-project')
OUTPUT = ROOT / 'output/pdf/ProPitch_AI_내부_API_명세_v1.0.pdf'
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('Korean', '/System/Library/Fonts/Supplemental/AppleGothic.ttf'))
pdfmetrics.registerFontFamily('Korean', normal='Korean', bold='Korean', italic='Korean', boldItalic='Korean')

INK = colors.HexColor('#172A43')
BLUE = colors.HexColor('#235EA7')
LIGHT = colors.HexColor('#EAF2FC')
PALE = colors.HexColor('#F4F7FB')
LINE = colors.HexColor('#C8D5E3')
ORANGE = colors.HexColor('#FFF2D9')
MUTED = colors.HexColor('#4E6380')

styles = {
    'title': ParagraphStyle('title', fontName='Korean', fontSize=22, leading=31, textColor=INK, spaceAfter=7),
    'subtitle': ParagraphStyle('subtitle', fontName='Korean', fontSize=10.4, leading=16, textColor=MUTED, spaceAfter=18),
    'h1': ParagraphStyle('h1', fontName='Korean', fontSize=14, leading=20, textColor=BLUE, spaceBefore=4, spaceAfter=8),
    'h2': ParagraphStyle('h2', fontName='Korean', fontSize=10.6, leading=16, textColor=INK, spaceBefore=9, spaceAfter=5),
    'body': ParagraphStyle('body', fontName='Korean', fontSize=8.45, leading=13.4, textColor=INK, spaceAfter=5),
    'small': ParagraphStyle('small', fontName='Korean', fontSize=7.6, leading=11.3, textColor=INK, spaceAfter=3),
    'tablehead': ParagraphStyle('tablehead', fontName='Korean', fontSize=7.8, leading=11.4, textColor=INK),
    'table': ParagraphStyle('table', fontName='Korean', fontSize=7.45, leading=11.2, textColor=INK),
    'callout': ParagraphStyle('callout', fontName='Korean', fontSize=8.2, leading=13, textColor=INK),
}


def p(text, style='body'):
    return Paragraph(text, styles[style])


def section(title):
    return [p(title, 'h1'), HRFlowable(width='100%', thickness=0.7, color=LINE, spaceAfter=9)]


def sub(title):
    return p(title, 'h2')


def bullet(text):
    return p('• ' + text, 'body')


def table(headers, rows, widths):
    data = [[p(h, 'tablehead') for h in headers]] + [[p(str(c), 'table') for c in row] for row in rows]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PALE]),
        ('GRID', (0, 0), (-1, -1), 0.35, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return t


def callout(text, background=ORANGE):
    t = Table([[p(text, 'callout')]], colWidths=[170 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), background),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return t


def code(lines):
    t = Table([[Preformatted('\n'.join(lines), ParagraphStyle('code', fontName='Courier', fontSize=7, leading=10, textColor=INK))]], colWidths=[170 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PALE),
        ('BOX', (0, 0), (-1, -1), 0.4, LINE),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return t


story = []

# 1. Scope and architecture
story += [p('ProPitch AI 내부 API 명세', 'title'), p('v1.0  ·  ERD v7 / 사용자 API v3.4 정합 제안  ·  2026-11-09', 'subtitle')]
story += [callout('<b>결정:</b> analysis-api는 작업 단위 HTTP 계약을 제공한다. STT, 음향, 자세, 얼굴, 특징 결합, 루브릭 채점, LLM 피드백은 같은 분석 작업 안의 단계 계약으로 정의한다. 단계마다 별도 HTTP 서버를 만드는 것은 MVP1 범위가 아니다.', LIGHT), Spacer(1, 12)]
story += section('1. 목적과 범위')
story += [p('발표 영상의 관찰 가능한 음성·영상 행동 특징을 시간축에 맞춰 추출하고, COMMON/EXPERT 루브릭의 점수를 계산한 뒤, LLM이 근거와 코칭을 문장으로 설명한다. 최종 숫자 점수는 루브릭 채점 단계에서 확정한다.')]
story += [table(['포함', 'MVP1에서 제외'], [
    ('MP4/MOV 영상, 음성 추출, 프레임 샘플링', '발표 내용의 사실성·논리성·자료와의 의미 비교'),
    ('STT·필러, 속도·침묵·음량·음높이 등 음향 관찰', '표정에서 감정·자신감을 직접 측정했다는 주장'),
    ('자세·움직임·제스처·시선/얼굴 방향 관찰', '얼굴 인식·개인 식별, 별도 평가자 채점'),
    ('관찰 신호에 적용 가능한 COMMON/EXPERT 기준 채점', '의미 평가가 필요한 루브릭 항목의 억지 점수화'),
], [85 * mm, 85 * mm]), Spacer(1, 10)]
story += [callout('<b>기존 문서와 충돌:</b> 사용자 API v3.4는 READY PDF 자료가 있으면 <b>contentCheck</b>를 생성한다고 적었다. 이 그림의 MVP1은 의미 평가를 제외한다. 따라서 본 명세 적용 시 <b>contentCheck=null</b>, <b>expectedQuestions=[]</b>로 고정하고, 사용자 API의 해당 설명·화면 안내를 함께 수정해야 한다.')]
story += [Spacer(1, 11)] + section('2. 흐름과 책임')
story += [table(['순서', '담당 / 결과'], [
    ('api → analysis-api', 'jobId, roundId, 영상 저장소 키, 고정된 채점/모델 버전을 전달'),
    ('전처리', '영상 검증, 오디오 추출, 프레임 샘플링, 공통 시간 기준 설정'),
    ('병렬 분석', 'Audio: STT + 음향 특징 / Video: 자세·제스처 + 얼굴 방향·표정 변화'),
    ('결합 → 채점', '시간 구간별 관찰값 결합, rubric_item_id별 점수와 근거 생성'),
    ('LLM → api', '숫자 점수 변경 없이 설명/코칭 생성; 콜백과 결과 검증 후 리포트 공개'),
], [40 * mm, 130 * mm])]
story.append(PageBreak())

# 2. Submission and polling
story += section('3. 서비스 간 HTTP API')
story += [p('기본 경로: analysis-api의 <b>/analysis</b>. 사용자 JWT는 받지 않는다. api와 analysis-api 사이에서 TLS 및 서비스 전용 인증을 사용한다. JSON은 UTF-8, 시각은 UTC ISO 8601, ID는 UUID다.')]
story += [sub('3.1 POST /analysis/jobs - 분석 작업 접수')]
story += [table(['필드', '필수 / 제약'], [
    ('jobId', '필수 UUID. analysis_jobs.id와 같음. 같은 ID + 같은 본문은 멱등 처리'),
    ('analysisId', '필수 UUID. rounds.id와 같음'),
    ('attempt', '필수 정수 1 또는 2. analysis_jobs.attempt와 같음'),
    ('videoKey', '필수 승인된 영상 저장소 키. URL이나 로컬 경로 불가'),
    ('targetMinutes', '선택 정수 0 이상. 생략 시 0; 0이면 시간 차이 null'),
    ('modelVersion', '필수. 서비스 공통 AI 번들 버전; 영상별 AI 설정이 아님'),
    ('scoringPolicyVersion', '필수. COMMON/EXPERT 루브릭 ID·가중치의 고정 버전'),
    ('commonRubricVersion, expertRubricVersion', '필수. 정책이 참조하는 버전과 일치해야 함'),
    ('materialKeys', '선택 배열. v3.4 호환을 위해 수신하되 MVP1에서는 읽거나 평가하지 않음'),
], [60 * mm, 110 * mm])]
story += [Spacer(1, 7), code([
    'POST /analysis/jobs',
    '{',
    '  "jobId": "11111111-1111-4111-8111-111111111111",',
    '  "analysisId": "22222222-2222-4222-8222-222222222222",',
    '  "attempt": 1, "videoKey": "rounds/2222/video.mp4",',
    '  "materialKeys": [], "targetMinutes": 10,',
    '  "modelVersion": "m1", "scoringPolicyVersion": "sp1",',
    '  "commonRubricVersion": "c1", "expertRubricVersion": "e1"',
    '}',
    '202 {"jobId":"11111111-1111-4111-8111-111111111111",',
    '     "status":"QUEUED","attempt":1}',
]), Spacer(1, 8)]
story += [p('같은 jobId로 동일 본문을 다시 보내면 202와 같은 작업을 반환한다. 본문이 다르면 409 JOB_ID_CONFLICT. 버전 불일치 또는 행동 지표로 평가할 수 없는 필수 루브릭 항목은 422 INVALID_SCORING_POLICY. 미디어 내용 검증 실패는 작업 FAILED로 보고한다.')]
story += [sub('3.2 GET /analysis/jobs/{jobId} - 상태/콜백 유실 복구')]
story += [p('200 응답: jobId, analysisId, attempt, status, stage, progress(0~100), failure?, result?를 반환한다. result는 DONE에서만 존재한다. 404는 알 수 없는 jobId. api는 콜백 유실 시 이 경로로 재조회하되, 현재 attempt인지 확인한다.')]
story += [sub('3.3 POST /analysis/jobs/{jobId}/cancel - 삭제 시 취소')]
story += [p('202 응답: 취소 요청 수락. 재요청도 같은 결과. 이미 DONE/FAILED면 상태를 바꾸지 않고 현재 상태를 반환한다. 진행 중 worker는 중간 산출물을 폐기하며 완료 콜백을 보내지 않는다. api는 삭제된 회차의 늦은 콜백을 무시한다.')]
story.append(PageBreak())

# 3. State and callback
story += section('4. 상태와 콜백')
story += [table(['내부 stage', '외부 status', '진행률 예시', '완료 조건'], [
    ('QUEUED', 'QUEUED', '0', '대기열 등록'),
    ('PREPROCESS', 'EXTRACTING', '5~20', '영상 검증·오디오·프레임 준비'),
    ('AUDIO / VIDEO', 'ANALYZING', '20~65', '병렬 분석 결과 확보'),
    ('ALIGN', 'ANALYZING', '65~75', '공통 시간 구간으로 결합'),
    ('RUBRIC', 'SCORING', '75~88', '항목 점수와 근거 확정'),
    ('FEEDBACK', 'SCORING', '88~99', '점수 불변 피드백 생성·검증'),
    ('DONE', 'DONE', '100', '결과 저장·검증 완료'),
    ('FAILED', 'FAILED', '마지막 값', 'failureCode 기록'),
], [39 * mm, 32 * mm, 25 * mm, 74 * mm]), Spacer(1, 10)]
story += [p('AUDIO와 VIDEO는 병렬이며 완료 순서가 바뀔 수 있다. progress는 단조 증가해야 한다. CANCELLED는 analysis-api 내부 취소 상태이고 사용자 API의 공개 상태 목록에 추가하지 않는다.')]
story += [sub('4.1 POST /internal/analysis-jobs/{jobId}/events - analysis-api → api')]
story += [p('이 경로는 api 서버가 수신한다. 이벤트는 at-least-once 전달이므로 eventId로 중복 제거한다. api는 현재 jobId·attempt·삭제 여부·상태 역행을 검사한다. DONE은 결과를 먼저 저장하고 검증한 뒤 발행한다.')]
story += [code([
    '{',
    '  "eventId": "33333333-3333-4333-8333-333333333333",',
    '  "analysisId": "22222222-2222-4222-8222-222222222222",',
    '  "attempt": 1, "status": "ANALYZING",',
    '  "stage": "AUDIO", "progress": 43,',
    '  "occurredAt": "2026-11-09T06:00:00Z"',
    '}',
    'DONE: "status":"DONE", "stage":"DONE", "progress":100,',
    '      "result":{"reportKey":"analysis/.../report.json"}',
    'FAILED: "status":"FAILED",',
    '        "failure":{"code":"STT_TIMEOUT","retryable":true}',
]), Spacer(1, 8)]
story += [table(['상황', 'api 응답·처리'], [
    ('유효한 신규 이벤트', '204; 상태·진행률 갱신. DONE이면 결과 검증·DB 저장까지 성공한 뒤 204'),
    ('동일 eventId / 오래된 attempt / 삭제된 회차', '204; 무해하게 무시, 공개 리포트 재생성 금지'),
    ('결과 형식 또는 점수 검증 실패', '422; analysis-api가 재전송해도 재현되면 운영 오류로 전환'),
    ('api 일시 장애', '5xx; analysis-api가 동일 eventId로 지수 백오프 재전송'),
], [70 * mm, 100 * mm])]
story += [Spacer(1, 8), p('최종 reportKey는 승인된 저장소의 JSON 객체만 가리킨다. callback 본문에 원본 영상·전사 전문을 넣지 않는다. api는 reportKey를 읽어 버전, 점수 범위, 시간 범위, report_scores 항목 집합을 검증한다.')]
story.append(PageBreak())

# 4. Stage contracts
story += section('5. worker 단계별 데이터 계약')
story += [p('단계 사이의 산출물은 analysis-api 내부 객체/JSON 계약이다. 별도 HTTP endpoint를 추가하지 않는다. 각 단계는 jobId, stage, schemaVersion, modelVersion, inputDigest, startedAt, finishedAt, quality, limitations를 공통 메타데이터로 기록한다.')]
story += [table(['단계', '필수 출력', '검증'], [
    ('PREPROCESS', 'durationSec; audioKey; frameManifest; timebase=VIDEO_START; samplingConfig{fps, windowSec, hopSec}', '실제 미디어가 MP4/MOV, ≤500 MiB·≤3600 s. 시작 시각 0; 구간 [startSec,endSec).'),
    ('STT', 'utterances[{startSec,endSec,text,words[]}]; fillers[{startSec,endSec,label}]', '각 단어·필러 구간이 원본 길이 안에 있고 시간 순서가 맞음.'),
    ('ACOUSTIC', 'windows[{startSec,endSec,speechRateWpm,pauseRatio,volumeDb,pitchHz,pitchVariation}]', '측정 불가능한 값은 null + reason. 0으로 대체하지 않음.'),
    ('POSE_GESTURE', 'windows[{startSec,endSec,postureStability,movement,gestureFrequency,bodyOrientation}]', '프레임 표본 수·가시성 기록. 화면 밖/가림을 낮은 점수로 오해하지 않음.'),
    ('FACE_EXPRESSION', 'windows[{startSec,endSec,faceVisibleRatio,expressionChange,gazeDirection,faceDirection}]', '비가시 구간은 null + reason. 감정·성격·자신감 단정 금지.'),
    ('ALIGN', 'windows[{startSec,endSec,audioFeatures,videoFeatures,coverage,missingSignals}]', '오디오/비디오 구간은 공통 영상 시작 시각과 동일 windowSec/hopSec 사용.'),
], [32 * mm, 83 * mm, 55 * mm])]
story += [Spacer(1, 8), callout('<b>전처리 고정값:</b> fps, windowSec, hopSec, 오디오 샘플링 레이트는 배포된 modelVersion의 공통 설정으로 고정하고 결과 메타데이터에 기록한다. 영상별 수동 조정값으로 점수를 바꾸지 않는다.', LIGHT)]
story += [Spacer(1, 10), sub('5.1 관찰 신호의 해석 한계')]
story += [bullet('STT 텍스트는 말하기 속도·필러·구간 정렬에 사용한다. 발표 내용의 의미·사실성·자료 일치도 점수에는 사용하지 않는다.')]
story += [bullet('“자신감”, “전달력” 등 상위 용어는 관찰 신호의 조합을 설명할 때만 쓴다. 단일 센서의 직접 측정값처럼 반환하지 않는다.')]
story += [bullet('카메라 각도·조명·소음·화자 중첩·가려짐은 limitations에 명시한다. 채점에 필수인 신호가 없으면 임의 점수를 만들지 않고 FAILED로 종료한다.')]
story.append(PageBreak())

# 5. Scoring and result
story += section('6. 루브릭 채점·LLM 피드백')
story += [sub('6.1 RUBRIC 단계 - 숫자 점수의 유일한 생산자')]
story += [bullet('작업 시작 전에 정책 버전이 COMMON/EXPERT 루브릭과 일치하는지 확인한다. 각 rubric_item의 scoring_guide가 MVP1의 관찰 가능한 신호로 평가 가능한지 사전 검증한다.')]
story += [bullet('각 항목 결과: rubricItemId, score(0~100 정수), evidence[{fromSec,toSec,signal,observedValue,reason}], quality. 근거는 실제 산출한 신호와 영상 시간 구간을 참조한다.')]
story += [bullet('commonScore/expertScore = 각 루브릭 항목의 가중 평균을 반올림한 0~100 정수. totalScore = commonScore×commonWeight + expertScore×expertWeight를 마지막에 한 번 반올림한다. 정책 가중치 합은 1.')]
story += [bullet('필수 항목을 채점할 신호가 없거나 의미 평가가 필요한 항목이면 FAILED(UNSCORABLE_RUBRIC_ITEM). “미측정=0점”으로 처리하지 않는다.')]
story += [sub('6.2 FEEDBACK 단계 - 숫자 점수 변경 금지')]
story += [p('LLM 입력은 버전이 고정된 항목별 점수·근거·시간 구간·관찰 한계만이다. 출력은 strengths[], improvements[], actions[], segmentFeedback[] 및 itemExplanations[]이다. LLM의 자유 문장을 근거·측정값으로 재사용하지 않는다. 검증기는 근거 없는 숫자, 없는 시각, 점수 변경, 의미 평가 문장을 거부한다.')]
story += [callout('<b>실패 분기:</b> 채점 성공 후 LLM만 실패하면 승인된 규칙형 문장으로 대체하고 quality=DEGRADED, limitations에 FEEDBACK_FALLBACK을 기록한다. 채점에 필수인 신호가 없으면 리포트를 만들지 않는다.')]
story += [Spacer(1, 9), sub('6.3 DONE 결과 계약 - 기존 reports / report_scores / report_segments와 연결')]
story += [table(['필드', '출처 / 저장 위치'], [
    ('analysisId, jobId, versions', 'rounds.id, analysis_jobs.id, 고정된 model/policy/rubric 버전'),
    ('commonScore, expertScore, totalScore', 'RUBRIC 결과 → reports 3개 점수'),
    ('scores[]', 'rubricItemId·score·evidence → report_scores; 항목 집합은 정책과 일치'),
    ('segments[]', 'fromSec·toSec·kind·feedback → report_segments'),
    ('timeline', '시간 구간별 특징 요약 → reports.timeline'),
    ('coaching', 'strengths·improvements·actions → reports.coaching 제안'),
    ('contentCheck, expectedQuestions', 'MVP1 고정 null, []'),
    ('quality, limitations', 'NORMAL/DEGRADED 및 관찰 한계 → reports 기존 필드'),
], [66 * mm, 104 * mm])]
story += [Spacer(1, 7), p('동일 회차에는 공개 reports가 최대 1개다. 재시도 결과가 도착해도 현재 attempt만 반영한다. 실패한 작업의 점수나 일부 단계 결과를 완료 리포트처럼 공개하지 않는다.')]
story += [PageBreak(), sub('6.4 DONE result JSON 예시'), p('형식 설명용 예시다. 실제 응답은 활성 정책의 모든 rubric_item을 scores에 포함해야 한다.', 'small'), code([
    'report.json (illustrative values)',
    '{"analysisId":"<round UUID>","jobId":"<job UUID>",',
    ' "commonScore":80,"expertScore":70,"totalScore":74,',
    ' "versions":{"model":"m1","scoringPolicy":"sp1",',
    '   "commonRubric":"c1","expertRubric":"e1"},',
    ' "scores":[{"rubricItemId":"<item UUID>","score":80,',
    '   "evidence":[{"fromSec":12.0,"toSec":18.0,',
    '     "signal":"speechRateWpm","observedValue":138,',
    '     "reason":"rubric threshold matched"}]},',
    '   {"rubricItemId":"<expert item UUID>","score":70,',
    '    "evidence":[{"fromSec":40.0,"toSec":48.0,',
    '      "signal":"pauseRatio","observedValue":0.24,',
    '      "reason":"rubric threshold matched"}]}],',
    ' "coaching":{"strengths":[],"improvements":[],"actions":[]},',
    ' "segments":[],"timeline":{"speechRate":[],"gaze":[]},',
    ' "targetMinutes":10,"timeDeltaMinutes":0.5,',
    ' "contentCheck":null,"expectedQuestions":[],',
    ' "quality":"NORMAL","limitations":[]}',
])]

# 6. Errors, acceptance and ERD
story += section('7. 오류·재시도·운영 규칙')
story += [table(['코드', '재시도', '처리'], [
    ('INVALID_MEDIA / LIMIT_EXCEEDED', '아니오', '파일·길이·코덱 등 입력 오류. 업로드 사전 검증과 중복 확인'),
    ('INVALID_SCORING_POLICY / UNSCORABLE_RUBRIC_ITEM', '아니오', '정책/기준 수정 후 새 작업으로 재실행'),
    ('STT_TIMEOUT / MODEL_UNAVAILABLE / STORAGE_TIMEOUT', '예', 'api의 자동 재시도 최대 1회; 새 jobId, attempt=2'),
    ('INSUFFICIENT_REQUIRED_SIGNAL', '아니오', '필수 신호 부재. 점수 생성 금지'),
    ('FEEDBACK_FALLBACK', '작업 실패 아님', '정해진 문장으로 대체; quality=DEGRADED'),
], [66 * mm, 27 * mm, 77 * mm]), Spacer(1, 10)]
story += [p('동시 실행 상한 3개와 나머지 QUEUED는 사용자 API v3.4를 따른다. 단계 내부 재시도는 동일 attempt의 일시 오류에 한정하고, 사용자 API의 attempt 재시도 횟수와 별개로 중복 결과가 생기지 않도록 jobId로 묶는다.')]
story += [sub('7.1 수락 기준')]
story += [bullet('같은 jobId 재접수와 동일 eventId 재전송에도 job/report가 중복되지 않는다.')]
story += [bullet('모든 점수에는 실제 시간 범위·관찰 신호·루브릭 항목 ID가 연결된다. LLM 출력은 숫자 점수를 바꾸지 않는다.')]
story += [bullet('자료 PDF가 있어도 MVP1 결과는 contentCheck=null, expectedQuestions=[]다. 의미 평가 화면은 표시하지 않는다.')]
story += [bullet('필수 신호 결손은 FAILED, 선택 신호 결손은 null+limitations로 기록한다. 시간 범위·버전·가중치·점수 범위를 검증한 뒤 DONE을 공개한다.')]
story += [sub('7.2 보안·보존')]
story += [p('내부 서비스 인증, 승인된 저장소 키 prefix, 최소 권한 객체 접근을 적용한다. 원본 영상·전사 전문·얼굴 프레임을 API 로그/콜백에 기록하지 않는다. 중간 산출물은 저장소 수명 정책으로 정리하고, 공개 리포트에 필요한 근거만 DB에 남긴다.')]
story += [PageBreak()] + section('8. ERD v7 변경 권고 - 아직 적용하지 않음')
story += [table(['우선순위', '변경', '이유'], [
    ('필수', 'report_scores.evidence jsonb NOT NULL', '항목 점수와 실제 관찰 신호·구간을 연결. 단순 score만으로 근거를 재현할 수 없음.'),
    ('필수', 'reports.coaching jsonb NOT NULL', '최종 강점·개선점·실행 코칭을 구조적으로 저장. 기존 limitations는 품질 한계용.'),
    ('선택', 'analysis_jobs.stage varchar', 'AUDIO/VIDEO/ALIGN 등 현재 단계를 운영 화면/콜백 유실 복구에서 구분할 때만 필요.'),
    ('추후', 'analysis_stage_runs 별도 테이블', '단계별 재시작·비용·지연 통계가 실제 운영 요구가 될 때 추가.'),
], [20 * mm, 62 * mm, 88 * mm])]
story += [Spacer(1, 7), p('STT/자세/얼굴별 테이블은 MVP1에서 추가하지 않는다. 시간축 특징은 기존 reports.timeline으로, 점수 근거는 report_scores.evidence로 충분하다. reports.content_check는 삭제보다 null 유지가 v3.4 응답 호환에 안전하다.')]
story += [Spacer(1, 10), callout('<b>출처와 확정 필요 사항:</b> 제공된 파이프라인 그림, ERD v7, 사용자 API v3.4를 기준으로 작성했다. 점수 구간별 세부 채점 규칙, 관찰 신호 임계값, 배포 modelVersion의 fps/windowSec/hopSec 값은 아직 미정이며 활성 루브릭 등록 전에 확정·검증해야 한다.', LIGHT)]


def page_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(20 * mm, 17 * mm, 190 * mm, 17 * mm)
    canvas.setFont('Korean', 7.2)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 12.5 * mm, 'ProPitch · AI 내부 API 명세 v1.0 · 제안안')
    canvas.drawRightString(190 * mm, 12.5 * mm, f'{doc.page}')
    canvas.restoreState()


doc = SimpleDocTemplate(
    str(OUTPUT), pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
    topMargin=18 * mm, bottomMargin=22 * mm, title='ProPitch AI 내부 API 명세 v1.0',
    author='ProPitch 설계 문서',
)
doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
print(OUTPUT)
