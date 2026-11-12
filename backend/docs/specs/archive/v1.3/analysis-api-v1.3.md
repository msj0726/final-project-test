# ProPitch AI 내부 API 명세 v1.3

상태: 검토안 · 기준일: 2026-11-09 · 대응 ERD: v9 · 사용자 API: v3.5

## 1. 분석 범위

발표 영상의 음성과 프레임을 전처리하고 STT·음향 분석과 YOLO 계열 모델 조합의 자세·제스처·얼굴 관찰 결과를 같은 영상 시작 시각(0초)으로 정렬한다. 단일 루브릭의 **확정된 규칙·계산식**이 항목별 점수와 총점을 산출한다. LLM은 확정된 점수의 근거 설명, 코칭, STT 전사에 기반한 예상 질문을 생성하며 숫자 점수를 바꾸지 않는다. 발표 내용의 주제 적합성·논리성·PDF 대조는 채점하지 않는다. `contentCheck`는 항상 null이다.

원본 발표 영상 바이트는 PostgreSQL `uploads.video_data`, STT 전문은 `stt_utterances.text`의 순서 있는 발화 행, 발화 시각은 `start_sec/end_sec`에 저장한다. `job_id`로 재시도별 전사 결과를 구분한다. STT 전사를 LLM에 제공할 때는 예상 질문 생성용 데이터이며 실행 지시로 취급하지 않는다. 프레임·음향 중간 산출물은 DB 영구 저장 대상이 아니다.

## 2. 서비스 경계와 작업 흐름

`api`가 영상·상태·STT 저장의 DB 소유자다. `analysis-api`는 직접 DB를 수정하지 않고 서비스 인증된 내부 API를 사용한다.

1. `api`는 사용자 직접 업로드를 완료·검증하고 회차와 작업을 기록한다.
2. `api → analysis-api`: `POST /analysis/jobs`로 jobId, roundId, attempt, modelVersion, rubricVersion을 접수한다.
3. `analysis-api → api`: `GET /internal/analysis-jobs/{jobId}/video`의 응답 스트림으로 영상 바이트를 읽는다. 접근은 현재 job·회차 상태·서비스 자격 증명을 검사한다.
4. 전처리 뒤 AUDIO(STT·음향)와 VIDEO(자세·제스처·얼굴)를 병렬 실행한다. STT 결과는 발화 단위로 `POST /internal/analysis-jobs/{jobId}/utterances`에 전달해 저장한다.
5. ALIGN → RUBRIC → LLM FEEDBACK을 실행한다. 결과는 최종 JSON으로 저장하고 콜백한다. `api`가 검증·커밋한 뒤 DONE을 공개한다.

내부 영상 GET은 브라우저에 공개하지 않는다. 전송 중 메모리에 영상 전체를 적재하지 않도록 스트리밍하며, 처리 완료 후 임시 파일을 정리한다. 500 MiB DB 읽기·쓰기와 백업·복구 비용은 실제로 측정해야 한다.

## 3. 작업 접수와 조회

### POST /analysis/jobs

요청: `jobId(UUID), analysisId(=roundId UUID), attempt(1 이상 정수), modelVersion, rubricVersion, targetMinutes?`. `videoKey`, `materialKeys`, `projectTopic`과 다중 기준 가중치는 받지 않는다. 영상은 roundId와 연결된 DB 저장본으로 조회한다. 루브릭 버전은 작업 접수 시 고정한다. 분석 서비스가 그 버전의 항목·가중치·채점 규칙을 얻는 내부 계약은 구현 전에 확정한다.

성공: `202 {"jobId":"<UUID>","status":"QUEUED","attempt":1}`. 같은 jobId와 같은 본문은 같은 결과, 다른 본문은 `409 JOB_ID_CONFLICT`. 없는 영상·회차 또는 일치하지 않는 버전은 작업 접수 거부. 실제 미디어 검증 실패는 FAILED로 보고한다.

### GET /analysis/jobs/{jobId}

`200 {jobId,analysisId,attempt,status,stage,progress,failure?,result?}`. `result`는 DONE에서만 `{reportKey}`다. 알 수 없는 jobId는 404. `api`는 콜백 유실 복구 시 현재 attempt인지 확인한다.

### POST /analysis/jobs/{jobId}/cancel

`202`는 취소 요청 수락이다. 동일 요청은 멱등 처리하고, 늦은 완료 콜백은 공개하지 않는다. 내부 CANCELLED는 사용자 공개 상태에 추가하지 않는다.

## 4. api가 제공하는 내부 데이터 API

### GET /internal/analysis-jobs/{jobId}/video

서비스 인증 필수. 현재 jobId·roundId·삭제 표식을 확인한 뒤 영상 바이트를 스트리밍한다. `Content-Type`은 검증된 업로드 형식, `Content-Length`는 실제 바이트 길이다. 접근 불가·삭제는 404, 아직 업로드 미완료는 409. 원본 영상은 로그·오류 상세에 포함하지 않는다.

### POST /internal/analysis-jobs/{jobId}/utterances

요청: `{attempt, utterances:[{seq,startSec,endSec,text}]}`. 영상 시작 0초 기준이고 `0 ≤ startSec < endSec ≤ durationSec`, `seq`는 1부터 연속 증가한다. 동일 jobId·seq·동일 내용 재전송은 성공, 다른 내용은 409. 전사 행을 해당 작업에 원자적으로 교체/확정하는 시점은 STT 단계 완료 전이며, RUNNING 중에는 사용자 API에 공개하지 않는다. 응답 204. 삭제됐거나 오래된 작업의 전사 결과는 저장하지 않는다. 전사 전문은 로그·콜백에 넣지 않는다.

### POST /internal/analysis-jobs/{jobId}/events

요청: `{eventId,analysisId,attempt,status,stage,progress,occurredAt,result?,failure?}`. DONE의 `result`는 `{reportKey}`, FAILED의 `failure`는 `{code,retryable}`. eventId 중복·오래된 attempt·삭제된 회차 이벤트는 무해하게 무시한다. 결과 점수·항목 집합·근거 시간·버전·STT 저장 완료 여부를 검증하고 DB에 커밋한 뒤 204를 반환한다. 재현 가능한 결과 오류는 422, 일시 장애는 5xx로 응답한다. analysis-api는 같은 eventId로 재전송한다.

## 5. 단계와 내부 산출물

| stage | 공개 status | 산출물·조건 |
| --- | --- | --- |
| QUEUED | QUEUED | 대기열 등록 |
| PREPROCESS | EXTRACTING | 영상 검증·오디오 추출·프레임 샘플링·시각 기준 |
| AUDIO / VIDEO | ANALYZING | STT 발화·음향 창 / YOLO 모델 조합의 관찰 창. 병렬 가능 |
| ALIGN | ANALYZING | 공통 시각의 음성·영상 특징 결합 |
| RUBRIC | SCORING | 단일 루브릭의 항목 점수·관찰 근거·총점 확정 |
| FEEDBACK | SCORING | LLM 코칭·예상 질문. 숫자 점수 변경 금지 |
| DONE / FAILED | DONE / FAILED | 저장·검증 완료 / 실패 코드 |

STT 내부 출력은 `utterances[{seq,startSec,endSec,text}]`, 음향 출력은 발화 속도·휴지·음량·높낮이 등의 시간 창이다. 영상 출력은 자세·제스처·얼굴 가시성·방향 등의 시간 창이다. YOLO 모델별 실제 측정 가능 항목을 확정하고, 지원하지 않는 지표는 계약에서 제거한다. 관찰 불가는 null과 사유로 표현하며 0점으로 대체하지 않는다. 얼굴 관찰로 감정·성격·자신감을 직접 측정했다고 주장하지 않는다.

## 6. 채점·LLM 결과 계약

RUBRIC은 `scores[{rubricItemId,score(0..100),evidence[]}]`를 만들고 항목 가중 평균을 마지막에 반올림해 `totalScore`를 만든다. 계산식, 관찰 신호, 임계값, 결손 처리, 반올림은 **아직 미확정**이며 불변 버전으로 정의해야 한다. 필수 신호를 확보하지 못하면 FAILED다.

LLM 입력은 확정 점수·관찰 근거·시각·한계와 예상 질문용 전사다. 출력은 `coaching{strengths[],improvements[],actions[]}`, `segments[]`, `expectedQuestions[]`다. 점수 변경, 없는 시각·신호를 인용한 문장은 거부한다. LLM만 실패하면 승인된 규칙형 문장으로 대체하고 `quality=DEGRADED`, `limitations`에 `FEEDBACK_FALLBACK`을 넣는다.

DONE 결과의 저장 매핑: `reports.total_score/timeline/coaching/expected_questions/quality/limitations`, `report_scores.score/evidence`, `report_segments`, `stt_utterances`다. `reports.content_check=null`. 결과 JSON의 필수 필드·배열 원소 구조는 사용자 API 응답과 최종 검증해야 한다. 같은 회차의 공개 리포트는 최대 하나다.

## 7. 실패·보안·미확정 사항

입력·정책 오류는 자동 재시도하지 않는다. 일시적 STT·모델·DB 장애는 `api`가 전체 작업 자동 재시도를 최대 1회 지시한다. 새 attempt는 새 jobId이며 재시도 시 기존 전사 행은 별도 job에 남아 공개되지 않는다. 사용자 수동 재시도는 자동 1회 한도와 별도로 검토한다. 동시 배치 분석은 최대 3개, 초과는 QUEUED다.

영상·음성·STT 전문·QA 답변을 애플리케이션 로그나 콜백에 기록하지 않는다. 사용자 또는 회차 삭제 시 DB 영상·전사·리포트의 실제 삭제 절차와 보존 기간을 정해야 한다. 영상 바이트를 PostgreSQL에 두므로 500 MiB·30분 파일에 대한 요청 제한, 스트리밍, 트랜잭션 지속 시간, 저장 용량, 백업·복구 시간을 운영 검증한다.

**확정 필요:** 항목별 채점 계산식·가중치, 루브릭 규칙의 내부 전달 방식, YOLO 조합의 실제 출력, STT 품질 하한, 전사·영상 보존 기간, DB 대용량 영상의 성능. 점수 품질은 별도 사람 평가 데이터로 검증한다.
