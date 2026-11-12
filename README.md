# ProPitch 팀 개발 시작점

이 브랜치는 6명이 같은 계약에서 개발을 시작하기 위한 공용 코드다. 백엔드는 Python 3.11·FastAPI·PostgreSQL, 프론트는 Vue 3·TypeScript·Vite를 사용한다.

## 먼저 읽기

1. [공통 AI 작업 지침](AGENTS.md)과 [팀 개발 규칙](backend/TEAM_RULES.md)
2. [담당 폴더와 리뷰어](backend/docs/OWNERSHIP.md)
3. [사용자 API v3.5](backend/docs/specs/user-api-v3.5.md), [AI 내부 API v1.4](backend/docs/specs/analysis-api-v1.4.md), [ERD v10](backend/docs/specs/erd-v10.dbml)
4. [계약 적용 기준](backend/docs/SPEC_ALIGNMENT.md)과 [미확정 결정](backend/docs/CONTRACT_DECISIONS.md)

## 실행

- [백엔드 설치·실행·검사](backend/README.md)
- [프론트 설치·실행·빌드](frontend/README.md)
- [브랜치·PR 협업 절차](CONTRIBUTING.md)

`backend/api`는 사용자 API, `backend/analysis`는 AI 서비스, `backend/contracts`는 공통 자료 형식의 시작점이다. `frontend`는 화면 코드다. 담당 폴더 안의 파일 구성은 각 담당자가 정한다.

현재 운영 API와 AI API는 `/healthz` 중심 골격이다. 업로드·작업 관리·실제 분석·결과 화면은 담당자가 구현해야 한다. `backend/contracts/examples`의 JSON은 형식 확인용이며 실행되는 가짜 분석기는 포함하지 않았다.

이번 브랜치에는 로컬 영상·외부 데이터셋·실험 결과를 넣지 않았다. 필요한 실험 자료는 출처와 사용 조건을 확인한 뒤 별도 작업에서 공유한다.
