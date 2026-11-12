# 계약 결정과 남은 정책

## 이번 연결에서 확정한 부분

- POST /analysis/jobs는 jobId/analysisId/attempt/modelVersion/rubricVersion/targetMinutes만 받는다. ID는 UUID, attempt는 1 이상 정수다. targetMinutes 생략은 AI API v1.4 기준 0(목표 시간 없음)으로 처리한다. 사용자 API v3.5의 프로젝트 생성 기본값 30과 구분한다.
- utterances는 전체 STT 완료 스냅샷으로 한 번 전달한다. seq는 1부터 연속, 개별 startSec<endSec, 모든 endSec는 영상 길이 이내. 동일 스냅샷 재전송은 204, 다른 내용은 409. 빈 배열은 STT 완료 표시일 수 있지만 실제 필수 신호 실패 정책은 별도다.
- DONE은 result만, FAILED는 failure만 포함한다. DONE progress=100. occurredAt은 UTC. stage/status는 AI 명세 매핑과 일치한다.
- 같은 eventId·과거 attempt·삭제 대상의 콜백은 저장/재공개하지 않는다. 실제 결과 오류는 422이며 수정 없는 무한 재전송을 하지 않는다.
- api만 전체 작업 재시도를 지시한다. 콜백 전달 재시도는 같은 eventId를 유지하며 전체 분석을 다시 돌리지 않는다.
- 최종 Report는 v3.5의 필드 집합, contentCheck=null, quality 문자열, model/rubric 버전, 정수 점수를 따른다.

## 계약 형식 초안

아래 JSON 형식은 소비 팀이 입출력을 맞추기 위한 초안이다. 실제 신호·점수·저장 정책은 아직 확정되지 않았다.

| 항목 | 현재 형식 | 실제 구현 전 확인 |
|---|---|---|
| evidence 원소 | fromSec,toSec,signal,value,reason; 관찰불가 value=null+reason | STT/Vision 신호·단위 확정 |
| timeline | signal명 → Evidence 배열 | 시간 창 형식·크기·샘플링 합의 |
| segments/questions | fromSec,toSec,kind,feedback / kind,text | LLM 스키마와 enum 조정 |
| timeCheck | actualMinutes,deltaMinutes; 목표 0이면 delta=null | 허용 범위와 판정 방식 합의 |

계약 JSON 예시의 점수와 신호는 실제 분석 결과가 아니며 런타임 응답으로 사용하지 않는다.

## 실제 분석 도입 전에 필요한 결정

- 강유성 + 장민서/이지수: 루브릭 항목·관찰 신호·단위·가중치·정규화·반올림·결손 처리, STT 품질 하한. 승인 전 실제 점수를 제공하지 않는다.
- 박재흥 + 장민서: reportKey 조회/삭제, 루브릭 전달, bytea 부분 읽기/쓰기·Range, 업로드 준비 시 duration_sec not-null 처리, 대기 작업 started_at not-null 의미.
- 박재흥 + 팀: 영상/STT 보관·실삭제·백업 정리 기간, 활성 루브릭 하나를 DB에서 보장하는 인덱스·전이 방식, 업로드 만료 시간.
- 이지영 + 김승혜 + 장민서: Report 중첩 배열의 개발용 형식과 화면 매핑 확인.
- QA 카메라/녹화/PDF/RAG는 MVP1 이후 결정한다.

실제 개인정보·영상 저장이나 점수 산출을 시작하기 전 팀이 미정 정책을 합의하고 이 문서와 정본을 갱신해야 한다.

## v1.4에서 아직 결정되지 않은 채점값

발화속도 단위·시간 분모·적정 구간, 유창성의 규칙/LLM 세부 기준과 비율, 세 제스처 행동의 감점·지속시간·중복 상한, 정면 판정과 비율 환산·최소 유효 시간, 총점 .5 반올림, 루브릭 전달 방식은 미정이다. 계산 설정 없이 계약 예시의 점수를 실제 점수로 쓰지 않는다. score_source/breakdown/scoring_config는 ERD v10와 사용자 API v3.5 변경 후 추가한다.

계약 결과 샘플은 네 항목의 필드 형식만 보여준다. 실제 계산식·휴리스틱 판단을 실행한 결과가 아니다. .5 반올림은 아직 정하지 않았으므로 총점 일치 정책은 팀 합의 후 구현한다.

## ERD v10이 확정한 저장 구조

score_source, breakdown, scoring_config와 rubrics.status가 DBML에 추가됐다. ACTIVE 루브릭은 네 항목 각 weight=0.25, 서비스당 하나다. DRAFT는 미정 계산값 허용, ACTIVE는 필수 설정 검증이 선행된다. breakdown/scoring_config 내부 JSON 필드·반올림 방식·공개 Report의 표현은 여전히 상세 합의가 필요하다. 사용자가 제공한 v3.5 원본을 임의 수정하지 않고 계약 차이를 SPEC_ALIGNMENT.md에 기록했다.
