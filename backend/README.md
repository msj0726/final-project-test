# ProPitch 백엔드 개발 시작 가이드

이 가이드는 팀원이 저장소를 받은 뒤 로컬에서 공용 코드를 실행하고, 자신의 담당 영역에서 개발을 시작하기 위한 문서다. **현재 기술 스택은 Python 3.11·FastAPI·PostgreSQL**이다. Java·Spring Boot·MySQL 설정을 그대로 적용하면 이 저장소의 코드·ERD와 맞지 않는다. 사용자 API v3.5, AI 내부 API v1.4, ERD v10을 기준으로 한다.

**MVP1 목표(2026-11-12 목요일):** 영상 업로드 → 비동기 분석(발화 속도·침묵·반복 표현·시선·자세·내용·구조) → 타임스탬프 근거와 종합 평가·우선 개선 지침. 현재 운영 API는 health 중심 골격이며 실제 영상 업로드·DB 저장·모델·프론트 연결은 담당자가 구현한다. 내용·구조 평가는 현재 명세의 네 점수 항목 밖에 있어 [계약 결정](docs/CONTRACT_DECISIONS.md)이 더 필요하다.

## 팀원에게 전달할 개발 시작점

- **공용 토대:** `api.main:app`과 `analysis.api.main:app`이 운영 코드의 진입점이다. 현재 두 앱은 health 중심 골격이므로 업로드·작업·분석·결과 API를 담당자가 구현해야 한다. `contracts/`는 팀 간 자료 형식의 시작점이며, 계획된 경로를 이미 구현된 API로 보지 않는다.
- **계약과 담당:** [사용자 API v3.5](docs/specs/user-api-v3.5.md)·[AI 내부 API v1.4](docs/specs/analysis-api-v1.4.md)·[ERD v10](docs/specs/erd-v10.dbml)을 읽고 [담당 폴더](docs/OWNERSHIP.md) 안에서 구현한다. 공용 입출력·DB 변경은 소비 담당자와 함께 검토한다. 내용·구조 평가처럼 [미확정 계약](docs/CONTRACT_DECISIONS.md)은 합의 후 반영한다.

팀원은 먼저 [공통 AI 지침](AGENTS.md)과 [팀 규칙](TEAM_RULES.md)을 확인한 뒤 자신의 담당 코드를 붙인다. 프론트는 [Vue 3 + TypeScript 안내](../frontend/README.md)를 따른다.

## 1. 준비할 도구

| 도구 | 필요한 이유 | 사용 시점 |
|---|---|---|
| Python 3.11 | `pyproject.toml`이 허용하는 Python 버전 | 필수 |
| [uv](https://docs.astral.sh/uv/) | `uv.lock` 기준 패키지 설치·실행 | 필수 |
| VS Code + Python/Debugpy 확장 | 코드 작성·디버깅. 다른 IDE도 가능 | 권장 |
| Git | 브랜치·PR로 코드 공유 | 팀 협업 |
| Docker Desktop 또는 Docker Engine + Compose | 로컬 PostgreSQL·Redis 실행 | DB/큐 작업 시 |
| Postman, curl 또는 VS Code REST Client | 개발 중 HTTP 호출 | 선택 |

PostgreSQL을 직접 설치할 필요는 없다. Docker Compose를 사용할 경우 PostgreSQL과 Redis가 로컬에서 실행된다. 현재 health 골격 실행에는 DB·Redis가 필요하지 않다. Java JDK·IntelliJ·Spring Initializr·Lombok·JPA도 현재 백엔드를 실행하는 데 필요하지 않다.

버전 확인:

```sh
python3.11 --version
uv --version
git --version
```

Docker를 사용할 때만 `docker --version`과 `docker compose version`도 확인한다. `python3.11` 명령이 없으면 Python 3.11을 설치하거나 `uv python install 3.11`로 준비한다.

## 2. 저장소와 Python 환경 준비

VS Code에서 **`backend` 폴더 자체를 열어야** `.vscode` 실행 설정과 터미널의 작업 위치가 맞는다. 아래 명령은 모두 `backend` 폴더에서 실행한다. 이미 폴더를 열었다면 첫 `cd`는 건너뛴다.

```sh
cd backend
uv sync --locked
```

`uv sync --locked`는 `pyproject.toml`과 `uv.lock`에 지정된 패키지를 `.venv`에 설치한다. lock과 프로젝트 설정이 어긋나면 실패하므로 임의로 패키지를 설치하기보다 담당자와 함께 두 파일을 갱신한다. VS Code의 Python 인터프리터는 `backend/.venv`를 선택한다. 프로젝트를 새로 생성할 필요는 없다.

## 3. 로컬 설정 파일 준비

DB/큐를 실행하거나 프론트 주소를 바꿀 때 `.env.example`을 `.env`로 복사한다. `.env`는 Git에 올리지 않는다. 이미 파일이 있으면 덮어쓰지 않는다.

macOS/Linux:

```sh
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

| 변수 | 용도 | 현재 기본값/주의 |
|---|---|---|
| `CORS_ORIGINS` | 운영 API가 허용할 프론트 주소의 JSON 배열 | Vue/Vite 로컬 주소 `http://localhost:5173`; 실제 FE 주소가 다르면 변경 |
| `POSTGRES_USER/PASSWORD/DB` | 로컬 Compose의 DB 계정/DB 이름 | 로컬 예시값이며 운영 환경에 사용하지 않음 |

## 4. 운영 골격 실행

현재 운영 서버 두 개가 있다. 업무 API는 담당자가 구현해야 하므로 `/docs`에는 아직 health 경로만 나온다.

| 구분 | 실행 모듈 | 포트 | 현재 기능 |
|---|---|---|---|
| 사용자 API 골격 | `api.main:app` | 8000 | `/healthz`, Swagger, 공통 오류 처리 |
| AI API 골격 | `analysis.api.main:app` | 8001 | `/healthz`, Swagger |

각각 별도 터미널에서 실행한다.

```sh
uv run --locked uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
uv run --locked uvicorn analysis.api.main:app --host 127.0.0.1 --port 8001 --reload
```

각 포트의 `/healthz`는 프로세스 생존만 확인하며 DB·Redis 연결 상태를 보장하지 않는다. `/readyz`는 명세에 있으나 아직 구현하지 않았다.

## 5. DB와 Redis가 필요한 작업

박재흥·강유성 담당의 DB/큐 작업을 시작할 때만 Docker를 켜고 다음을 실행한다. `.env`가 있어야 Compose가 DB 계정을 읽는다.

```sh
docker compose up -d
docker compose ps
```

Compose는 PostgreSQL 16을 `127.0.0.1:5432`, Redis 7을 `127.0.0.1:6379`에 바인딩한다. 현재 운영 API 골격은 이 서비스에 연결되지 않는다. DB 모델·migration·Celery를 구현하면서 연결한다. 종료는 `docker compose down`을 사용한다. **`docker compose down -v`는 로컬 DB 볼륨의 데이터를 삭제한다.**

현재 ERD는 [v10 DBML](docs/specs/erd-v10.dbml)이다. PostgreSQL을 쓰는 이유는 이 ERD가 PostgreSQL의 `bytea`·`jsonb`·후속 `vector` 필드를 사용하기 때문이다. MySQL로 바꾸려면 타입·migration·대용량 영상·제약을 다시 설계해야 한다. ORM 또는 migration 도구는 아직 설치·설정하지 않았다. 실제 DB 작업 기준은 [DB 가이드](docs/DATABASE_RULES.md)를 읽는다.

## 6. 폴더 구조와 담당 경계

Spring 예시의 controller/service/repository/domain/dto/global에 해당하는 역할을 이 저장소의 FastAPI 구조로 보면 다음과 같다. **폴더의 내부 파일 구성은 담당자가 정한다.** 공통 API·DB 계약은 함께 검토한다.

```text
backend/
  api/
    main.py             # 사용자 API 앱 진입점
    routers/            # HTTP 요청·응답과 권한 경계 (Spring controller)
    services/           # 업무 규칙과 상태 전이 (service)
    models/             # PostgreSQL 테이블 모델 예정 (domain/repository와 연결)
    schemas/            # 사용자 API 요청·응답 모델 위치 (dto)
    clients/            # AI 서비스 호출 등 외부 연결
    core/               # 설정·공통 오류 (global)
    migrations/         # DB 변경 이력 예정
  analysis/
    api/main.py         # 운영 AI API 골격
    pipeline/           # 실제 분석 단계 연결 위치
    modules/            # stt, audio, vision, content, scoring, coaching
    worker/             # 장시간 분석 워커 구현 위치
  contracts/
    analysis.py         # 서버 간 작업·이벤트·STT·리포트 계약
    models.py           # 공통 응답·오류·프로젝트·업로드 계약
    examples/           # 합성 요청·리포트 JSON
    schemas/            # 코드에서 생성한 JSON Schema
  docs/                # 정본 명세·결정·담당·DB 규칙
  tests/               # 계약·HTTP 오류·실패 테스트
```

프론트는 저장소 루트의 `frontend/`에서 Vue 3 + TypeScript로 개발한다. 설치·실행 방법은 `frontend/README.md`를 따른다. [담당자별 폴더](docs/OWNERSHIP.md)에서 책임자와 리뷰어를 확인한다. 새 기능을 추가할 때 호출부·테스트·샘플·공통 계약에 미치는 영향을 함께 확인한다.

## 7. 명세와 API 확인 방법

[사용자 API v3.5](docs/specs/user-api-v3.5.md), [AI 내부 API v1.4](docs/specs/analysis-api-v1.4.md), [ERD v10](docs/specs/erd-v10.dbml)이 현재 정본이다. [적용 기준](docs/SPEC_ALIGNMENT.md)은 문서 간 차이와 현재 구현 상태를, [계약 결정](docs/CONTRACT_DECISIONS.md)은 계약 초안과 남은 정책을 설명한다. 이미지에서 추가된 내용·구조 평가의 세부 계약은 아직 확정되지 않았다.

`contracts/endpoint-catalog.json`은 **계획된 경로의 목록**이다. 실제 서버에 구현된 경로는 실행 중인 서버의 `/openapi.json` 또는 `/docs`에서 확인한다. 프론트가 리포트 화면을 먼저 만들 때는 `contracts/examples/report.json`과 `transcript.json`을 형식 확인용 예시로 사용할 수 있다. 실제 API 완성 여부와 혼동하지 않는다.

## 8. VS Code에서 작업하기

1. VS Code에서 저장소 루트가 아니라 `backend` 폴더를 연다.
2. 추천 확장(Python, Debugpy, Ruff)을 설치하고 `.venv` 인터프리터를 선택한다.
3. **Run and Debug**에서 `API :8000` 또는 `Analysis :8001`을 실행한다.
4. VS Code Tasks의 `Setup`과 `Check`를 사용할 수 있다.

## 9. 변경 전후 확인

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
```

계약 모델을 바꿨다면 다음 명령으로 JSON Schema를 갱신하고, 생성된 파일과 샘플·테스트를 함께 PR에 넣는다.

```sh
uv run --locked python -m contracts.export
```

팀 규칙은 [TEAM_RULES.md](TEAM_RULES.md), AI 도구 공통 지침은 [AGENTS.md](AGENTS.md), 담당과 MVP 완료 기준은 [OWNERSHIP.md](docs/OWNERSHIP.md)에 있다. PR에는 실제로 실행한 명령과 결과, 아직 검증하지 못한 부분을 적는다.

## 10. 자주 막히는 지점

| 상황 | 먼저 확인할 것 |
|---|---|
| `uv sync --locked` 실패 | `backend` 폴더인지, Python 3.11이 있는지, pyproject·lock이 함께 갱신됐는지 |
| 포트 사용 중 | 8000/8001을 이미 다른 서버가 사용 중인지 확인 |
| 운영 `/docs`에 업무 경로가 없음 | 운영 앱은 아직 health 골격이며 업무 API는 담당자가 구현해야 함 |
| PostgreSQL/Redis 연결 실패 | Docker가 실행 중인지, `docker compose ps` 상태와 포트 충돌을 확인 |
