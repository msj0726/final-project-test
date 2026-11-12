# ProPitch 사용자 API 명세 v3.5

상태: 팀 검토안 · 기준일: 2026-11-09 · Base URL `/api/v1` · 대응 ERD v9 / AI 내부 API v1.3

***
### 발표자료 입력에 대한 부분과 실시간 질의 관한 부분은 우선 빼고 진행하였습니다.
***

## 1. 범위와 공통 규칙

핵심 흐름은 로그인 → 프로젝트 → 영상 직접 업로드 → 비동기 음성·영상 분석 → 리포트 → 질의응답이다. 사용자 역할은 USER와 ADMIN이다. 숫자 점수는 **단일 루브릭**의 정해진 규칙으로 산출하며 최종 총점과 항목별 점수를 제공한다. LLM은 코칭과 예상 질문을 생성하고 점수를 바꾸지 않는다. 발표 내용 의미 평가·PDF 대조는 이번 발표 분석 범위에 없으며 `contentCheck`는 항상 null이다. 제품의 자료 등록·질의응답 기능은 별도 범위로 유지한다.

공개 API 외 HTTP는 Bearer 인증을 사용한다. USER는 자기 자원만, ADMIN은 운영 기능만 접근한다. 타인 자원은 404, 역할 불일치는 403. 단건 `{data:...}`, 목록 `{data:[],page:{number,size,total}}`, 204는 무본문이다. 시각은 UTC RFC 3339, ID는 UUID 문자열이다. 업무 POST는 `Idempotency-Key` 필수(login/refresh/logout/WS ticket 제외)이며 같은 키·같은 요청은 최초 결과, 다른 내용은 409다. 삭제는 즉시 접근 차단과 삭제 예약을 뜻한다. 영상·전사문·인증 정보는 로그에 남기지 않는다.

오류는 `{error:{code,message,fields,details,retryable,requestId}}` 형식이다. 주요 코드는 `VALIDATION_FAILED`(400), `UNAUTHENTICATED`(401), `FORBIDDEN`/`CONSENT_REQUIRED`(403), `NOT_FOUND`(404), `UPLOAD_EXPIRED`/`ALREADY_DELETED`(410), `UPLOAD_INCOMPLETE`/`REPORT_NOT_READY`/`INVALID_STATE`/`IDEMPOTENCY_CONFLICT`(409), `UPLOAD_TOO_LARGE`(413), `UNSUPPORTED_MEDIA`(415), `RATE_LIMITED`(429), `TEMPORARILY_UNAVAILABLE`(503)다. FastAPI 기본 422 오류는 이 공통 400 형식으로 변환한다.

## 2. 인증·계정

| 메서드·경로 | 요청 | 응답 |
| --- | --- | --- |
| POST `/auth/signup` | name,email,password,agreements,agreementVersions | 201 user |
| POST `/auth/login` | email,password | user,tokens |
| POST `/auth/refresh` | refreshToken | tokens |
| POST `/auth/logout` | refreshToken | 204 |
| POST `/auth/password-reset` | email | 202, 가입 여부 비노출 |
| POST `/auth/password-reset/confirm` | token,newPassword | 204 |
| GET `/me` | — | user,agreements,agreementVersions |
| PATCH `/me` | name?,currentPassword?,newPassword? | user |
| PUT `/me/agreements` | agreements,agreementVersions | 갱신된 동의 |
| DELETE `/me` | password | 204 |

회원가입은 USER만 생성한다. 관리자 계정은 운영 절차로 만든다. 동의는 사용자당 현재 상태 한 행을 유지하며 문서 버전을 기록한다. 과거 동의 이력을 보존하려면 추가 설계가 필요하다.

## 3. 프로젝트·자료

| 메서드·경로 | 요청 | 응답 |
| --- | --- | --- |
| GET `/projects` | status?,page?,size? | 프로젝트 카드 목록 |
| POST `/projects` | name,topic,finalDate?,targetMinutes? | 201 Project |
| GET `/projects/{projectId}` | — | project,rounds,materials,qaEligible |
| PATCH `/projects/{projectId}` | 변경할 필드 | Project |
| DELETE `/projects/{projectId}` | — | 204 |
| POST `/projects/{projectId}/materials` | multipart PDF,confidentialConfirmed=true | 202 자료 정보 |
| GET `/projects/{projectId}/materials` | — | 자료 목록·색인 상태 |
| DELETE `/projects/{projectId}/materials/{materialId}` | — | 204 |

프로젝트 생성 시 활성 단일 루브릭 버전을 `projects.rubric_id`에 고정한다. 활성 루브릭이 없으면 `409 RUBRIC_UNAVAILABLE`. `targetMinutes` 생략 시 30, 0이면 목표 시간 없음. 자료는 프로젝트당 여러 PDF를 등록할 수 있으며 QA 검색에는 사용할 수 있다. 이번 발표 행동 분석 작업에는 PDF를 전달하지 않는다.

## 4. 영상 직접 업로드와 DB 저장

영상은 **FastAPI 사용자 API로 직접 전송**한다. S3 서명 URL·`videoKey`·서명 재생 URL 계약은 사용하지 않는다. 허용 형식은 실제 내용까지 검증한 MP4/MOV, 최대 **500 MiB(524,288,000바이트)·30분**이다. 서버는 업로드 중 요청 크기를 제한하고 완료 시 실제 크기·해시·재생 가능성·길이를 검사한다.

| 메서드·경로 | 요청 | 응답 |
| --- | --- | --- |
| POST `/projects/{projectId}/uploads` | fileName,sizeBytes,contentType,checksum; Idempotency-Key | 201 `{uploadId,roundNo,status:CREATED,expiresAt,uploadPath}` |
| PUT `/uploads/{uploadId}/content` | 영상 바이너리, Content-Type, X-Checksum-Sha256 | 204; 같은 내용 재전송은 동일 결과, 다른 내용은 409 |
| POST `/uploads/{uploadId}/complete` | Idempotency-Key | 202 `{analysisRef:{projectId,roundNo,analysisId},status:QUEUED}` |
| DELETE `/uploads/{uploadId}` | — | 204 |
| GET `/projects/{projectId}/rounds/{roundNo}/video` | 인증, Range? | 200/206 영상 바이너리 스트림; 삭제·권한·만료 검사 |

업로드 준비와 회차 행은 한 트랜잭션에서 생성한다. 영상 바이트는 `uploads.video_data`에 **한 번만** 저장하고 회차는 `upload_id`로 참조한다. `complete`는 실제 파일 검증 뒤 한 번만 분석을 접수한다. 파일 전송 전에 호출하면 409, 만료되면 410이다. GET video는 브라우저 재생을 위해 Range 요청·`Content-Range`를 지원해야 한다. 해당 스트리밍은 프레임워크 기본 동작이라고 가정하지 않고 구현·검증한다. DB의 큰 값을 처리할 때 영상 전체를 서버 메모리에 동시에 올리지 않는 방법을 검증해야 한다.

## 5. 분석 상태·리포트·STT 전사

`analysisId=rounds.id`는 재시도해도 유지하고 `jobId=analysis_jobs.id`는 attempt마다 새로 만든다. 상태는 QUEUED→EXTRACTING→ANALYZING→SCORING→DONE 또는 FAILED. DONE은 최종 리포트와 STT 저장이 모두 검증·커밋된 뒤에만 공개한다.

| 메서드·경로 | 요청 | 응답 |
| --- | --- | --- |
| GET `/projects/{projectId}/rounds` | — | 회차·상태·총점 목록 |
| GET `/projects/{projectId}/rounds/{roundNo}/status` | — | status,progress,stage,etaSec?,failure? |
| POST `/projects/{projectId}/rounds/{roundNo}/retry` | Idempotency-Key | 202 QUEUED |
| GET `/projects/{projectId}/rounds/{roundNo}/report` | — | Report |
| GET `/projects/{projectId}/rounds/{roundNo}/transcript` | — | `{utterances:[{seq,startSec,endSec,text}]}`; DONE 이후만 공개 |
| GET `/projects/{projectId}/compare` | from,to | 항목·총점 비교 |
| DELETE `/projects/{projectId}/rounds/{roundNo}` | — | 204 |
| GET `/schedule` | month? | 발표 일정 |

전사 API는 로그인한 소유자에게만 공개하며 페이지 단위가 필요해질 만큼 길어지는지 운영 검증한다. 각 발화의 시각은 영상 시작 0초 기준이고 `0 ≤ startSec < endSec ≤ durationSec`다. 전사 전문은 `stt_utterances` 행을 `seq` 순으로 조립한다. 분석 실패나 재시도 중의 전사는 공개하지 않는다. 화면에서 전사를 쓰지 않기로 결정하면 공개 GET은 제거할 수 있지만 DB 저장은 유지한다.

Report: `{analysisId,projectId,roundNo,status:DONE,totalScore,scores:[{rubricItemId,itemKey,score,weight,evidence[]}],versions:{model,rubric},segments[],timeline,coaching:{strengths[],improvements[],actions[]},targetMinutes,timeCheck,contentCheck:null,expectedQuestions[],quality,limitations[]}`. `quality`는 NORMAL/DEGRADED. 항목별 근거는 관찰 신호와 실제 영상 시간 구간을 가리킨다. 점수 없는 실패 결과를 리포트로 반환하지 않는다. 목표 시간이 0이면 시간 차이는 null이다. 비교는 동일 루브릭·모델 버전의 DONE 회차만 같은 기준으로 해석한다.

## 6. api와 analysis-api 내부 계약

`POST /analysis/jobs`는 `{jobId,analysisId,attempt,modelVersion,rubricVersion,targetMinutes?}`를 전송한다. `videoKey`, `materialKeys`, `projectTopic`, 정책 가중치는 전송하지 않는다. analysis-api는 서비스 인증으로 `GET /internal/analysis-jobs/{jobId}/video`를 호출해 DB 영상을 스트리밍으로 읽고, `POST /internal/analysis-jobs/{jobId}/utterances`로 발화별 전사·시각을 저장한다. 완료·실패는 `POST /internal/analysis-jobs/{jobId}/events`로 보고한다. 콜백 유실 시 `GET /analysis/jobs/{jobId}`로 복구하고 삭제 시 `POST /analysis/jobs/{jobId}/cancel`을 호출한다.

같은 eventId·이전 attempt·삭제된 회차의 늦은 결과는 중복 저장하거나 재공개하지 않는다. 결과의 버전, 항목 집합, 점수·근거·시간 범위를 검증한 뒤 DONE을 공개한다. 전체 작업 자동 재시도는 일시 장애에 1회, 동시 배치 분석은 최대 3개다.

## 7. 질의응답

기존 v3.4의 QA 세션 기능을 유지한다. 분석 완료 회차를 기준으로 `GET /projects/{projectId}/qa/eligibility`, `POST /projects/{projectId}/qa/sessions`, `GET /qa/sessions/{sessionId}`, `POST /qa/sessions/{sessionId}/ticket`, `POST /qa/sessions/{sessionId}/more`, `POST /qa/sessions/{sessionId}/end`, `GET /qa/sessions/{sessionId}/questions/{questionId}/evidence`, `GET /qa/sessions/{sessionId}/report`, `GET /projects/{projectId}/qa/sessions`, `DELETE /qa/sessions/{sessionId}`를 제공한다. 브라우저 WebSocket은 `/api/v1/qa/sessions/{sessionId}/stream?ticket=...`으로 FastAPI가 중계한다.

질문 수는 추가·꼬리 질문을 포함해 최대 10개이며, 프로젝트당 진행 중 세션은 하나다. QA 답변 전사는 `qa_answers.transcript`에 저장한다. 이 값은 발표 영상의 `stt_utterances`와 다른 데이터다. 카메라 전송 방식·QA 녹화 보관은 아직 확정되지 않았다. 질문 근거는 명시적 조회에서만 반환한다.

## 8. 관리자·운영

| 메서드·경로 | 기능 |
| --- | --- |
| GET `/admin/dashboard` | 이용 현황 |
| GET `/admin/analyses` | 실패·진행 작업 조회 |
| GET `/admin/rubric` | 활성 단일 루브릭과 항목 조회 |
| PUT `/admin/rubric` | 새 단일 루브릭 버전 생성; 기존 버전 불변 |
| GET `/admin/users` | 사용자 조회 |
| PATCH `/admin/users/{userId}` | 상태 변경 |
| GET `/healthz`, GET `/readyz` | 생존·의존성 상태 확인; `/api/v1` 밖 |

관리자는 원본 영상이나 STT 전문을 기본 조회 응답으로 받지 않는다. 삭제 예약 시 사용자 접근을 즉시 막고 DB 영상 바이트·전사·리포트의 물리 삭제 및 백업 보존 정책을 별도로 적용한다.

## 9. 구현 전 확정·검증 항목

- 항목별 채점 계산식·임계값·결손 처리·반올림과 루브릭 버전의 배포 방식.
- 500 MiB 영상의 FastAPI 수신, PostgreSQL bytea 쓰기·읽기, Range 재생, 메모리·디스크·트랜잭션·백업 비용. 기존 60분 한도는 30분으로 변경.
- 영상·전사 보존 기간과 사용자 삭제 시 실제 삭제·백업 정리 기한.
- STT 전사 품질 하한과 YOLO 모델 조합의 실제 출력 지표.
- QA 영상 저장 범위, QA 점수 체계, 최종 LLM JSON 필드와 리포트의 정확한 호환.
