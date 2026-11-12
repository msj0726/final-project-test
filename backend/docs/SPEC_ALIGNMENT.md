# 최신 명세 적용 기준

> 최신 범위 변경: 사용자 이미지의 영상 업로드·발화/시선/자세/내용/구조 분석·타임스탬프 근거·종합 평가·우선 개선 지침을 MVP1 목표로 적용한다. 내용·구조 평가는 계약 변경이 필요한 추가 목표다. [담당 경계와 최신 기준](OWNERSHIP.md)을 우선 확인한다.

정본: [사용자 API v3.5](specs/user-api-v3.5.md), [AI 내부 API v1.4](specs/analysis-api-v1.4.md), [ERD v10](specs/erd-v10.dbml). 원본 해시는 specs/provenance.json에 있다. 이전 v7과 API 본문 v3.2는 specs/archive/v7에 보관하며 현재 구현 기준이 아니다.

사용자는 이번 범위를 **분석 연동부터 구축, PDF·QA 후속**으로 확인했다. 새 API 문서에 유지된 PDF/QA 경로와 ERD 테이블은 제품 후속 범위다. 이를 이번 구현 완료 범위로 표시하지 않는다.

| 항목 | 현재 기준 |
|---|---|
| 영상 | FastAPI 직접 PUT, PostgreSQL uploads.video_data 한 번 저장, MP4/MOV 최대 500 MiB·30분 |
| 점수 | 단일 rubric_id, 네 항목의 규칙+지정된 휴리스틱 LLM 평가, 동일 가중 평균 총점. FEEDBACK은 점수 변경 금지 |
| 제거 | 영상 S3 URL/videoKey, 이중 기준 점수·정책 가중치·calibration |
| ID | UUID 문자열. analysisId=rounds.id 유지, jobId=analysis_jobs.id는 attempt마다 새 값 |
| STT | stt_utterances(job_id,seq,start_sec,end_sec,text), DONE 이전 비공개 |
| 재시도 | api가 일시 장애에 전체 자동 재시도 1회 지시. worker의 독립 전체 재시도 금지 |
| 공개 상태 | QUEUED/EXTRACTING/ANALYZING/SCORING/DONE/FAILED |
| 결과 | contentCheck=null, quality=NORMAL/DEGRADED, versions={model,rubric} |
| 오류 | 사용자 입력 400 공통 error, 내부 결과 검증 오류는 422 보존 |
| 작업 경계 | api가 DB 소유, analysis는 인증된 video/utterances/events 호출만 사용 |

## 적용된 코드

- 공통 모델·JSON Schema·샘플: 새 작업 접수, 이벤트, 발화, Report 전체 골격, 업로드 메타데이터.
- 내부 `/internal/` 검증의 422와 사용자 400을 분리했다. 실제 운영 내부 라우터는 아직 없다.
- 원본 표·본문을 반영한 endpoint-catalog는 계획 목록이다. 운영 api.main/analysis.api.main은 현재 health만 제공한다. 작업 접수·영상 전송·STT·결과 콜백은 담당자가 구현한다.

## 문서 간 세부 해석

- AI v1.4 흐름 설명에 roundId가 있지만 상세 POST 계약의 wire 필드는 analysisId다. 코드도 analysisId를 사용한다.
- 새 명세는 과거와 달리 실제 SHA-256과 UUID를 사용한다. durationSec/etag를 업로드 시작·완료 요청에 다시 넣지 않는다.
- 사용자 명세의 일반 400 규칙으로 내부 결과 오류 422를 덮어쓰지 않는다.
- 자료/QA는 문서에 있으나 사용자가 이번 범위에서 제외했다.
- 남은 운영 계약과 개발용 형식 초안은 [CONTRACT_DECISIONS.md](CONTRACT_DECISIONS.md)를 따른다. 계약 예시 검증은 실제 DB 스트리밍이나 채점 품질 검증을 대신하지 않는다.

## AI API v1.4 변경

평가 항목은 SPEECH_RATE·FLUENCY·GESTURE·GAZE 각 0~100 정수다. 세 제스처 감점 후보는 FACE_OCCLUSION·HAND_STILLNESS·UNRELATED_OBJECT_TOUCH로 한정한다. RUBRIC_RULE → RUBRIC_HEURISTIC → SCORE_AGGREGATE → FEEDBACK 순서이며 모두 공개 상태 SCORING이다. 규칙 점수는 LLM이 수정하지 못한다. 휴리스틱 판단은 명시된 기준만 수행하고 서버가 검증·합산한다. FEEDBACK 실패의 문장 대체와 필수 휴리스틱 실패는 다르게 처리한다.

ERD v10에는 score_source/breakdown/scoring_config가 추가됐지만, 사용자 API v3.5에는 규칙만 점수를 계산한다는 구문이 남아 있다. v1.4 원문이 요구한 DB 필드는 v10에 반영됐지만 실제 migration과 공개 Report의 scoreSource/breakdown 필드는 구현되지 않았다. 사용자 API v3.5와 상세 JSON 스키마를 함께 확정해야 한다. 목요일 시연의 내용·구조 평가는 현재 v1.4의 점수 네 항목에도 포함되지 않는 추가 목표다.

## ERD v10 반영

[ERD v10](specs/erd-v10.dbml)과 [설명 가이드](specs/erd-v10-guide.html)를 정본으로 보관했다. v9는 archive/v9로 이동했다. reports.total_score는 네 항목 확정 점수의 동일 가중 평균이며 반올림 방식은 활성 루브릭 설정에 고정한다. report_scores에는 score_source(RULE/LLM/HYBRID), breakdown(JSONB), evidence가 저장된다. rubrics.status는 DRAFT/ACTIVE이며 ACTIVE는 서비스당 하나다. rubric_items.scoring_config는 DRAFT에서 미정값을 허용하고 ACTIVE 전 필수 값을 검증한다. ACTIVE 네 항목의 weight는 각각 0.25이고 (rubric_id,item_key)는 유일하다. 필수 휴리스틱 UNDETERMINED는 FAILED, 선택 기준은 점수에서 제외하고 limitations에 남긴다.

DBML을 저장한 것은 migration을 실행했다는 뜻이 아니다. 사용자 API v3.5·AI API v1.4 원본은 받은 그대로 두었다. 두 문서의 기존 v9 참조나 공개 점수 설명은 후속 문서 개정이 필요하다.
