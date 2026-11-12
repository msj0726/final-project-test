# 첨부 API 명세 본문 전사

> 파일명은 v3.3이지만 본문은 v3.2입니다. 원문 보존용이며 적용 규칙은 ../SPEC_ALIGNMENT.md를 따릅니다.

ProPitch API 명세 v3.2 — 사용자 API · 질의응답 실시간 중계

Nov 4, 2026 

팀 논의용 · 2026-11-04 · Base URL /api/v1 · 서비스명 ProPitch(가제)

v3.1(FastAPI 사용자 API·실시간 중계)의 구조와 규칙을 유지하고, 서비스 개편을 반영했다. 영상 평가는 업로드 → 분석 → 리포트로만 진행하고, 실시간 구간은 카메라를 켠 턴제 질의응답으로 옮긴다. 기술 계약은 제안이며 미확정 정책은 8장에서 논의한다. 카메라 실시간 세션은 기본 방향으로 가정했으나 세부 전송 방식은 확정 전이다.

변경 요약 (v3.1 → v3.2)

| 구분 | 내용 |
| --- | --- |
| 삭제 | 라이브 리허설 전체: 3-3 live-sessions·chunk·pause/restart·discard/undo, 5장 실시간 피드백(feedback-ticket, metrics/alert), Report.liveAlerts, 연습 mode LIVE |
| 신설 | 5장 질의응답: 시작 자격 확인, 세션·WebSocket 중계, 질문 근거 조회, 별도 질의응답 리포트 |
| 신설 | 3-2 발표 자료 등록(선택, 대외비 확인, RAG 색인 상태), Project.targetMinutes |
| 변경 | 4장 Report에 contentCheck(발표 내용 점검), timeCheck(목표 시간 점검) 추가 |
| 변경 | 6장 평가 제출에 customItems(임의 평가 항목) 추가 |
| 변경 | 7장 관리자 AI 모델 고도화 = 점수 검증(기존) + 평가 항목 후보(신설) + 모델 버전(신설), 대시보드의 discard를 qaUsage로 교체 |
| 유지 | 1~2장 공통·인증, 영상 업로드, 4-1·4-2 내부 분석 연동·재시도(자료 키만 추가), 보정·루브릭, healthz |

핵심 API

서비스의 핵심은 ‘로그인 → 자료 등록(선택) → 영상 업로드 → 분석 → 리포트 → 질의응답 → 질의응답 리포트’ 흐름이다.

| 핵심 기능 | 주요 API | 확인 기준 |
| --- | --- | --- |
| 인증·소유권·동의 | POST /auth/signup, /auth/login, /auth/refresh, GET /me | 로그인한 사용자가 자기 데이터만 접근하고 영상 동의를 확인함 |
| 프로젝트·자료·영상 업로드 | POST /projects, POST /projects/{id}/material, POST /projects/{id}/uploads, POST …/uploads/{uploadId}/complete | 실제 파일 검증 후 회차·분석을 중복 없이 생성하고 자료는 선택 사항으로 처리함 |
| 비동기 분석 연결 | 내부 POST /analysis/jobs, POST /internal/analysis-jobs/{jobId}/events, GET /analyses/{analysisId} | 접수·진행·완료·실패가 연결되고 중복/지연 콜백을 안전하게 처리함 |
| 리포트·영상 재생 | GET /projects/{id}/rounds/{n}/report, GET …/video | 점수·근거·내용 점검·QA가 보이고 근거 장면을 재생할 수 있음 |
| 질의응답 | GET /projects/{id}/qa/eligibility, POST /projects/{id}/qa/sessions, WebSocket, GET /qa/sessions/{sid}/report | 분석된 영상이 있을 때만 시작하고 주제 기반 질문·꼬리 질문·조기 종료·별도 리포트가 동작함 |
| 실패 복구·삭제·운영 확인 | 내부 GET/DELETE /analysis/jobs/{jobId}, 관리자 POST /admin/analyses/{analysisId}/retry, DELETE /projects/{id}/rounds/{n}, GET /healthz | 콜백 유실을 복구하고 삭제 데이터가 재생성되지 않으며 서버 상태를 확인함 |

그 밖의 기능: 이력·비교, 전문가 평가·보정·임의 평가 항목, 관리자 통계·초대·일정. 멱등성·오류 처리·권한·동의·버전 기록은 모든 단계에 함께 적용한다. 카메라 영상 전송 방식·심사위원 표현 방식·점수/폴백 기준은 구현 전에 팀 합의가 필요하다.

1. 공통 규칙

전송·권한: HTTPS/JSON. 공개 API 외 HTTP는 Bearer 인증. USER는 자기 데이터, EXPERT는 자기 배정, ADMIN은 운영 기능만 접근한다. 타인 자원은 404, 역할 불일치는 403이다.

응답: 단건 {data:객체}, 페이지 목록 {data:[],page:{number,size,total}}, 204는 무본문. 목록은 page=0, size=20(최대 100). 도메인 내부 배열은 페이지를 나누지 않는다.

표기: ?는 요청 선택 필드, T/null만 null 허용. 나머지 요청·응답 필드는 필수다. PATCH는 생략값 유지, 최소 한 필드 필요. 배열이 비면 []이고 미정의 요청 필드는 거부한다.

타입: ID·버전·이름·문구는 string, 역할·상태는 표의 enum, 동의·done은 boolean. 회차·seq·generation·attempt는 1 이상 integer, 크기·개수는 0 이상 integer, 시간 길이는 0 이상 number다. 점수는 0~100 integer, 차이는 -100~100 integer다.

날짜: 시각은 UTC RFC 3339, 날짜는 YYYY-MM-DD, month는 YYYY-MM. finalDate만 날짜 또는 null이며 null은 미정/해제를 뜻한다. 화면 시간대·집계 기준은 확인 필요다.

멱등성: 업무 POST는 Idempotency-Key 필수(login/refresh/logout/ws-ticket 제외). 같은 키·같은 요청은 최초 결과, 다른 내용은 409, 처리 중은 409+Retry-After. upload당 회차·분석, 프로젝트당 진행 중 질의응답 세션, assignment당 최종 평가는 하나만 생성한다. 키 보관 기간은 확인 필요다.

삭제·보안: 204 삭제는 즉시 접근 차단·삭제 예약이며 물리 삭제 완료가 아니다. 삭제된 데이터가 비동기 작업으로 재생성되지 않게 한다. 토큰·티켓·서명 URL·영상·음성·발표 자료·질의응답 답변은 로그에 남기지 않는다.

서비스 구분: 아래 사용자·관리자 API는 api(FastAPI 사용자 API 서버)의 /api/v1 기준이다. 4-1의 /analysis/jobs는 별도 analysis-api 서비스 경로, /internal/...은 api의 내부 수신 경로다. 내부 API는 외부 공개·사용자 JWT 접근을 금지하고 TLS와 서비스 전용 인증으로 제한한다.

공통 객체: User{id,name,email,role,createdAt}, Project{id,name,topic,finalDate,targetMinutes,done,createdAt}, TokenPair{accessToken,accessTokenExpiresAt,refreshToken,refreshTokenExpiresAt}, AnalysisRef{projectId,roundNo,analysisId}. 역할은 USER/EXPERT/ADMIN이다. v3.1의 연습 mode(UPLOAD/LIVE)는 삭제되었고 회차는 모두 영상 업로드다. 응답 표는 data 내부 필드를 뜻하며 목록만 공통 page를 갖는다.

| HTTP | 오류 코드·처리 |
| --- | --- |
| 400 | VALIDATION_FAILED / CHECKSUM_MISMATCH / CONFIDENTIAL_NOT_CONFIRMED — 입력 수정 |
| 401 / 403 | UNAUTHENTICATED — refresh 1회 후 로그인 / FORBIDDEN, ACCOUNT_SUSPENDED, CONSENT_REQUIRED |
| 404 / 410 | NOT_FOUND, NO_COMPARABLE_ROUND / ALREADY_DELETED, UPLOAD_EXPIRED |
| 409 | INVALID_STATE, VERSION_MISMATCH, IDEMPOTENCY_CONFLICT, OPERATION_IN_PROGRESS, UPLOAD_INCOMPLETE, REPORT_NOT_READY, VERSION_UNAVAILABLE |
| 409 | QA_NOT_ELIGIBLE, QA_SESSION_ACTIVE, QA_LIMIT_REACHED, QA_SESSION_ENDED |
| 409 | EMAIL_ALREADY_EXISTS, EVALUATION_ALREADY_SUBMITTED, INSUFFICIENT_ELIGIBLE_VIDEOS |
| 413 / 415 / 429 | UPLOAD_TOO_LARGE / UNSUPPORTED_MEDIA / RATE_LIMITED(Retry-After) |
| 500 / 503 | INTERNAL_ERROR / TEMPORARILY_UNAVAILABLE — 같은 업무 키로 안전하게 재시도 |

오류 형식은 아래와 같고 fields는 필드 경로→안내, details는 코드별 객체다. requestId는 응답 헤더 X-Request-Id와 같다.

FastAPI 구현 시 계약 유지: FastAPI의 기본 요청 검증 오류는 422와 detail 형식이므로, 이 명세의 400 VALIDATION_FAILED 및 공통 error 형식을 유지하려면 요청 검증·HTTP 예외 처리기를 공통으로 적용한다. Pydantic 요청 모델은 미정의 필드 거부, 필수·null 구분을 표의 규칙에 맞춘다. 응답 모델·상태 코드·204 무본문도 명세대로 지정한다. FastAPI 오류 처리 문서

{"error":{"code":"QA_NOT_ELIGIBLE","message":"분석이 끝난 발표 영상이 있어야 질의응답을 시작할 수 있어요.","fields":{},"details":{"analyzedRounds":0},"retryable":false,"requestId":"req_example"}}

2. 인증·계정

v3.1과 같다. 질의응답 시작 시 카메라·마이크 동의는 5장에서 따로 받는다.

| 메서드·경로 | 설명 | 요청 | 응답 |
| --- | --- | --- | --- |
| POST /auth/signup | 회원가입 (USER 전용) | name, email, password, agreements{terms,privacy,aiAnalysis,expertReview} | 201 data{user:User} |
| POST /auth/login | 로그인 | email, password | data{user:User,tokens:TokenPair} |
| POST /auth/refresh | 토큰 재발급 (회전) | refreshToken | data{tokens:TokenPair} |
| POST /auth/logout | 로그아웃 | refreshToken | 204 |
| POST /auth/password-reset | 재설정 메일 요청 | email | 202 (가입 여부 비노출) |
| POST /auth/password-reset/confirm | 새 비밀번호 설정 | token, newPassword | 204 |
| GET /me | 내 정보 | - | data{user:User,agreements} |
| PATCH /me | 이름·비밀번호 변경 | name?, currentPassword?, newPassword? | data{user:User} |
| DELETE /me | 탈퇴 (삭제 예약) | password | 204 |

전문 평가자·관리자 계정은 관리자가 7장에서 생성하며 가입 API로 만들 수 없다.

필수 동의 항목: terms, privacy, aiAnalysis 필수, expertReview 선택. 미동의 상태의 업무 API는 403 CONSENT_REQUIRED.

탈퇴 시 영상·발표 자료·질의응답 기록은 삭제 예약되고 즉시 접근이 차단된다.

3. 프로젝트·발표 자료·영상 업로드

3-1. 프로젝트

| 메서드·경로 | 설명 | 요청 | 응답 |
| --- | --- | --- | --- |
| GET /projects | 내 프로젝트 목록 (카드) | status?, page, size | data[{project:Project,roundCount,qaCount,latestScore,materialStatus,qaEligible}] |
| POST /projects | 프로젝트 생성 | name, topic, finalDate?, targetMinutes? | 201 data{project:Project} |
| GET /projects/{projectId} | 상세 | - | data{project:Project,rounds,material,qaEligible} |
| PATCH /projects/{projectId} | 수정 | name?, topic?, finalDate?, targetMinutes?, done? | data{project:Project} |
| DELETE /projects/{projectId} | 삭제 예약 | - | 204 |

targetMinutes는 0이면 제한 없음, 생략 시 30이다. 리포트의 발표 시간 점검 기준으로만 쓰며 업로드를 막지 않는다.

qaEligible은 분석 완료(DONE) 영상이 1개 이상일 때 true다.

v3.1의 mode, 연습 시작(live) 관련 필드는 모두 삭제되었다.

3-2. 발표 자료 (신설, 선택)

| 메서드·경로 | 설명 | 요청 | 응답 |
| --- | --- | --- | --- |
| POST /projects/{projectId}/material | 자료 등록·교체 | multipart: file, confidentialConfirmed=true. Idempotency-Key | 202 data{material{fileName,sizeBytes,indexStatus}} |
| GET /projects/{projectId}/material | 자료 상태 | - | data{material |
| DELETE /projects/{projectId}/material | 자료·색인 삭제 예약 | - | 204 |

confidentialConfirmed가 true가 아니면 400 CONFIDENTIAL_NOT_CONFIRMED. 대외비 자료는 등록하지 않는다는 확인이다.

indexStatus는 NONE, INDEXING, READY, FAILED. READY가 아니면 분석과 질의응답은 자료 없이 진행하며 응답에 materialUsed=false로 표시한다.

허용 파일 형식·크기·보관 기간은 팀 논의 항목이다 (8장).

자료는 프로젝트 생성 시 함께 등록하는 흐름이 기본이지만 API는 생성 이후 등록도 허용한다.

3-3. 영상 업로드 (presigned)

흐름은 v3.1과 같다. 영상 한도(30분 내외, 최대 60분)는 업로드 시작 시 검증한다.

| 메서드·경로 | 설명 | 요청 | 응답 |
| --- | --- | --- | --- |
| POST /projects/{projectId}/uploads | 업로드 시작 | fileName, sizeBytes, contentType, durationSec?, checksum. Idempotency-Key | 201 data{uploadId,roundNo,putUrl,headers,expiresAt} |
| PUT {putUrl} | 영상 직접 전송 (스토리지) | 바이너리 | 200 |
| POST /uploads/{uploadId}/complete | 전송 완료·분석 요청 | etag?. Idempotency-Key | 202 data{analysisRef:AnalysisRef,status:QUEUED} |
| DELETE /uploads/{uploadId} | 업로드 취소 | - | 204 |

한도 초과는 413 UPLOAD_TOO_LARGE, 형식 오류는 415 UNSUPPORTED_MEDIA, 체크섬 불일치는 400 CHECKSUM_MISMATCH.

만료된 putUrl은 410 UPLOAD_EXPIRED, 전송 전 complete는 409 UPLOAD_INCOMPLETE.

같은 uploadId로 회차는 하나만 생성한다.

4. 분석·리포트·이력·일정

4-0. 분석 상태

QUEUED, EXTRACTING, ANALYZING, SCORING, DONE, FAILED. 목표는 30분 내외 영상 기준 30분 이내 완료이고 최대 60분 영상도 수용한다(확인 필요). FAILED는 자동 재시도 1회 후 확정된다.

| 메서드·경로 | 설명 | 요청 | 응답 |
| --- | --- | --- | --- |
| GET /projects/{projectId}/rounds | 회차 목록 | - | data[{roundNo,analysisId,status,progress,totalScore,createdAt}] |
| GET /projects/{projectId}/rounds/{roundNo}/status | 진행 조회 (폴링 3~5초) | - | data{status,progress,stage,etaSec?,failure?{code,retryable}} |
| POST /projects/{projectId}/rounds/{roundNo}/retry | FAILED 재분석 | Idempotency-Key | 202 data{status:QUEUED} |
| GET /projects/{projectId}/rounds/{roundNo}/report | 분석 리포트 | versions? | data{report:Report} |
| GET /projects/{projectId}/compare | 회차 비교 | from, to | data{items[],deltas[]} |
| GET /projects/{projectId}/rounds/{roundNo}/video | 재생 URL | - | data{url,expiresAt} (서명 URL) |
| DELETE /projects/{projectId}/rounds/{roundNo} | 회차·영상 삭제 예약 | - | 204 |
| GET /schedule | 발표 일정 (D-day) | month? | data[{projectId,name,finalDate,dday}] |

완료 이전 report는 409 REPORT_NOT_READY. 삭제된 회차는 410 ALREADY_DELETED.

compare는 두 회차가 모두 DONE일 때만 허용하고 아니면 404 NO_COMPARABLE_ROUND.

v3.1의 중도 종료(discarded) 목록과 실시간 경고(liveAlerts)는 삭제되었다.

4-0a. Report 객체

{"report":{ "analysisId":"an_01","projectId":"p_01","roundNo":2,"status":"DONE", "totalScore":78, "scores":{"delivery":80,"structure":74,"visual":76,"voice":82}, "segments":[{"fromSec":0,"toSec":45,"kind":"INTRO","feedback":"..."}], "timeline":{"speed":[],"pause":[],"gaze":[]}, "targetMinutes":30, "timeCheck":{"actualMinutes":27.5,"deltaMinutes":-2.5,"withinRange":true}, "contentCheck":{  "materialUsed":true,  "messages":[{"text":"핵심 메시지","state":"COVERED"}],  "mismatches":[{"atSec":312,"slide":8,"text":"자료와 다른 수치"}] }, "expectedQuestions":[{"kind":"TECH","text":"..."}], "quality":{"level":"NORMAL","notes":[]}, "limitations":["..."], "versions":{"model":"m1","rubric":"r1","calibration":"c1"}}}

contentCheck는 자료가 READY일 때 생성하고 아니면 null이다. state는 COVERED, PARTIAL, MISSING.

timeCheck.deltaMinutes는 실제에서 목표를 뺀 값이고 targetMinutes가 0이면 이 필드는 null이다.

점수·피드백은 통계 근거 없이 수치를 만들지 않고, 품질 저하 시 quality와 limitations에 이유를 남긴다.

4-1. 내부 분석 연동 (api ↔ analysis-api)

| 서비스 | 메서드·경로 | 설명 |
| --- | --- | --- |
| analysis-api | POST /analysis/jobs | 작업 생성: jobId, analysisId, videoKey, materialKey?, targetMinutes?, versions |
| analysis-api | GET /analysis/jobs/{jobId} | 작업 상태 조회 |
| analysis-api | POST /analysis/jobs/{jobId}/cancel | 취소 |
| api | POST /internal/analysis-jobs/{jobId}/events | 진행·완료·실패 보고 (status, progress, result?, failure?) |

events는 중복 수신을 허용하므로 eventId로 멱등 처리하고, 순서가 바뀔 낮은 상태는 버린다.

materialKey가 있으면 analysis-api가 발표 내용 점검(contentCheck)에 사용하고, 없으면 contentCheck는 null로 완료한다.

4-2. 실패·재시도·동시성

자동 재시도는 1회(attempt 최대 2)이고 일시 장애(retryable=true)만 대상이다. 입력 오류는 재시도하지 않는다.

동시 분석 작업은 3개이며 초과분은 QUEUED로 대기한다. 질의응답 세션 동시 수는 별도 한도가 필요하다(8장).

수동 재분석은 사용자가 retry를 호출할 때만 하며 이전 attempt 결과는 보존하지 않는다.

세 버전(model, rubric, calibration)은 작업 생성 시점에 고정하고 리포트에 그대로 남긴다.

5. 질의응답 (카메라 실시간 세션)

영상 분석이 끝난 프로젝트에서만 시작한다. 기본 기준은 가장 최근 DONE 회차이고 회차를 고를 수 있다. 세션 방식(카메라 전송·심사위원 표현)은 기본 방향이며 세부는 확정 전이다(8장).

5-1. 세션 REST

| 메서드·경로 | 설명 | 요청 | 응답 |
| --- | --- | --- | --- |
| GET /projects/{projectId}/qa/eligibility | 시작 가능 여부 | - | data{eligible,rounds[{roundNo,analysisId,createdAt}],defaultRoundNo,materialStatus} |
| POST /projects/{projectId}/qa/sessions | 세션 생성 | baseRoundNo?, consentCameraMic(true). Idempotency-Key | 201 data{sessionId,status:READY,plan,wsUrl,wsTicket,wsTicketExpiresAt} |
| GET /qa/sessions/{sessionId} | 세션 조회 | - | data{session} |
| POST /qa/sessions/{sessionId}/ticket | WS 티켓 재발급 (재연결) | - | data{wsTicket,wsTicketExpiresAt} |
| POST /qa/sessions/{sessionId}/more | 추가 질문 요청 (REST 대체 경로) | Idempotency-Key | 202 data{askedCount,maxQuestions} |
| POST /qa/sessions/{sessionId}/end | 여기서 마치기 | Idempotency-Key | 202 data{status:ENDED,reportReady} |
| GET /qa/sessions/{sessionId}/questions/{questionId}/evidence | 질문 근거 (요청 때만) | - | data{evidence[{kind:ANALYSIS or MATERIAL,ref,excerpt}]} |
| GET /qa/sessions/{sessionId}/report | 질의응답 리포트 | - | data{report:QaReport} |
| GET /projects/{projectId}/qa/sessions | 세션 목록 | page, size | data[{sessionId,baseRoundNo,status,askedCount,createdAt}] |
| DELETE /qa/sessions/{sessionId} | 세션·기록 삭제 예약 | - | 204 |

분석 완료 회차가 없으면 409 QA_NOT_ELIGIBLE, 진행 중 세션이 있으면 409 QA_SESSION_ACTIVE.

근거는 기본으로 질문 객체에 내려주지 않는다(evidenceAvailable만). 사용자가 보기를 누를 때 위 경로로 받는다.

세션 상태는 READY, LIVE, WRAP_UP, ENDED. ENDED 이후 요청은 409 QA_SESSION_ENDED.

plan 객체:

{"plan":{ "plannedCount":6,"maxQuestions":10, "topics":[  {"topicId":"t1","kind":"TECH","title":"점수 산출 기준","status":"PENDING"},  {"topicId":"t4","kind":"BIZ","title":"목표 사용자","status":"PENDING"} ]}}

기본은 기술 3 + 사업 3이고 LLM이 늘리거나 줄일 수 있다(plan_updated 이벤트로 알린다). topic status는 PENDING, ASKED, DONE, SKIPPED.

maxQuestions는 꼬리 질문과 추가 질문을 포함해 10이며 도달하면 추가 요청은 409 QA_LIMIT_REACHED.

5-2. 실시간 중계 (WebSocket)

구조는 v3.1의 실시간 중계와 같다: 브라우저 ↔ FastAPI api ↔ analysis-api. 연결 주소는 wss://{host}/api/v1/qa/sessions/{sessionId}/stream?ticket={wsTicket}이다.

티켓은 1회용이고 만료가 짧다. 재사용하면 연결을 거부한다. 토큰은 URL에 넣지 않는다.

종료 코드: 4401 인증 실패·티켓 만료, 4403 권한 없음, 1008 정책 위반, 1009 메시지 크기 초과, 1011 서버 오류.

세션당 동시 연결은 1개이고 새 연결이 오면 이전 연결을 닫는다. 끊긴 뒤 재연결은 ticket 재발급 후 가능하며 진행 중인 질문 상태는 서버가 복원한다(복원 범위는 확인 필요).

| 방향 | 이벤트 | 페이로드 |
| --- | --- | --- |
| client to server | config | audioCodec, videoMode(NONE or FRAME or STREAM), sampleRate |
| client to server | audio_frame | seq, data (마이크 오디오) |
| client to server | video_frame | seq, ts, data (카메라, 전송 방식 확정 전) |
| client to server | answer_start / answer_end | questionId |
| client to server | request_more | - (추가 질문) |
| client to server | end_early | - (여기서 마치기) |
| server to client | question | questionId, topicId, text, followUp, followUpKind(CLARIFY or DEEPEN), evidenceAvailable, index, maxQuestions |
| server to client | caption | questionId, text (질문 음성 자막, 선택) |
| server to client | plan_updated | plan |
| server to client | wrap_up | reason(PLAN_DONE or LIMIT), summaryReady |
| server to client | ended | reportReady, endedEarly |
| server to client | status | status, ts |
| server to client | error | code, message, retryable |

답변 종료(answer_end) 후 LLM이 답변의 불분명·부족 여부를 판단해 꼬리 질문(followUp=true)을 보내거나 다음 핵심 주제로 넘어간다.

모든 계획 주제를 다루면 wrap_up을 보내고, 사용자는 추가 질문 또는 마치기를 고른다. 조기 종료된 주제는 SKIPPED로 기록한다.

실시간 점수·판정 피드백은 보내지 않는다. 평가는 종료 후 리포트에서만 제공한다.

미확정 (합의 필요): 카메라 영상 전송 방식(WebSocket 프레임, WebRTC, 녹화 후 업로드), 심사위원의 화면 표현(음성만, 아바타, 텍스트 자막), 답변 음성 STT 범위, 녹화본 보관 여부.

5-3. QaReport 객체

{"report":{ "sessionId":"qa_01","projectId":"p_01","baseRoundNo":2, "askedCount":8,"plannedCount":6,"addedCount":2,"endedEarly":false, "topics":[  {"topicId":"t1","kind":"TECH","title":"점수 산출 기준","result":"SUFFICIENT","comment":"..."},  {"topicId":"t5","kind":"BIZ","title":"확장 계획","result":"SKIPPED","comment":null} ], "summary":{  "structure":{"level":"GOOD","comment":"..."},  "consistency":{"level":"FAIR","comment":"..."},  "delivery":null }, "questions":[{"questionId":"q1","topicId":"t1","followUp":false,"text":"...","answerText":"...","evidenceAvailable":true}], "quality":{"level":"NORMAL","notes":[]}, "limitations":["..."], "versions":{"model":"m1","rubric":"r1","calibration":"c1"}}}

result는 SUFFICIENT, NEEDS_WORK, SKIPPED. 다루지 않은 주제는 “진행 안 함”으로 표시한다.

summary.delivery(카메라 기반 전달력)는 영상 전송이 없거나 품질이 낮으면 null이다. 이 항목의 산출 범위는 팀 논의다.

세션이 최소 1문 이상 답변되지 않았으면 리포트는 생성하지 않고 reportReady=false로 끝낸다(확인 필요).

6. 전문 평가자 (EXPERT)

v3.1과 같은 배정 기반 흐름이며 아래 표에서 customItems만 추가되었다. 평가자에게 AI 점수는 노출하지 않는다.

| 메서드·경로 | 설명 | 요청 | 응답 |
| --- | --- | --- | --- |
| GET /expert/assignments | 내 배정 목록 | status?, page, size | data[{assignmentId,status,progress}] + page |
| GET /expert/assignments/{assignmentId} | 배정 상세 (영상 재생 URL·기준) | - | data{assignment,video{url,expiresAt},rubric} |
| PUT /expert/assignments/{assignmentId}/draft | 임시 저장 | scores?, memo?, customItems? | data{savedAt} |
| POST /expert/assignments/{assignmentId}/evaluation | 최종 제출 | scores, memo?, customItems?. Idempotency-Key | 201 data{evaluationId} |
| POST /expert/assignments/{assignmentId}/skip | 건너뛰기 | reason | 204 |
| GET /expert/progress | 진행률 | - | data{done,total} |

scores는 delivery, structure, visual, voice 4항목 0~100 정수다. 이미 제출된 assignment는 409 EVALUATION_ALREADY_SUBMITTED.

customItems (신설): [{name,score}]. 평가자가 임의로 추가한 평가 항목이다. 점수 산식(종합 점수·보정)에는 들어가지 않고, 관리자 후보 목록(7장)으로 전달된다. name은 공백 제외 입력이고 score는 0~100 정수다. 개수 상한과 중복 이름 합치기 규칙은 확인 필요.

임시 저장은 덮어쓰기이며 최종 제출 후에는 수정할 수 없다.

7. 관리자 (ADMIN)

| 메서드·경로 | 설명 | 요청 | 응답 |
| --- | --- | --- | --- |
| GET /admin/dashboard | 이용 현황 | from?, to? | data{users,projects,analyses,successRate,avgDurationSec,qaUsage{sessions,avgAsked,endedEarlyRate}} |
| GET /admin/analyses | 분석 목록 | status?, page, size | data[] + page |
| GET /admin/validation | AI 점수 vs 전문가 검증 | versions?, page, size | data{summary,items[]} |
| GET /admin/calibrations | 보정 이력 | page, size | data[] + page |
| POST /admin/calibrations | 보정 실행 | basis, memo?. Idempotency-Key | 202 data{calibrationId,status} |
| GET /admin/experts | 평가자 목록·현황 | page, size | data[] + page |
| POST /admin/experts | 평가자 계정 생성 | name, email. Idempotency-Key | 201 data{user} |
| POST /admin/assignments | 평가 배정 | expertId, analysisIds. Idempotency-Key | 201 data{created} |
| GET /admin/rubric | 평가 기준 조회 | - | data{rubric{version,items[]}} |
| PUT /admin/rubric | 새 평가 기준 버전 생성 | items[], memo?. Idempotency-Key | 201 data{version} |
| GET /admin/users | 사용자 목록 | role?, status?, page, size | data[] + page |
| PATCH /admin/users/{userId} | 상태·역할 변경 | status? | data{user} |

AI 모델 고도화 (신설)

| 메서드·경로 | 설명 | 요청 | 응답 |
| --- | --- | --- | --- |
| GET /admin/criteria-candidates | 평가 항목 후보 목록 (평가자 customItems 집계) | status?, page, size | data[{candidateId,name,count,avgScore,status}] + page |
| PATCH /admin/criteria-candidates/{candidateId} | 채택 또는 보류 | status(ADOPTED or HELD), memo? | data{candidate} |
| GET /admin/model-versions | 모델·평가기준·보정 버전 목록 | - | data[{version,kind,status,createdAt,validationSummary}] |
| POST /admin/model-versions/{version}/apply | 검증 후 적용 (확인 필요) | memo?. Idempotency-Key | 202 data{version,status} |

후보 status는 NEW, ADOPTED, HELD. 채택은 다음 평가 기준 버전 후보로 등록될 뿐 평가 기준이 자동으로 바뀔 수 없다. 실제 반영은 PUT /admin/rubric으로 새 버전을 만들어서 한다.

적용(apply)의 방식은 새 버전이 이후 분석에만 쓰이는 것을 기본으로 하고 이미 만든 리포트는 유지하는 것이 안전하다. 확정은 팀 논의다. 버전 없는 요청은 409 VERSION_UNAVAILABLE.

v3.1의 중도 종료 집계(discard)는 대시보드에서 빠지고 qaUsage로 대체된다. 질의응답 답변 본문은 관리자 API에 노출하지 않는다.

정합성 부족 시 INSUFFICIENT_ELIGIBLE_VIDEOS(409)는 보정 실행에 쓰는 검증 영상 수가 부족할 때 반환한다.

7-1. 상태 확인

GET /healthz는 인증 없이 생존 여부만 반환한다. GET /readyz는 DB·스토리지·analysis-api 연결을 점검하며 내부 망에서만 열는다. 두 경로는 /api/v1 밖에 둔다.

8. 화면 매핑·팀 논의·구현 검토 체크

8-1. 화면 매핑

| 화면 | 사용 API |
| --- | --- |
| / (메인) | 없음 (정적) |
| /login, /signup | 2장 auth |
| /me (내 프로젝트) | GET /projects, GET /schedule |
| /new (새 연습) | POST /projects, 3-2 material, 3-3 uploads |
| /status/{projectId}/{roundNo} | rounds status, retry |
| /report/{projectId}/{roundNo} | rounds report, video, compare |
| /qa/{projectId} (시작 설정·세션) | qa eligibility, qa sessions, WebSocket stream, evidence |
| /qareport/{projectId}/{sessionId} | qa report |
| /expert, /expert/eval/{assignmentId} | 6장 |
| /admin, /admin/validation, /admin/users 등 | 7장 (검증 탭에 기준 후보·모델 버전) |

삭제된 화면: /live, /discarded.

8-2. 팀 논의 (미확정)

| 항목 | 논의 내용 |
| --- | --- |
| 질의응답 세션 방식 | 카메라 영상 전송 방식, 심사위원 표현(음성·아바타·자막), STT 범위 |
| 꼬리 질문 | 만드는 기준(CLARIFY, DEEPEN), 상한 10개 포함 여부, 핵심 주제 도출 방식 |
| 조기 종료 | 답변 0개일 때 리포트 생성 여부, 미진행 주제 표시 |
| 녹화·전달력 | 세션 녹화 보관 기간, 카메라 기반 전달력 평가 범위 |
| 발표 자료(RAG) | 적용 범위(내용 점검, 질문 생성), 파일 형식·크기, 보관·삭제·갱신, 필수로 바뀔지 |
| 동시 세션 수 | 질의응답 동시 세션 한도와 분석 작업 동시성(3)과의 관계 |
| 임의 평가 항목 | customItems 개수 상한, 중복 이름 합치기, 채택 후 반영 절차 |
| 모델 버전 적용 | apply의 적용 범위(신규 분석만 여부)와 롤백 |
| 영상 한도 | 30분 내외·최대 60분과 처리 시간 목표의 관계 |
| 요구사항 FR-05 | 실시간 피드백 제거에 따른 재확인 |

8-3. 구현 검토 체크

☐ FastAPI 공통 예외 핸들러로 422를 400 VALIDATION_FAILED 형식으로 변환

☐ 업무 POST에 Idempotency-Key 검사 (세션 생성·종료·자료 등록 포함)

☐ 프로젝트당 진행 중 질의응답 세션 1개 제한과 QA_SESSION_ACTIVE

☐ 질문 수 10개 상한을 서버에서 강제 (클라이언트 차단과 별개)

☐ WS 티켓 1회용·만료, 종료 코드 4401/4403/1008/1009/1011 일치

☐ 질문 근거는 요청 때만 반환하고 일반 질문 객체에 포함하지 않음

☐ 발표 자료 대외비 확인(confidentialConfirmed) 검사와 삭제 시 색인 함께 삭제

☐ 영상·음성·자료·답변 본문이 로그·오류 details에 남지 않음

☐ customItems가 점수 산식에 들어가지 않음을 테스트로 보장

☐ 삭제 예약 데이터가 재생성되지 않도록 비동기 작업과 충돌 처리

☐ 화면 매핑의 삭제 화면(/live, /discarded)을 정리
