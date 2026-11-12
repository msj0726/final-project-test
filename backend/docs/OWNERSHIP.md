# 담당 폴더와 MVP1 기준

**담당 폴더는 고정하고 내부 구성은 담당자가 결정한다.** 파일 이름·하위 폴더·알고리즘은 자유롭게 선택하되 외부 계약, 보안, 테스트, 공통 도구 규칙은 지킨다. 다른 담당 폴더 수정은 해당 담당자와 먼저 공유한다. 담당은 독점 수정 권한이 아니라 최종 책임을 뜻한다.

경로는 저장소 루트 기준이다. 실제 폴더와 OWNERSHIP.md를 생성했다. 구현 파일·빈 함수는 미리 강제하지 않았다. frontend는 Vue 앱 경계로 사용한다. 실제 실행 상태는 frontend/README.md를 확인한다.

| 담당 | 주 담당 경로 |
|---|---|
| 장민서 | `backend/analysis/modules/vision`<br>`backend/api/services/results`<br>`backend/api/routers/results` |
| 이지수 | `backend/analysis/modules/stt`<br>`backend/analysis/modules/audio`<br>`backend/analysis/modules/content` |
| 박재흥 | `backend/api/services/uploads`<br>`backend/api/services/jobs`<br>`backend/api/routers/uploads`<br>`backend/api/routers/jobs`<br>`backend/api/clients`<br>`backend/api/models`<br>`backend/api/migrations`<br>`backend/infra/runtime` |
| 강유성 | `backend/analysis/modules/scoring`<br>`backend/analysis/modules/coaching`<br>`backend/analysis/worker`<br>`backend/infra/analysis` |
| 이지영 | `frontend/src/features/upload`<br>`frontend/src/features/analysis-status`<br>`frontend/src/shared/api`<br>`frontend/infra` |
| 김승혜 | `frontend/src/features/report`<br>`frontend/src/features/transcript`<br>`frontend/src/features/video-player` |

## 역할과 연결

- 장민서: 시선·자세 관찰, 결과·이벤트·STT 수신 검증.
- 이지수: STT, 발화 속도·침묵·반복 표현, 전사 기반 내용·구조 평가 입력/출력. 내용 분석 구현은 추가 범위이며 강유성과 평가 기준을 먼저 맞춘다.  실시간 QA는 후속.
- 박재흥: 업로드·작업 등록·영상 접근·DB·서비스 실행.
- 강유성: 루브릭·채점·종합 코칭·우선 개선 지침, 워커/분석 실행 환경.
- 이지영: 업로드·진행/오류 화면, 공통 API 호출, FE 환경.
- 김승혜: 종합 리포트·전사·근거 시각 영상 이동·우선 개선 지침 화면.

내용 분석/코칭은 이미지의 미배정 기능을 기존 역할에 연결한 분담안이다. 팀이 조정하면 이 문서와 폴더의 담당 표시를 함께 갱신한다.

## 공용 파일의 최종 정리 담당

| 공용 영역 | 정리 담당 | 변경 시 검토 |
|---|---|---|
| backend/contracts 및 생성 Schema·샘플 | 장민서 | 실제 소비 담당자, 점수는 강유성 |
| backend/api/core, api/main.py | 장민서 | 박재흥·이지영 |
| backend/analysis/api, pipeline | 강유성 | 장민서·이지수·박재흥 |
| backend/compose.yaml, pyproject.toml, uv.lock, .github/workflows | 박재흥 | 강유성·이지영 |
| frontend의 앱 진입점·라우터·패키지·공통 스타일 | 이지영 | 김승혜 |
| docs·AGENTS·TEAM_RULES | 장민서 | 영향받는 담당자 |
| backend/tests | 변경 작성자 | 해당 기능 리뷰어 |

프론트는 Vue 3 + TypeScript를 사용한다. FE 공통 파일은 이지영이 구성하고 김승혜가 소비 형태를 검토한다. frontend/infra는 FE 빌드·배포 설정, backend/infra/runtime은 서비스·DB 환경, backend/infra/analysis는 모델·워커 실행 환경이다. 루트 Compose/CI를 세 사람이 각각 수정하지 않는다. GitHub ID가 없어 CODEOWNERS 강제 설정은 하지 않았다.

## MVP1 목표 — 사용자 이미지 기준

이미지 제목은 ‘MVP 1·2 중간발표 목표’다. 사용자 요청에 따라 아래 내용을 이번 MVP1 목표로 적용한다. 목표일은 기존 지시인 **2026-11-12 목요일**이다. 달성을 보장하는 일정은 아니다.

1. 영상 업로드 후 비동기 분석이 실행되고 진행·실패를 화면에서 확인한다.
2. 발화 속도·침묵·반복 표현·시선·자세·내용·구조를 분석한다. 실제 측정 불가 항목은 한계와 이유를 표시한다.
3. 평가 보고서에서 타임스탬프 근거, 종합 평가, 우선 개선 지침을 제공한다. 근거를 선택하면 해당 영상 구간을 확인할 수 있어야 한다.

목표와 현재 상태를 구분한다. 현재 운영 앱은 health 중심 골격이며 실제 업로드·모델·FE 연결은 미완성이다. 완료 판정은 각 항목의 실제 입력부터 화면까지 연결된 검증으로 한다. 계약 예시는 실제 MVP 기능 완료로 계산하지 않는다.

## 최신 명세와 추가 목표의 차이

이미지의 내용·구조 평가는 v3.5/v1.4의 ‘내용 의미 평가 제외’와 다르다. 최신 사용자 요청을 제품 목표로 우선하되 실행 계약은 합의 없이 변경하지 않는다. 이지수·강유성·장민서가 전사 기반 정성 평가인지, 숫자 점수 포함인지, 근거·출력 필드를 정한 후 contracts와 명세를 함께 갱신한다. 그 전에는 contentCheck=null과 FEEDBACK LLM의 확정 점수 변경 금지를 유지한다. PDF 대조·실시간 QA까지 추가된 것으로 해석하지 않는다.

## 목요일 전 작업 순서

11/10: 담당 경계·내용/구조 계약·각 기능 완료 기준 확인. 11/11: 실제 모듈과 BE/FE 연결 및 실패 검증. 11/12: 업로드→분석→근거 리포트 통합 시연과 실제 완료/미완료 항목 구분. 부족한 기능을 계약 예시로 감춰 완료 처리하지 않는다.

## v1.4 계약 작업 배분

이지수: 발화속도 단위·시간 분모, 휴지/필러/반복 측정의 근거와 품질 하한. 장민서: GAZE 관찰 가능 시간/정면 기준, GESTURE의 세 행동 근거와 검출 한계. 강유성: 네 항목 루브릭 설정, RULE/LLM 담당 기준, 동일 가중 합산·반올림·실패 정책. 박재흥: score_source·breakdown·scoring_config의 ERD/API 저장 경계. 이지영·김승혜: 네 항목·근거·DEGRADED를 화면에서 구분. 세부 수치가 정해지기 전 실제 점수를 완료로 표시하지 않는다.
