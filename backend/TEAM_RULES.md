# ProPitch 6인 공통 개발 규칙

> 최신 범위 변경: 사용자 이미지의 영상 업로드·발화/시선/자세/내용/구조 분석·타임스탬프 근거·종합 평가·우선 개선 지침을 MVP1 목표로 적용한다. 내용·구조 평가는 계약 변경이 필요한 추가 목표다. [담당 경계와 최신 기준](docs/OWNERSHIP.md)을 우선 확인한다.

작업 전 [AGENTS.md](AGENTS.md), [현재 명세](docs/SPEC_ALIGNMENT.md), [담당 영역](docs/OWNERSHIP.md)을 읽는다. 현재 기준은 사용자 API v3.5 / AI 내부 v1.4 / ERD v10다. MVP1은 11월 12일 분석 연동이며 PDF·QA는 후속이다.

## 작업과 리뷰

- 작업 이슈에 목적·담당/리뷰어·수정 파일·입출력·완료 조건을 적는다. 한 PR은 한 동작/계약 변경으로 제한하고 불필요한 전체 리팩터링을 섞지 않는다.
- main 직접 push 대신 브랜치/PR을 사용한다. 예: feat/stt-contract, fix/event-replay. 이 에이전트의 브랜치는 codex/를 사용한다.
- 작성자가 코드·권한·실패 경로·검증 결과를 설명할 책임을 진다. AI의 완료 주장만으로 병합하지 않는다. 다른 팀원의 리뷰와 CI 통과가 필요하다.
- 공통 계약은 소비 팀, migration/환경은 관련 BE·인프라 담당 리뷰를 받는다. 동시에 공용 파일을 수정하기 전 범위를 공유한다.
- 각자 로컬에서 개발하고 공유 서버 파일을 직접 덮어쓰지 않는다. AI 코딩 도구가 다른 경우에도 같은 AGENTS.md를 읽게 한다.

## 코드와 계약

- Python 3.11 + uv.lock, Ruff 포맷/검사. API ID는 UUID 문자열이다.
- routers는 HTTP/권한 경계, services는 업무 규칙, clients는 외부 호출. analysis가 DB를 직접 수정하거나 사용자 API가 모델 실행을 직접 import하지 않는다.
- API 계약 변경은 모델·생성 Schema·샘플·테스트·문서를 함께 수정한다. 미래 API 계획 목록을 구현된 OpenAPI처럼 안내하지 않는다.
- 미정의 요청 필드 거부. PATCH는 생략 유지, 최소 한 필드, finalDate만 null 해제. 점수는 정수 0~100.
- 단건 data, 페이지 data+page, 204 무본문. 사용자 검증 오류는 400 공통 error, 내부 결과 검증은 422. requestId는 X-Request-Id와 같다.
- 실제 영상은 API 직접 업로드→DB bytea. 영상에 S3/videoKey/서명 URL을 부활시키지 않는다. 500 MiB·30분의 실제 제한/검증은 서버 책임이다.
- 단일 루브릭의 규칙+지정된 휴리스틱 LLM 평가, FEEDBACK의 확정 점수 변경 금지, contentCheck=null. 관찰불가=null+사유. 계약 예시의 점수·신호를 실제 모델 출력처럼 표시하지 않는다.

### 이름 규칙

- 기존 API·DB 필드명은 현행 명세를 따른다. 작명 통일만을 위한 변경은 하지 않는다.
- 새 이름은 같은 개념에 같은 용어를 쓴다. Python 파일·변수·함수와 DB 테이블·컬럼은 `snake_case`, API JSON 필드와 TypeScript 변수·함수는 `camelCase`, Python 클래스와 Vue 컴포넌트·TypeScript 타입은 `PascalCase`를 따른다. 예: Python·DB의 `analysis_id`와 API JSON의 `analysisId`.
- 새 Boolean은 참일 때의 뜻이 분명하게 짓고 `is`·`has`·`can`·`should` 접두어를 권장한다. 기존 계약의 `done`·`retryable`처럼 뜻이 명확한 이름은 허용한다.
- 새 API 필드·경로 또는 DB 컬럼·테이블은 담당자 간 검토 후 명세·계약 모델·예시·테스트를 함께 갱신하고, DB 변경에는 migration을 포함한다.

## 상태와 데이터 보호

- analysisId는 회차 UUID로 유지, jobId는 attempt마다 새 UUID. 상태 QUEUED→EXTRACTING→ANALYZING→SCORING→DONE/FAILED.
- DONE 공개 전 버전·항목 집합·점수/근거 시간·STT 저장을 검증한다. 삭제·과거 attempt·중복/역순 이벤트는 공개 결과를 덮어쓰지 않는다.
- 전체 분석 자동 재시도는 api만 지시하며 일시 장애 1회. 콜백 재전송은 같은 eventId로 한다. 동시 배치 3개, 운영 큐는 영속성을 갖춰야 한다.
- 사용자별 소유권과 역할을 각각 검증한다. 타인 리소스404, 역할403, 일반 가입USER만 허용. 내부 API는 별도 서비스 인증과 TLS가 필요하다.
- 비밀값은 .env/secret 관리. 영상·전사·QA 답변·비밀번호·토큰은 Git/프롬프트/로그에 넣지 않는다. 합성 fixture를 사용한다.
- DB 변경은 Alembic migration, 고유 제약/트랜잭션으로 중복을 막는다. 공유 데이터 삭제·파괴적 변경은 복구 방안과 사용자 권한을 확인한다.

## 완료 조건

Ruff·pytest 통과, 필요한 통합·실패 테스트, 문서 갱신, 리뷰어 검토. 실험/테스트의 한계와 실행하지 못한 검증을 적는다. 실제 모델은 탐색 데이터 재사용과 독립 평가를 구분해 보고한다. 작은 검증 상승이나 계약 예시 검증을 실제 품질 개선으로 주장하지 않는다.

GitHub 저장소 보호/권한·CODEOWNERS는 아직 설정하지 않았다. 로컬 문서와 CI 파일을 만든 것만으로 병합 규칙이 강제되는 것은 아니다.

## Vue 프론트 공통 기준

프론트는 `frontend/`의 Vue 3 + TypeScript 앱을 사용한다. 이지영은 앱 진입점·공통 API, 김승혜는 결과·전사·근거 화면을 맡는다. 담당 폴더 내부 구성은 각자가 정하되 컴포넌트 간 공개 props/emit, API 형식, 전역 스타일·의존성 변경은 함께 검토한다. 프론트에서 DB·Redis·analysis 내부 API를 직접 호출하지 않는다. 실제 사용자 API를 연결할 때 `contracts/`의 camelCase 계약과 인증·오류 규칙을 사용한다.
