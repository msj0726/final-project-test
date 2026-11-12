# ProPitch Vue 프론트엔드

**Vue 3 + TypeScript + Vite** 앱이다. 화면 디자인은 프로토타입(app5)의 외형을 그대로 따른다(`src/shared/styles/prototype.css`, 기본은 빨간 테마, 주소 뒤에 `?ui=blue`를 붙이면 파란 테마).

현재 백엔드(`backend/`)에는 `/healthz` 만 구현돼 있다. 그래서 이 앱은 **백엔드에 있는 경로는 실제 서버로, 아직 없는 경로는 목업으로** 동작한다. 목업은 `backend/contracts`의 응답 형식을 따르는 합성 데이터이며 실제 분석 결과가 아니다. UI 라이브러리는 정하지 않았다.

## 준비와 실행

Node.js 22.18 이상(또는 Vue 공식 안내가 허용하는 버전)과 npm이 필요하다. VS Code에서는 이 `frontend` 폴더를 열고 **Vue - Official** 확장을 사용한다.

```sh
cd frontend
npm ci
npm run dev
```

브라우저에서 http://localhost:5173 을 연다. 포트 5173이 사용 중이면 Vite가 다른 포트를 선택하지 않고 오류를 낸다. 이렇게 해야 백엔드의 `CORS_ORIGINS=["http://localhost:5173"]`과 주소가 어긋나지 않는다. 다른 포트를 쓰려면 `package.json`의 dev 포트와 백엔드 `.env`의 CORS_ORIGINS를 함께 바꾼다.

목업 로그인: `jiyoung@example.com` / `password123`. 새로 가입한 계정도 같은 브라우저에서 쓸 수 있다. 목업 데이터는 `localStorage`(`propitch-mock-db-v3`)에 저장되며, 초기화는 개발자도구에서 `localStorage.removeItem('propitch-mock-db-v3')`.

```sh
npm run typecheck   # Vue/TypeScript 검사 (strict + noUnused* + noImplicitReturns)
npm run lint        # ESLint (typescript-eslint + eslint-plugin-vue)
npm run test:e2e    # Playwright E2E (설치된 Chrome 사용)
npm run build       # 검사 + dist/ 생성
npm run preview
```

패키지를 추가하면 `package.json`과 `package-lock.json`을 함께 커밋한다.

## 백엔드 연결 방식 (`VITE_API_MODE`, `.env.example` 참고)

| 값 | 동작 |
|---|---|
| `hybrid` (기본) | `src/shared/api/client.ts`의 `IMPLEMENTED` 목록에 있는 경로만 실제 서버로, 나머지는 목업 |
| `real` | 모든 요청을 실제 서버로 |
| `mock` | 모든 요청을 목업으로 (백엔드 없이 실행) |

브라우저는 항상 같은 출처(5173)로 호출하고, Vite가 `/api`·`/healthz`·`/readyz`를 `VITE_PROXY_TARGET`(기본 `http://127.0.0.1:8000`)으로 넘긴다. 화면 하단의 검은 막대는 `/healthz` 호출 결과를 보여 준다.

로컬에서 백엔드를 함께 띄우려면 [백엔드 가이드](../backend/README.md)의 실행 방법을 따른다. 8000번 포트를 다른 프로그램이 쓰고 있으면 백엔드를 다른 포트로 띄우고 `VITE_PROXY_TARGET`을 맞춘다.

**백엔드가 경로를 구현하면:** `src/shared/api/client.ts`의 `IMPLEMENTED`에 그 경로를 추가한다. 그 경로부터 목업 대신 실제 서버를 호출하며 화면 코드는 바꾸지 않는다. 응답 형식이 달라졌다면 `src/shared/api/types.ts`와 `mock/`을 계약에 맞춰 함께 고친다.

## 파일과 담당

| 경로 | 역할 | 주 담당 |
|---|---|---|
| `src/App.vue`, `src/main.ts`, `src/router/`, `vite.config.ts`, `package.json` | 앱 시작·라우팅·공통 설정 | 이지영, 김승혜 검토 |
| `src/features/upload/`, `analysis-status/` | 영상 업로드·비동기 분석 상태 | 이지영 |
| `src/shared/api/`, `src/shared/lib/`, `src/shared/state/` | 사용자 API 호출·오류 형식·목업 서버·공통 유틸 | 이지영 |
| `src/features/auth/`, `projects/`, `history/`, `schedule/`, `account/`, `landing/`, `coming-soon/` | 로그인·프로젝트·이력·일정·계정·소개 화면 | 이지영 |
| `src/features/report/`, `transcript/`, `video-player/` | 보고서·전사·근거 시각 재생 | 김승혜 |
| `src/shared/ui/`, `src/shared/styles/` | 공통 컴포넌트·스타일 | 두 담당자 함께 |
| `infra/` | 프론트 실행·배포 관련 설정 | 이지영 |

각 담당 폴더의 내부 파일 이름과 구성은 담당자가 정한다. 공통 API 호출 방식, 라우팅, 전역 스타일·의존성을 바꿀 때는 두 프론트 담당자가 함께 검토한다. 이 앱은 `vue-router` 하나만 의존성으로 추가했다(상태 라이브러리는 쓰지 않고 `src/shared/state/`의 reactive 객체를 사용).

## 코드 검증

| 도구 | 하는 일 |
|---|---|
| TypeScript (`vue-tsc`) | 전체 타입 검사. `strict`, `noUnusedLocals/Parameters`, `noImplicitReturns` |
| ESLint | `eslint.config.js`. 정적 오류·`any` 금지·`console` 제한·Vue 템플릿 오류 |
| Playwright | `e2e/`. 로그인·보호 경로·프로젝트·업로드→분석→리포트·분석 실패 재시도·영상 재생·모바일 폭·테마·`/healthz` 프록시. 테스트 전용 서버(5174·5175)를 직접 띄우므로 개발 서버와 충돌하지 않는다. `/healthz` 테스트는 백엔드(8000)가 꺼져 있으면 건너뛴다 |
| Sentry (`@sentry/vue`) | 오류 수집. `VITE_SENTRY_DSN` 이 없으면 꺼진다. 영상·전사문·토큰·비밀번호가 나가지 않도록 데이터 수집 옵션을 모두 끄고 전송 직전에 헤더·본문·쿠키·사용자 정보를 지운다. 5xx·네트워크 오류는 요청 경로(ID 제거)와 상태 코드만 기록한다. `e2e/sentry.spec.ts` 가 가짜 DSN 으로 전송 내용을 가로채 검증한다 |

Playwright 는 처음 한 번 `npx playwright install chrome` 이 필요할 수 있다(이미 Chrome 이 설치돼 있으면 불필요).

## 구현된 화면 (질의응답 제외)

로그인/회원가입, 프로젝트 목록·생성·완료 표시·삭제, 영상 업로드(형식·크기·길이 검사, SHA-256 계산, 진행률), 분석 상태(실패 시 재시도), 리포트(점수·시간축·구간별 피드백·지표·전사문), 이력·추이, 발표 일정, 계정 설정.

**미구현:** 질의응답(`/qa`는 준비 중 안내), 발표자료(PDF) 등록, 관리자·전문가 화면, 비밀번호 재설정, 회차 비교(`/compare`).

## 계약과 맞춘 부분

- 요청·응답 형식은 `backend/contracts`(models.py, analysis.py)를 따른다. 단건 `{data}`, 목록 `{data,page}`(page.number는 0부터), 오류 `{error:{code,message,fields,details,retryable,requestId}}`, 업무 POST는 `Idempotency-Key`.
- 업로드: `POST /projects/{id}/uploads`(fileName·sizeBytes·contentType·checksum) → `PUT /uploads/{id}/content`(Content-Type, `X-Checksum-Sha256`) → `POST /uploads/{id}/complete`. 체크섬은 파일을 4MiB씩 읽는 증분 SHA-256(`src/shared/lib/sha256.ts`)으로 계산해 500MiB 파일도 메모리에 통째로 올리지 않는다.
- 목업이 만드는 Report·Transcript는 백엔드 Pydantic 모델(`contracts.analysis.Report`, `Transcript`)의 검증을 통과한다(구조·네 항목·가중치 0.25·시간 범위·시간 차이 규칙). 실제 분석 결과가 아니다.
- 항목 키는 `SPEECH_RATE`·`FLUENCY`·`GESTURE`·`GAZE`. 항목 이름은 응답에 없어 `src/shared/lib/rubric.ts`에서 매핑한다.

## 계약에 없어 임시로 정한 부분 (확정 필요, `src/shared/api/types.ts`의 `[가정]`)

1. `Report.timeline`의 신호 이름(`SPEECH_RATE_WINDOW`, `FAST_SPEECH`, `FILLER_WORD`, `LONG_PAUSE`, `LOW_STT_CONFIDENCE`, `HAND_MOTION`, `HAND_MOTION_HIGH`, `GAZE_OFF_FRONT`, `GAZE_OFF_SHORT`, `FACE_NOT_VISIBLE`)과 각 `value`의 단위. 화면은 알려진 신호만 그리고 모르는 신호는 무시한다(`src/shared/lib/signals.ts`).
2. `Report.segments[].kind` 값(`STRENGTH` = 잘한 점, 그 외 = 고칠 점), `expectedQuestions[].kind` 값(`TECH`/`BUSINESS`), `limitations[]` 코드(`FACE_NOT_VISIBLE_EXCLUDED`, `LOW_STT_CONFIDENCE`).
3. 프로젝트·회차 목록 응답 필드. 회차 목록에 `durationSec`·`createdAt`이 있다고 가정했다.
4. 프로젝트 카드·이력에 필요한 항목별 점수는 요약 API가 없어 회차 리포트를 읽어 만든다(`src/features/projects/projectOverview.ts`). 요약 필드가 생기면 이 파일만 바꾼다.
5. 약관 문서 버전을 프론트 상수로 보낸다.

## 구현 전 짚어야 할 기술 이슈

- **영상 재생 인증:** `GET /projects/{id}/rounds/{n}/video`는 Bearer 인증이라 `<video src>`로 헤더를 붙일 수 없다. 쿠키·단기 토큰 등 방식 합의가 필요하다. 목업은 내장 샘플 영상(`public/sample/sample-pitch.mp4`, 2분 합성 화면)을 재생하고, 실제 모드에서는 영상 없이 시계만 흘리는 플레이어로 동작한다(`src/features/video-player/usePlayer.ts`, `videoSrc()`).
- **토큰 보관:** 현재 `sessionStorage`. 운영 방식(쿠키 vs 저장소)은 백엔드와 합의 후 확정.
- **영상 보존 기간:** 명세에 확정된 값이 없어 화면에 "자동 삭제 N일" 문구를 쓰지 않았다.

## 백엔드와 연결할 때

공용 계약은 [backend/contracts](../backend/contracts/README.md), 실제 구현 상태는 [백엔드 가이드](../backend/README.md)를 따른다. 예시 점수를 실제 평가 결과처럼 표시하지 않는다.

프론트는 사용자 API만 호출한다. PostgreSQL·Redis·analysis 내부 API·서비스 토큰을 브라우저 코드에 넣지 않는다. 공통 규칙과 담당 경계는 [팀 규칙](../backend/TEAM_RULES.md)과 [담당 문서](../backend/docs/OWNERSHIP.md)를 확인한다.

참고: [Vue 공식 시작 안내](https://vuejs.org/guide/quick-start.html).
