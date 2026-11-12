# ProPitch 사용자 및 AI 통합 API 명세 v3.6

검토안 · 2026-11-10 · 사용자 API v3.5와 AI 내부 API v1.4 통합

이번 통합본은 발표자료 등록·실시간 QA와 전사 기반 예상 질문 생성을 모두 유지한다. PDF 자료는 QA 검색용이며 발표 행동 점수에는 반영하지 않는다.

브라우저는 사용자 API에 영상을 올린다. 사용자 API는 영상 바이트를 DB에 저장하고 분석 서버에 작업을 맡긴다. 분석 서버는 STT·음향·Vision 특징을 추출하고, 규칙과 지정된 LLM 휴리스틱 기준으로 발화속도·유창성·제스처·시선을 평가한다. 서버가 네 항목 점수와 동일 가중 평균 총점을 검증해 사용자에게 제공한다.

**읽는 법:** A부는 브라우저와 사용자 API 서버의 계약이고 B부는 서버 간 AI 계약이다. A부 URL에는 `/api/v1`을 붙인다(healthz/readyz 제외). B부에는 붙이지 않는다. JSON 값은 설명용 예시이며 실제 점수·성능·토큰 수명으로 확정한 값이 아니다. 입력 길이·비밀번호 정책처럼 정하지 않은 제한은 임의로 추가하지 않았다.

## A. 사용자 API

### A-0. 공통 규칙

- 공개 인증 경로 외에는 Bearer 인증. USER는 자기 자원, ADMIN은 운영 기능만 접근한다. 타인 자원은 404, 역할 불일치는 403이다.
- 성공 단건은 `{data:...}`, 페이지 목록은 `{data:[],page:{number,size,total}}`. 204는 JSON 없이 응답한다.
- 업무 POST는 Idempotency-Key 필수(login/refresh/logout/ticket 제외). 같은 키·요청은 같은 결과, 다른 내용은 409다.
- UUID는 자원 ID, 시각은 UTC RFC 3339. 표에서 `?`는 선택 입력, null은 값이 없음을 뜻한다. PATCH의 생략 필드는 유지한다.
- 삭제는 즉시 접근 차단·삭제 예약이다. 영상·전사문·토큰을 로그에 남기지 않는다.
- 아래 실패 항목은 대표 사례다. 공통으로 입력 오류 400, 인증 실패 401, 권한/동의 403, 자원 없음 404, 제한 429, 일시 장애 503을 적용한다. 내부 API의 422와 사용자 API의 입력 검증 400을 구분한다.

실패 응답 예시:
```json
{
  "error": {
    "code": "REPORT_NOT_READY",
    "message": "아직 분석 리포트가 준비되지 않았습니다.",
    "fields": {},
    "details": {},
    "retryable": false,
    "requestId": "req-example"
  }
}
```

| 값 | 의미 |
| --- | --- |
| code / message | 프로그램이 분기할 오류 코드 / 화면 안내 문장 |
| fields / details | 필드별 오류 / 오류의 추가 정보 |
| retryable / requestId | 같은 작업 재시도 가능 여부 / 서버 로그 추적 ID |


### A-1. 인증과 계정


#### 회원가입

**기능 개요:** 일반 사용자 계정과 현재 동의를 DB에 저장한다.

**요청**

- Method: `POST`
- URL: `/auth/signup`

- Body (JSON 예시):

```json
{
  "name": "홍길동",
  "email": "user@example.com",
  "password": "Example-only!123",
  "agreements": {
    "terms": true,
    "privacy": true,
    "aiAnalysis": true
  },
  "agreementVersions": {
    "terms": "v1",
    "privacy": "v1",
    "aiAnalysis": "v1"
  }
}
```

| 값 | 의미 |
| --- | --- |

| `name` | 표시할 이름 또는 프로젝트 제목. |

| `email` | 이메일 주소. |

| `password` | 비밀번호. 전송 시 HTTPS 사용, DB에는 해시만 저장. |

| `agreements` | terms=이용약관, privacy=개인정보, aiAnalysis=AI 분석 동의. |

| `agreementVersions` | 각 동의 문서의 버전. |


**응답**

- 성공 (201): 아래 JSON 예시.


```json
{
  "data": {
    "user": {
      "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      "name": "홍길동",
      "email": "user@example.com",
      "role": "USER",
      "createdAt": "2026-11-10T00:00:00Z"
    }
  }
}
```


- 실패: 409 EMAIL_ALREADY_EXISTS: 이미 사용 중인 이메일.


회원가입은 USER만 생성한다. 관리자 계정은 운영 절차로 만든다. 사용자당 현재 동의 한 행을 유지하며 과거 동의 이력은 저장하지 않는다.


#### 로그인

**기능 개요:** 이메일·비밀번호를 확인하고 로그인 토큰을 발급한다.

**요청**

- Method: `POST`
- URL: `/auth/login`

- Body (JSON 예시):

```json
{
  "email": "user@example.com",
  "password": "Example-only!123"
}
```

| 값 | 의미 |
| --- | --- |

| `email` | 이메일 주소. |

| `password` | 비밀번호. 전송 시 HTTPS 사용, DB에는 해시만 저장. |


**응답**

- 성공 (200): 아래 JSON 예시.


```json
{
  "data": {
    "user": {
      "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      "name": "홍길동",
      "email": "user@example.com",
      "role": "USER",
      "createdAt": "2026-11-10T00:00:00Z"
    },
    "tokens": {
      "accessToken": "예시-액세스-토큰",
      "accessTokenExpiresAt": "2026-11-10T01:00:00Z",
      "refreshToken": "예시-갱신-토큰",
      "refreshTokenExpiresAt": "2026-11-11T00:00:00Z"
    }
  }
}
```


- 실패: 401 UNAUTHENTICATED: 인증 실패.


user는 계정 정보, tokens는 액세스·갱신 토큰과 각 만료 시각이다. 예시 날짜 간격은 토큰 수명 정책이 아니다.


#### 토큰 갱신

**기능 개요:** 갱신 토큰으로 새로운 토큰 쌍을 발급한다.

**요청**

- Method: `POST`
- URL: `/auth/refresh`

- Body (JSON 예시):

```json
{
  "refreshToken": "예시-갱신-토큰"
}
```

| 값 | 의미 |
| --- | --- |

| `refreshToken` | 액세스 토큰을 갱신하거나 로그아웃할 로그인 세션의 토큰. |


**응답**

- 성공 (200): 아래 JSON 예시.


```json
{
  "data": {
    "tokens": {
      "accessToken": "예시-액세스-토큰",
      "accessTokenExpiresAt": "2026-11-10T01:00:00Z",
      "refreshToken": "예시-갱신-토큰",
      "refreshTokenExpiresAt": "2026-11-11T00:00:00Z"
    }
  }
}
```


- 실패: 401: 만료·폐기되었거나 유효하지 않은 갱신 토큰.


#### 로그아웃

**기능 개요:** 해당 로그인 세션의 갱신 토큰을 폐기한다.

**요청**

- Method: `POST`
- URL: `/auth/logout`

- Body (JSON 예시):

```json
{
  "refreshToken": "예시-갱신-토큰"
}
```

| 값 | 의미 |
| --- | --- |

| `refreshToken` | 액세스 토큰을 갱신하거나 로그아웃할 로그인 세션의 토큰. |


**응답**

- 성공 (204): 본문 없음.


#### 비밀번호 재설정 메일 요청

**기능 개요:** 가입된 이메일이면 재설정 메일 발송을 요청한다.

**요청**

- Method: `POST`
- URL: `/auth/password-reset`

- Body (JSON 예시):

```json
{
  "email": "user@example.com"
}
```

| 값 | 의미 |
| --- | --- |

| `email` | 이메일 주소. |


**응답**

- 성공 (202): 접수. 가입 여부가 응답으로 드러나지 않게 한다.


#### 비밀번호 재설정

**기능 개요:** 유효한 일회용 토큰으로 비밀번호를 바꾼다.

**요청**

- Method: `POST`
- URL: `/auth/password-reset/confirm`

- Body (JSON 예시):

```json
{
  "token": "예시-일회용-토큰",
  "newPassword": "New-example!123"
}
```

| 값 | 의미 |
| --- | --- |

| `token` | 비밀번호 재설정 메일로 받은 일회용 토큰. |

| `newPassword` | 새 비밀번호. |


**응답**

- 성공 (204): 본문 없음.


- 실패: 400: 재설정 토큰 또는 입력이 유효하지 않음.


#### 내 정보 조회

**기능 개요:** 내 계정과 현재 동의를 조회한다.

**요청**

- Method: `GET`
- URL: `/me`

- Body: 없음.


**응답**

- 성공 (200): 아래 JSON 예시.


```json
{
  "data": {
    "user": {
      "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      "name": "홍길동",
      "email": "user@example.com",
      "role": "USER",
      "createdAt": "2026-11-10T00:00:00Z"
    },
    "agreements": {
      "terms": true,
      "privacy": true,
      "aiAnalysis": true
    },
    "agreementVersions": {
      "terms": "v1",
      "privacy": "v1",
      "aiAnalysis": "v1"
    }
  }
}
```


#### 내 정보 변경

**기능 개요:** 이름 또는 비밀번호를 변경한다.

**요청**

- Method: `PATCH`
- URL: `/me`

- Body (JSON 예시):

```json
{
  "name": "새 이름"
}
```

| 값 | 의미 |
| --- | --- |

| `name` | 표시할 이름 또는 프로젝트 제목. |


**응답**

- 성공 (200): 아래 JSON 예시.


```json
{
  "data": {
    "user": {
      "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      "name": "홍길동",
      "email": "user@example.com",
      "role": "USER",
      "createdAt": "2026-11-10T00:00:00Z"
    }
  }
}
```


입력 가능 필드는 name?, currentPassword?, newPassword?. 비밀번호 변경 시 현재·새 비밀번호를 함께 제공한다. 예시는 이름 변경만 표시했다.


#### 현재 동의 갱신

**기능 개요:** 현재 동의와 문서 버전을 갱신한다.

**요청**

- Method: `PUT`
- URL: `/me/agreements`

- Body (JSON 예시):

```json
{
  "agreements": {
    "terms": true,
    "privacy": true,
    "aiAnalysis": true
  },
  "agreementVersions": {
    "terms": "v1",
    "privacy": "v1",
    "aiAnalysis": "v1"
  }
}
```

| 값 | 의미 |
| --- | --- |

| `agreements` | terms=이용약관, privacy=개인정보, aiAnalysis=AI 분석 동의. |

| `agreementVersions` | 각 동의 문서의 버전. |


**응답**

- 성공 (200): 아래 JSON 예시.


```json
{
  "data": {
    "agreements": {
      "terms": true,
      "privacy": true,
      "aiAnalysis": true
    },
    "agreementVersions": {
      "terms": "v1",
      "privacy": "v1",
      "aiAnalysis": "v1"
    }
  }
}
```


#### 회원 탈퇴

**기능 개요:** 계정과 하위 데이터 접근을 막고 삭제를 예약한다.

**요청**

- Method: `DELETE`
- URL: `/me`

- Body (JSON 예시):

```json
{
  "password": "Example-only!123"
}
```

| 값 | 의미 |
| --- | --- |

| `password` | 비밀번호. 전송 시 HTTPS 사용, DB에는 해시만 저장. |


**응답**

- 성공 (204): 본문 없음.


### A-2. 프로젝트


#### 프로젝트 목록

**기능 개요:** 내 프로젝트 카드 목록을 조회한다.

**요청**

- Method: `GET`
- URL: `/projects`

- 경로·쿼리·헤더: status?, page?, size? — 상태 필터·페이지 번호·페이지 크기.

- Body: 없음.


**응답**

- 성공 (200): 프로젝트 카드의 페이지 목록. 카드 집계 필드의 최종 스키마는 확정 필요.


#### 프로젝트 생성

**기능 개요:** 발표 프로젝트를 만들고 활성 루브릭을 고정한다.

**요청**

- Method: `POST`
- URL: `/projects`

- Body (JSON 예시):

```json
{
  "name": "서비스 소개 발표",
  "topic": "서비스 계획",
  "finalDate": null,
  "targetMinutes": 10
}
```

| 값 | 의미 |
| --- | --- |

| `name` | 표시할 이름 또는 프로젝트 제목. |

| `topic` | 프로젝트의 발표 주제. 이번 행동 점수의 내용 의미 평가는 하지 않음. |

| `finalDate` | 발표 날짜(YYYY-MM-DD). null이면 미정. |

| `targetMinutes` | 목표 발표 시간(분). 생략 시 30, 0이면 제한 없음. |


**응답**

- 성공 (201): 아래 JSON 예시.


```json
{
  "data": {
    "project": {
      "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      "name": "서비스 소개 발표",
      "topic": "서비스 계획",
      "finalDate": null,
      "targetMinutes": 10,
      "done": false,
      "rubricVersion": "r1",
      "createdAt": "2026-11-10T00:00:00Z"
    }
  }
}
```


- 실패: 409 RUBRIC_UNAVAILABLE: 적용 가능한 활성 루브릭이 없음.


#### 프로젝트 상세

**기능 개요:** 프로젝트와 연습 회차를 조회한다.

**요청**

- Method: `GET`
- URL: `/projects/{projectId}`

- 경로·쿼리·헤더: projectId: 프로젝트 UUID.

- Body: 없음.


**응답**

- 성공 (200): 아래 JSON 예시.


```json
{
  "data": {
    "project": {
      "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      "name": "서비스 소개 발표",
      "topic": "서비스 계획",
      "finalDate": null,
      "targetMinutes": 10,
      "done": false,
      "rubricVersion": "r1",
      "createdAt": "2026-11-10T00:00:00Z"
    },
    "rounds": [],
    "materials": [],
    "qaEligible": false
  }
}
```


project의 rubricVersion은 이 프로젝트에 고정된 채점 기준이다. materials는 등록 자료, qaEligible은 QA 시작 가능 여부다.


#### 프로젝트 수정

**기능 개요:** 프로젝트 설정을 바꾼다.

**요청**

- Method: `PATCH`
- URL: `/projects/{projectId}`

- 경로·쿼리·헤더: projectId: 프로젝트 UUID.

- Body (JSON 예시):

```json
{
  "name": "수정한 제목",
  "targetMinutes": 15
}
```

| 값 | 의미 |
| --- | --- |

| `name` | 표시할 이름 또는 프로젝트 제목. |

| `targetMinutes` | 목표 발표 시간(분). 생략 시 30, 0이면 제한 없음. |


**응답**

- 성공 (200): 아래 JSON 예시.


```json
{
  "data": {
    "project": {
      "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      "name": "수정한 제목",
      "topic": "서비스 계획",
      "finalDate": null,
      "targetMinutes": 15,
      "done": false,
      "rubricVersion": "r1",
      "createdAt": "2026-11-10T00:00:00Z"
    }
  }
}
```


name?, topic?, finalDate?, targetMinutes?, done? 중 변경할 값만 보낸다. 응답 project에는 실제 변경값을 반영한다. 위 응답은 공통 객체 구조 예시다.


#### 프로젝트 삭제

**기능 개요:** 프로젝트와 하위 회차의 삭제를 예약한다.

**요청**

- Method: `DELETE`
- URL: `/projects/{projectId}`

- 경로·쿼리·헤더: projectId: 프로젝트 UUID.

- Body: 없음.


**응답**

- 성공 (204): 본문 없음.


### A-3. 영상 업로드와 재생


영상 한도는 **500 MiB(524,288,000바이트)·30분**이다. MP4/MOV 실제 내용을 검사한다. FastAPI가 직접 수신하며 영상 바이트는 `uploads.video_data`에 저장한다. 업로드 준비와 회차는 한 트랜잭션으로 생성한다.


#### 업로드 준비

**기능 개요:** 영상 전송 전에 업로드와 회차를 만든다.

**요청**

- Method: `POST`
- URL: `/projects/{projectId}/uploads`

- 경로·쿼리·헤더: projectId, Idempotency-Key.

- Body (JSON 예시):

```json
{
  "fileName": "presentation.mp4",
  "sizeBytes": 10485760,
  "contentType": "video/mp4",
  "checksum": "0000000000000000000000000000000000000000000000000000000000000000"
}
```

| 값 | 의미 |
| --- | --- |

| `fileName` | 원본 영상 파일명. |

| `sizeBytes` | 영상 크기(바이트). 서버가 실제 크기도 검사. |

| `contentType` | 영상 MIME 형식. 실제 미디어 내용도 검사. |

| `checksum` | 원본 영상의 SHA-256 해시. 64자리 16진수. |


**응답**

- 성공 (201): 아래 JSON 예시.


```json
{
  "data": {
    "uploadId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "roundNo": 1,
    "status": "CREATED",
    "expiresAt": "2026-11-10T01:00:00Z",
    "uploadPath": "/api/v1/uploads/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/content"
  }
}
```


- 실패: 413: 신고한 파일 크기 초과.


uploadId는 전송 ID, roundNo는 프로젝트 내 회차 번호, expiresAt은 전송 마감, uploadPath는 다음 PUT 요청 주소다. checksum의 0 반복은 모양만 보여주는 예시이며 실제 파일 해시로 교체해야 한다.


#### 영상 전송

**기능 개요:** 원본 영상 바이트를 서버로 전송한다.

**요청**

- Method: `PUT`
- URL: `/uploads/{uploadId}/content`

- 경로·쿼리·헤더: uploadId, Content-Type, X-Checksum-Sha256.

- Body: 영상 바이너리. JSON·Base64가 아니다.


**응답**

- 성공 (204): 본문 없음.


- 실패: 409: 같은 업로드에 다른 파일 전송. 413: 크기 초과. 415: 지원하지 않는 형식.


같은 업로드·같은 파일 재전송은 동일 결과다. 실제 크기·해시·재생 가능성·길이를 완료 시 다시 검증한다.


#### 업로드 완료와 분석 요청

**기능 개요:** 전송된 영상을 검증하고 분석을 한 번만 접수한다.

**요청**

- Method: `POST`
- URL: `/uploads/{uploadId}/complete`

- 경로·쿼리·헤더: uploadId, Idempotency-Key.

- Body: 없음.


**응답**

- 성공 (202): 아래 JSON 예시.


```json
{
  "data": {
    "analysisRef": {
      "projectId": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      "roundNo": 1,
      "analysisId": "22222222-2222-4222-8222-222222222222"
    },
    "status": "QUEUED"
  }
}
```


- 실패: 409 UPLOAD_INCOMPLETE: 파일 없음. 410 UPLOAD_EXPIRED: 만료. 400 CHECKSUM_MISMATCH: 해시 불일치. 413: 길이·크기 초과.


analysisId는 회차 UUID이며 재시도해도 유지된다. QUEUED는 분석 접수 상태다.


#### 업로드 취소

**기능 개요:** 미완료 업로드를 취소하고 정리를 예약한다.

**요청**

- Method: `DELETE`
- URL: `/uploads/{uploadId}`

- 경로·쿼리·헤더: uploadId.

- Body: 없음.


**응답**

- 성공 (204): 본문 없음.


#### 영상 재생

**기능 개요:** 소유자의 영상을 DB에서 읽어 재생한다.

**요청**

- Method: `GET`
- URL: `/projects/{projectId}/rounds/{roundNo}/video`

- 경로·쿼리·헤더: projectId, roundNo, Bearer 인증, Range?(부분 요청).

- Body: 없음.


**응답**

- 성공 (200): 200 전체 영상 또는 206 요청한 바이트 구간. JSON 응답이 아니다.


- 실패: 404: 접근 불가. 410: 삭제됨.


Range·Content-Range 처리와 500 MiB bytea 읽기 성능은 별도 구현·검증한다.


### A-4. 분석과 리포트


#### 회차 목록

**기능 개요:** 프로젝트의 회차별 상태와 총점을 조회한다.

**요청**

- Method: `GET`
- URL: `/projects/{projectId}/rounds`

- 경로·쿼리·헤더: projectId.

- Body: 없음.


**응답**

- 성공 (200): 아래 JSON 예시.


```json
{
  "data": [
    {
      "roundNo": 1,
      "analysisId": "22222222-2222-4222-8222-222222222222",
      "status": "DONE",
      "progress": 100,
      "totalScore": 79,
      "createdAt": "2026-11-10T00:00:00Z"
    }
  ]
}
```


완료 전 점수의 null 처리 등 전체 목록 스키마는 최종 확정 필요.


#### 분석 상태 조회

**기능 개요:** 분석 진행률 또는 실패 이유를 조회한다.

**요청**

- Method: `GET`
- URL: `/projects/{projectId}/rounds/{roundNo}/status`

- 경로·쿼리·헤더: projectId, roundNo.

- Body: 없음.


**응답**

- 성공 (200): 아래 JSON 예시.


```json
{
  "data": {
    "status": "ANALYZING",
    "progress": 43,
    "stage": "AUDIO",
    "etaSec": null
  }
}
```


status는 큰 상태, stage는 내부 단계, progress는 0~100 진행률, etaSec는 예상 남은 초(모르면 null). 실패 시 failure={code,retryable}를 반환한다.


#### 분석 재시도

**기능 개요:** 실패한 회차의 새 분석 실행을 접수한다.

**요청**

- Method: `POST`
- URL: `/projects/{projectId}/rounds/{roundNo}/retry`

- 경로·쿼리·헤더: projectId, roundNo, Idempotency-Key.

- Body: 없음.


**응답**

- 성공 (202): 아래 JSON 예시.


```json
{
  "data": {
    "status": "QUEUED"
  }
}
```


- 실패: 409 INVALID_STATE: 재시도할 수 없는 상태.


자동 재시도는 일시 장애에 1회다. 사용자 수동 재시도 한도는 별도 확정 필요. 새 실행은 새 jobId·attempt로 구분한다.


#### 분석 리포트 조회

**기능 개요:** 네 가지 항목 점수·총점·근거·코칭을 조회한다.

**요청**

- Method: `GET`
- URL: `/projects/{projectId}/rounds/{roundNo}/report`

- 경로·쿼리·헤더: projectId, roundNo.

- Body: 없음.


**응답**

- 성공 (200): 아래 JSON 예시.


```json
{
  "data": {
    "report": {
      "analysisId": "22222222-2222-4222-8222-222222222222",
      "projectId": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      "roundNo": 1,
      "status": "DONE",
      "totalScore": 79,
      "scores": [
        {
          "rubricItemId": "00000001-1111-4111-8111-111111111111",
          "itemKey": "SPEECH_RATE",
          "score": 80,
          "weight": 0.25,
          "scoreSource": "RULE",
          "evidence": []
        },
        {
          "rubricItemId": "00000002-1111-4111-8111-111111111111",
          "itemKey": "FLUENCY",
          "score": 70,
          "weight": 0.25,
          "scoreSource": "HYBRID",
          "evidence": []
        },
        {
          "rubricItemId": "00000003-1111-4111-8111-111111111111",
          "itemKey": "GESTURE",
          "score": 90,
          "weight": 0.25,
          "scoreSource": "HYBRID",
          "evidence": []
        },
        {
          "rubricItemId": "00000004-1111-4111-8111-111111111111",
          "itemKey": "GAZE",
          "score": 76,
          "weight": 0.25,
          "scoreSource": "RULE",
          "evidence": []
        }
      ],
      "versions": {
        "model": "m1",
        "rubric": "r1"
      },
      "segments": [],
      "timeline": {},
      "coaching": {
        "strengths": [],
        "improvements": [],
        "actions": []
      },
      "targetMinutes": 10,
      "timeCheck": {
        "actualMinutes": 9,
        "deltaMinutes": -1
      },
      "contentCheck": null,
      "expectedQuestions": [],
      "quality": "NORMAL",
      "limitations": []
    }
  }
}
```


- 실패: 409 REPORT_NOT_READY: 아직 공개 가능한 결과 없음.


점수는 구조 예시이며 검증된 성적이 아니다. 실제 결과의 근거 배열과 시간축 JSON 세부 스키마는 채점 기준과 함께 확정한다.


| 리포트 값 | 뜻 |
| --- | --- |
| SPEECH_RATE / FLUENCY / GESTURE / GAZE | 발화속도 / 유창성 / 제스처 / 시선 |
| score / totalScore | 각 0~100점 / 네 항목 동일 가중 평균 |
| scoreSource | RULE=규칙, LLM=지정된 LLM 기준, HYBRID=두 방식 합산 |
| rubricItemId / weight | 적용한 루브릭 항목 ID / 총점에서의 비중 0.25 |
| evidence / timeline / segments | 채점 근거 / 시간별 관찰값 / 구간별 피드백 |
| coaching | strengths=강점, improvements=개선점, actions=실천 조언 |
| versions | 적용한 모델·루브릭 버전. 비교 기준 확인용 |
| timeCheck | 실제 발표 시간과 목표 대비 차이(분) |
| quality / limitations | NORMAL 또는 DEGRADED / 관찰·생성 한계 |
| expectedQuestions | 전사 기반 예상 질문. 실시간 QA 세션과 별개이며 점수에 반영하지 않음 |


#### STT 전사 조회

**기능 개요:** 완료된 분석의 전사 문장과 영상 내 시각을 조회한다.

**요청**

- Method: `GET`
- URL: `/projects/{projectId}/rounds/{roundNo}/transcript`

- 경로·쿼리·헤더: projectId, roundNo.

- Body: 없음.


**응답**

- 성공 (200): 아래 JSON 예시.


```json
{
  "data": {
    "utterances": [
      {
        "seq": 1,
        "startSec": 0.5,
        "endSec": 3.2,
        "text": "안녕하세요. 발표를 시작하겠습니다."
      }
    ]
  }
}
```


- 실패: 409 REPORT_NOT_READY: 분석 미완료.


seq는 발화 순서, startSec/endSec는 영상 시작부터 지난 초, text는 인식한 문장이다. 공개 리포트의 jobId에 연결된 전사만 반환한다.


#### 회차 비교

**기능 개요:** 두 완료 회차의 같은 기준 점수를 비교한다.

**요청**

- Method: `GET`
- URL: `/projects/{projectId}/compare`

- 경로·쿼리·헤더: projectId, from=이전 회차 번호, to=현재 회차 번호.

- Body: 없음.


**응답**

- 성공 (200): `{data:{items:[],deltas:[]}}` 구조. 항목별 점수와 차이의 상세 객체는 확정 필요.


- 실패: 404 NO_COMPARABLE_ROUND: 비교할 완료 회차가 없음.


같은 모델·루브릭 버전인지 확인한다. 다른 버전을 같은 기준의 개선으로 표현하지 않는다.


#### 회차 삭제

**기능 개요:** 영상·전사·리포트 접근을 막고 삭제를 예약한다.

**요청**

- Method: `DELETE`
- URL: `/projects/{projectId}/rounds/{roundNo}`

- 경로·쿼리·헤더: projectId, roundNo.

- Body: 없음.


**응답**

- 성공 (204): 본문 없음.


#### 발표 일정

**기능 개요:** 프로젝트의 발표 날짜와 남은 날짜를 조회한다.

**요청**

- Method: `GET`
- URL: `/schedule`

- 경로·쿼리·헤더: month?: YYYY-MM.

- Body: 없음.


**응답**

- 성공 (200): 아래 JSON 예시.


```json
{
  "data": [
    {
      "projectId": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      "name": "서비스 소개 발표",
      "finalDate": "2026-11-20",
      "dday": 10
    }
  ]
}
```


### A-5. 발표 자료와 실시간 질의응답


자료 업로드와 실시간 QA를 유지한다. PDF는 QA 검색에 사용할 수 있지만 발표 행동 분석 작업에는 보내지 않는다.


#### 발표 자료 등록

**기능 개요:** 프로젝트에 검색용 PDF를 등록한다.

**요청**

- Method: `POST`
- URL: `/projects/{projectId}/materials`

- 경로·쿼리·헤더: projectId, Idempotency-Key.

- Body: multipart/form-data: file=PDF 파일, confidentialConfirmed=true(대외비가 아닌 자료임을 확인).


**응답**

- 성공 (202): `{data:{materialId,fileName,sizeBytes,contentType,indexStatus}}`.


- 실패: 400 CONFIDENTIAL_NOT_CONFIRMED: 확인 누락. 413: 크기 초과. 415: PDF가 아님.


indexStatus는 NONE/INDEXING/READY/FAILED다. 실제 PDF 내용도 검사한다. 20 MiB 자료 크기 한도는 기존 문서의 가안으로 확정 필요.


#### 발표 자료 목록

**기능 개요:** 자료 파일과 검색 색인 상태를 조회한다.

**요청**

- Method: `GET`
- URL: `/projects/{projectId}/materials`

- 경로·쿼리·헤더: projectId.

- Body: 없음.


**응답**

- 성공 (200): `{data:{materials:[{id,fileName,sizeBytes,contentType,indexStatus}]}}`. READY 자료만 QA 검색에 사용한다.


#### 발표 자료 삭제

**기능 개요:** 선택 자료와 검색 색인의 삭제를 예약한다.

**요청**

- Method: `DELETE`
- URL: `/projects/{projectId}/materials/{materialId}`

- 경로·쿼리·헤더: projectId, materialId.

- Body: 없음.


**응답**

- 성공 (204): 본문 없음.


#### QA 시작 가능 여부

**기능 개요:** 분석 완료 회차가 있어 QA를 시작할 수 있는지 확인한다.

**요청**

- Method: `GET`
- URL: `/projects/{projectId}/qa/eligibility`

- 경로·쿼리·헤더: projectId.

- Body: 없음.


**응답**

- 성공 (200): 아래 JSON 예시.


```json
{
  "data": {
    "eligible": true,
    "rounds": [
      {
        "roundNo": 1,
        "analysisId": "22222222-2222-4222-8222-222222222222",
        "createdAt": "2026-11-10T00:00:00Z"
      }
    ],
    "defaultRoundNo": 1,
    "readyMaterialCount": 0
  }
}
```


eligible은 시작 가능 여부, defaultRoundNo는 기본 기준 회차, readyMaterialCount는 검색 가능한 PDF 수다. 동시 세션 가능 여부는 실제 세션 생성 시 다시 검사한다.


#### QA 세션 생성

**기능 개요:** 완료 회차를 기준으로 질문 계획과 실시간 연결을 준비한다.

**요청**

- Method: `POST`
- URL: `/projects/{projectId}/qa/sessions`

- 경로·쿼리·헤더: projectId, Idempotency-Key.

- Body (JSON 예시):

```json
{
  "baseRoundNo": 1,
  "consentCameraMic": true
}
```

| 값 | 의미 |
| --- | --- |

| `baseRoundNo` | 질문의 기준으로 삼을 발표 회차. 선택값이며 생략하면 최근 DONE 회차. |

| `consentCameraMic` | 카메라·마이크 사용 동의. true여야 시작 가능. |


**응답**

- 성공 (201): `{data:{sessionId,status:"READY",plan,wsUrl,wsTicket,wsTicketExpiresAt}}`.


- 실패: 409 QA_NOT_ELIGIBLE: 분석 완료 회차 없음. 409 QA_SESSION_ACTIVE: 진행 중 세션 있음.


plan은 질문 주제·순서·예정 개수, wsUrl은 FastAPI 연결 주소, wsTicket은 1회용 접속 티켓이다. 최대 질문 10개에는 꼬리·추가 질문이 포함된다.


#### QA 세션 조회

**기능 개요:** 세션의 현재 진행 상태를 조회한다.

**요청**

- Method: `GET`
- URL: `/qa/sessions/{sessionId}`

- 경로·쿼리·헤더: sessionId.

- Body: 없음.


**응답**

- 성공 (200): `{data:{session}}`. READY→LIVE→WRAP_UP→ENDED 상태와 질문 진행 정보를 포함. session 전체 스키마는 확정 필요.


#### QA 접속 티켓 재발급

**기능 개요:** 재연결에 필요한 일회용 티켓을 발급한다.

**요청**

- Method: `POST`
- URL: `/qa/sessions/{sessionId}/ticket`

- 경로·쿼리·헤더: sessionId.

- Body: 없음.


**응답**

- 성공 (200): `{data:{wsTicket,wsTicketExpiresAt}}`. 티켓은 만료되거나 사용되면 다시 사용할 수 없다.


#### QA 추가 질문

**기능 개요:** 질문 한도를 넘지 않는 범위에서 추가 질문을 요청한다.

**요청**

- Method: `POST`
- URL: `/qa/sessions/{sessionId}/more`

- 경로·쿼리·헤더: sessionId, Idempotency-Key.

- Body: 없음.


**응답**

- 성공 (202): `{data:{askedCount,maxQuestions}}`.


- 실패: 409 QA_LIMIT_REACHED: 10개 상한. 409 QA_SESSION_ENDED: 종료된 세션.


#### QA 종료

**기능 개요:** 질문을 마치고 QA 리포트 생성을 요청한다.

**요청**

- Method: `POST`
- URL: `/qa/sessions/{sessionId}/end`

- 경로·쿼리·헤더: sessionId, Idempotency-Key.

- Body: 없음.


**응답**

- 성공 (202): `{data:{status:"ENDED",reportReady}}`.


reportReady는 리포트 준비 완료 여부다. 답변 0개일 때 리포트를 생성할지는 확정 필요.


#### 질문 근거 조회

**기능 개요:** 사용자가 요청했을 때만 질문의 근거를 보여준다.

**요청**

- Method: `GET`
- URL: `/qa/sessions/{sessionId}/questions/{questionId}/evidence`

- 경로·쿼리·헤더: sessionId, questionId.

- Body: 없음.


**응답**

- 성공 (200): `{data:{evidence:[{kind,ref,excerpt}]}}`.


kind는 ANALYSIS 또는 MATERIAL, ref는 분석 구간 또는 자료 참조, excerpt는 공개 가능한 근거 발췌다. 일반 질문 응답에는 근거 전문 대신 evidenceAvailable만 준다.


#### QA 리포트 조회

**기능 개요:** 질문·답변·주제별 결과와 QA 요약을 조회한다.

**요청**

- Method: `GET`
- URL: `/qa/sessions/{sessionId}/report`

- 경로·쿼리·헤더: sessionId.

- Body: 없음.


**응답**

- 성공 (200): `{data:{report:{sessionId,projectId,baseRoundNo,askedCount,plannedCount,addedCount,endedEarly,topics,summary,questions,quality,limitations,versions}}}`.


topics는 주제별 SUFFICIENT/NEEDS_WORK/SKIPPED 결과, summary는 종합 설명, questions는 질문과 answerText를 포함한다. answerText는 qa_answers.transcript에서 읽는다. 카메라 전달력 평가 범위와 QA 세부 결과 스키마는 미정이다.


#### QA 세션 목록

**기능 개요:** 프로젝트의 QA 연습 이력을 조회한다.

**요청**

- Method: `GET`
- URL: `/projects/{projectId}/qa/sessions`

- 경로·쿼리·헤더: projectId, page?,size?.

- Body: 없음.


**응답**

- 성공 (200): 페이지 목록. 각 행은 sessionId,baseRoundNo,status,askedCount,createdAt.


#### QA 세션 삭제

**기능 개요:** 세션과 하위 답변·리포트의 삭제를 예약한다.

**요청**

- Method: `DELETE`
- URL: `/qa/sessions/{sessionId}`

- 경로·쿼리·헤더: sessionId.

- Body: 없음.


**응답**

- 성공 (204): 본문 없음.


#### QA 실시간 연결

**기능 개요:** 브라우저의 음성·카메라 입력을 FastAPI가 분석 서비스로 중계하고 질문을 돌려준다. 발표 영상 배치 분석의 네 항목 점수와 별도 흐름이다.

**요청**

- 방식: WebSocket 연결(REST JSON 요청과 다름).
- URL: `wss://{host}/api/v1/qa/sessions/{sessionId}/stream?ticket={wsTicket}`.
- 티켓은 단회용이며 만료·소유권·세션 상태를 검사한다. 세션당 연결 하나, 재연결 시 새 티켓 필요.

| 방향·이벤트 | 값과 의미 |
| --- | --- |
| client → config | audioCodec=음성 형식, videoMode=NONE/FRAME/STREAM, sampleRate=샘플링 속도 |
| client → audio_frame | seq=프레임 순서, data=음성 데이터 |
| client → video_frame | seq=순서, ts=시각, data=영상 데이터. 전송 방식·시각 기준은 미정 |
| client → answer_start / answer_end | questionId=답변하는 질문 ID |
| client → request_more / end_early | 추가 질문 요청 / 조기 종료 |
| server → question | questionId,topicId,text,followUp,followUpKind,evidenceAvailable,index,maxQuestions |
| server → plan_updated | plan=변경된 주제 계획 |
| server → wrap_up / ended | 마무리 이유·리포트 준비 여부 / 종료 상태 |
| server → status / error | 현재 상태·시각 / 오류 code,message,retryable |

**응답**

- 질문 메시지: followUp은 꼬리 질문 여부, followUpKind는 CLARIFY(명확히 묻기) 또는 DEEPEN(깊게 묻기), evidenceAvailable은 근거 조회 가능 여부다.
- 종료 코드: 4401 인증·티켓 만료, 4403 권한 없음, 1008 정책 위반, 1009 크기 초과, 1011 서버 오류.

답변 종료 뒤 LLM이 다음 질문 또는 꼬리 질문을 정한다. 실시간 점수 피드백은 보내지 않는다. 질문은 최대 10개, 다루지 않은 주제는 SKIPPED로 표시한다. 카메라 전송·녹화 보관·재연결 복원 범위·심사위원 화면 표현은 아직 미정이다. 위 표는 메시지 의미를 보존한 것으로 완전한 전송 스키마는 별도 확정해야 한다.


### A-6. 관리자와 운영


#### 운영 현황

**기능 개요:** 서비스 이용 현황을 조회한다.

**요청**

- Method: `GET`
- URL: `/admin/dashboard`

- 경로·쿼리·헤더: ADMIN 인증.

- Body: 없음.


**응답**

- 성공 (200): 이용 현황 객체. 기간·집계 지표의 정확한 스키마는 확정 필요.


#### 분석 작업 목록

**기능 개요:** 실패·진행 작업을 조회한다.

**요청**

- Method: `GET`
- URL: `/admin/analyses`

- 경로·쿼리·헤더: ADMIN 인증, status?,page?,size?.

- Body: 없음.


**응답**

- 성공 (200): 분석 작업의 페이지 목록. 영상·STT 전문은 포함하지 않음.


#### 루브릭 조회

**기능 개요:** 활성 단일 루브릭과 항목을 조회한다.

**요청**

- Method: `GET`
- URL: `/admin/rubric`

- 경로·쿼리·헤더: ADMIN 인증.

- Body: 없음.


**응답**

- 성공 (200): `{data:{rubric:객체,items:배열}}`. 버전·네 항목·규칙/LLM 세부 기준·가중치를 제공. 세부 계산 설정의 스키마는 B부 6장 참고.


#### 루브릭 버전 생성

**기능 개요:** 기존 기준을 덮어쓰지 않고 새 버전을 만든다.

**요청**

- Method: `PUT`
- URL: `/admin/rubric`

- 경로·쿼리·헤더: ADMIN 인증.

- Body: JSON: items[{itemKey,name,description,scoringGuide,weight}], memo?. 규칙 계산 설정·휴리스틱 세부 기준의 스키마는 확정 전.


**응답**

- 성공 (200): 새 루브릭 ID와 버전. 활성화 절차·응답 상태 코드는 확정 필요.


네 항목이 하나씩 존재하고 총점 가중치는 각각 0.25여야 한다. 감점값·휴리스틱 배정 등 계산 설정이 미정이면 실제 채점에 사용하지 않는다.


#### 사용자 목록

**기능 개요:** 사용자 계정 목록을 조회한다.

**요청**

- Method: `GET`
- URL: `/admin/users`

- 경로·쿼리·헤더: ADMIN 인증, status?,page?,size?.

- Body: 없음.


**응답**

- 성공 (200): 사용자 페이지 목록. 비밀번호 해시·토큰 제외.


#### 사용자 상태 변경

**기능 개요:** 사용자를 활성 또는 정지 상태로 변경한다.

**요청**

- Method: `PATCH`
- URL: `/admin/users/{userId}`

- 경로·쿼리·헤더: ADMIN 인증, userId.

- Body (JSON 예시):

```json
{
  "status": "SUSPENDED"
}
```

| 값 | 의미 |
| --- | --- |

| `status` | 자원의 상태. 요청 API별 허용값을 적용. |


**응답**

- 성공 (200): 아래 JSON 예시.


```json
{
  "data": {
    "user": {
      "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      "name": "홍길동",
      "email": "user@example.com",
      "role": "USER",
      "createdAt": "2026-11-10T00:00:00Z",
      "status": "SUSPENDED"
    }
  }
}
```


status는 ACTIVE 또는 SUSPENDED. 예시의 user.status는 변경된 상태다. 운영 응답의 전체 필드 목록은 최종 확정 필요.


#### 생존 확인

**기능 개요:** 프로세스가 실행 중인지 확인한다.

**요청**

- Method: `GET`
- URL: `/healthz`

- Body: 없음.


**응답**

- 성공 (200): 최소 생존 상태. `/api/v1` 밖에 둔다.


#### 준비 상태 확인

**기능 개요:** DB·분석 서비스 등 의존성 준비 상태를 검사한다.

**요청**

- Method: `GET`
- URL: `/readyz`

- 경로·쿼리·헤더: 내부망 운영 경로. `/api/v1` 밖.

- Body: 없음.


**응답**

- 성공 (200): 준비 상태. 구체 오류 응답 형식은 배포 계약에서 확정한다.


### A-7. ERD 및 미확정 계약


ERD v10의 report_scores는 네 점수·score_source·breakdown을 저장하고 rubric_items.scoring_config는 계산 설정의 위치를 정의한다. 미확정 숫자와 JSON 내부 스키마는 ACTIVE 전 확정해야 한다. 총점은 동일 가중 평균으로 맞춘다. 영상 500 MiB·30분의 DB 저장·재생 성능, 삭제·보관 기간, 루브릭 배포·활성화 방식, 각 채점 계산식은 검증·확정 전이다. 본 문서는 기존 코드를 변경하거나 서버 연동을 검증한 결과가 아니다.


## B. AI 내부 API와 채점 파이프라인



이 문서는 **사용자 API 서버(`api`)와 분석 서버(`analysis-api`)가 주고받는 요청**을 설명한다. 사용자가 영상을 올리면 `api`가 DB에 저장하고 분석 작업을 맡긴다. `analysis-api`는 영상에서 STT·음향 분석으로 발화속도·유창성의 특징을 추출하고, Vision 모델로 제스처·정면 응시 관찰값을 JSON으로 만든다. 루브릭에서 수치화 가능한 기준은 규칙으로 채점하고, 명시된 휴리스틱 세부 기준만 LLM에 맡긴다. 네 항목 점수와 동일 가중 평균 총점·근거·코칭을 만들면 `api`가 결과를 검증해 사용자에게 공개한다. 아래 경로는 서버 간 전용이며 브라우저에서 직접 호출하지 않는다.

| 먼저 알아둘 값 | 뜻 |
| --- | --- |
| `analysisId` / `roundId` | 사용자의 발표 연습 **회차 ID**. 같은 회차를 재분석해도 유지된다. 현재 계약에서는 두 값이 같다. |
| `jobId` | AI 분석을 **한 번 실행한 작업 ID**. 재시도하면 새로 발급한다. |
| `attempt` | 같은 회차를 분석한 **시도 순서**. 첫 실행은 1, 자동 재시도는 2다. |
| `modelVersion` | 실행에 사용한 AI 코드·모델 묶음의 버전. |
| `rubricVersion` | 항목별 채점 기준과 가중치의 버전. 작업 시작 시 고정한다. |
| `status` / `stage` | `status`는 외부에 보여줄 큰 진행 상태, `stage`는 AI 내부의 현재 처리 단계다. |
| `progress` | 작업 진행률(0~100). 완료 시 100이며 처리 중에는 낮아지지 않는다. |
| `eventId` | 같은 콜백이 다시 와도 한 번만 처리하기 위한 이벤트 ID. |
| `reportKey` | 분석 서버가 만든 **최종 결과 JSON**의 위치. 원본 영상이나 STT 전사 파일의 위치가 아니다. |
| `?` / `null` | `?`는 필드가 생략될 수 있다는 뜻. `null`은 필드는 있지만 값이 없다는 뜻이다. |

### B-1. 분석 범위

평가 항목은 **발화속도(SPEECH_RATE), 유창성(FLUENCY), 제스처(GESTURE), 시선(GAZE)** 네 개로 고정하며 각 0~100 정수다. 총점은 네 항목을 같은 비중으로 평균한다. 발화속도 단위·목표 구간, 유창성의 규칙/LLM 합산 비율, 제스처 감점값·지속시간 기준은 미확정이다. 미확정 기준에 임의의 숫자를 넣어 실제 점수로 공개하지 않는다.

정량 기준은 규칙 계산으로 확정하고 LLM이 변경하지 못한다. LLM은 루브릭에 배정된 휴리스틱 세부 기준만 평가한다. 서버가 그 결과를 검증·합산한 뒤, 별도 피드백 단계가 점수를 바꾸지 않고 설명·코칭·예상 질문을 생성한다. 발표 주제 적합성·논리성·PDF 대조는 채점하지 않으며 `contentCheck=null`을 유지한다. 물건 사용의 적절성 판단은 제스처 세부 기준에 한정하고 사실·내용 평가로 확대하지 않는다.

원본 발표 영상 바이트는 PostgreSQL `uploads.video_data`, STT 전문은 `stt_utterances.text`의 순서 있는 발화 행, 발화 시각은 `start_sec/end_sec`에 저장한다. `job_id`로 재시도별 전사 결과를 구분한다. STT 전사는 지정된 유창성 휴리스틱 기준과 예상 질문 생성에 필요한 데이터로 제공한다. 전사 내용을 모델의 실행 지시로 취급하지 않는다. 프레임·음향 중간 산출물은 DB 영구 저장 대상이 아니다.

### B-2. 서비스 경계와 작업 흐름

`api`가 영상·상태·STT 저장의 DB 소유자다. `analysis-api`는 직접 DB를 수정하지 않고 서비스 인증된 내부 API를 사용한다.

1. `api`는 사용자 직접 업로드를 완료·검증하고 회차와 작업을 기록한다.
2. `api → analysis-api`: `POST /analysis/jobs`로 jobId, roundId, attempt, modelVersion, rubricVersion을 접수한다.
3. `analysis-api → api`: `GET /internal/analysis-jobs/{jobId}/video`의 응답 스트림으로 영상 바이트를 읽는다. 접근은 현재 job·회차 상태·서비스 자격 증명을 검사한다.
4. 전처리 뒤 AUDIO(STT·음향)와 VIDEO(자세·제스처·얼굴)를 병렬 실행한다. STT 결과는 발화 단위로 `POST /internal/analysis-jobs/{jobId}/utterances`에 전달해 저장한다.
5. ALIGN → RUBRIC_RULE → RUBRIC_HEURISTIC → SCORE_AGGREGATE → FEEDBACK을 실행한다. 결과는 최종 JSON으로 저장하고 콜백한다. `api`가 검증·커밋한 뒤 DONE을 공개한다.

내부 영상 GET은 브라우저에 공개하지 않는다. 전송 중 메모리에 영상 전체를 적재하지 않도록 스트리밍하며, 처리 완료 후 임시 파일을 정리한다. 500 MiB DB 읽기·쓰기와 백업·복구 비용은 실제로 측정해야 한다.

### B-3. 분석 서버가 받는 API

#### B-3-1. 분석 작업 접수

**기능 개요:** 사용자 API 서버가 “이 회차의 영상을 분석해 달라”고 분석 서버에 요청한다. 분석은 오래 걸리므로 이 API는 완료 결과 대신 접수 결과를 돌려준다.

**요청**

- Method: `POST`
- URL: `/analysis/jobs`
- Body (JSON):

```json
{
  "jobId": "11111111-1111-4111-8111-111111111111",
  "analysisId": "22222222-2222-4222-8222-222222222222",
  "attempt": 1,
  "modelVersion": "m1",
  "rubricVersion": "r1",
  "targetMinutes": 10
}
```

| 값 | 의미 |
| --- | --- |
| `jobId` | 이번 **한 번의 분석 실행** ID. 재시도할 때 새 ID를 쓴다. |
| `analysisId` | 분석할 **발표 회차** ID. 현재 계약에서는 `rounds.id`와 같다. |
| `attempt` | 이 회차의 분석 시도 순서. 최초 1, 자동 재시도 2. |
| `modelVersion` | 사용할 AI 코드·모델 묶음의 버전. |
| `rubricVersion` | 적용할 채점 기준과 항목 가중치의 버전. |
| `targetMinutes` | 목표 발표 시간(분). 선택값이며 생략하면 0, 0은 목표 시간 없음. |

**응답**

- 성공 (202): `{"jobId":"11111111-1111-4111-8111-111111111111","status":"QUEUED","attempt":1}` — 작업이 **대기열에 등록됨**. 분석 완료를 뜻하지 않는다.
- 실패 (409): `JOB_ID_CONFLICT` — 같은 jobId로 다른 요청 내용을 보냄.
- 실패 (422): `INVALID_SCORING_POLICY` — 지정한 루브릭 버전을 사용할 수 없음.

영상은 `analysisId`에 연결된 DB 저장본에서 읽는다. 루브릭 버전은 작업 시작 시 고정한다. 같은 jobId·같은 본문을 다시 보내면 기존 접수 결과를 반환한다. 분석 서비스가 루브릭 항목·채점 규칙을 가져오는 방식은 구현 전에 정해야 한다. 미디어 내용 검증에 실패하면 접수 후 작업 상태를 FAILED로 보고한다.

#### B-3-2. 분석 상태 조회

**기능 개요:** 사용자 API 서버가 분석 진행 상태를 확인한다. 완료 콜백을 놓쳤을 때도 이 API로 결과를 복구한다.

**요청**

- Method: `GET`
- URL: `/analysis/jobs/{jobId}` — `{jobId}`는 조회할 분석 실행 ID.
- Body: 없음.

**응답**

- 성공 (200), 진행 중 예시:

```json
{
  "jobId": "11111111-1111-4111-8111-111111111111",
  "analysisId": "22222222-2222-4222-8222-222222222222",
  "attempt": 1,
  "status": "ANALYZING",
  "stage": "AUDIO",
  "progress": 43
}
```

| 값 | 의미 |
| --- | --- |
| `status` | 화면에 표시할 큰 상태: QUEUED, EXTRACTING, ANALYZING, SCORING, DONE, FAILED. |
| `stage` | 실제 내부 처리 단계. 위 예시는 음성 분석 중이라는 뜻. |
| `progress` | 진행률 0~100. 완료 시 100. |
| `failure` | FAILED일 때만 있는 `{code,retryable}`. 오류 종류와 재시도 가능 여부. |
| `result` | DONE일 때만 있는 `{reportKey}`. 최종 결과 JSON의 저장 위치. |

- 실패 (404): 해당 jobId가 없음.

사용자 API 서버는 결과를 반영하기 전에 이 작업이 현재 attempt인지, 회차가 삭제되지 않았는지 확인한다.

#### B-3-3. 분석 취소 요청

**기능 개요:** 사용자가 회차를 삭제하는 등의 이유로 진행 중인 분석을 중지하도록 요청한다.

**요청**

- Method: `POST`
- URL: `/analysis/jobs/{jobId}/cancel`
- Body: 없음.

**응답**

- 성공 (202): 취소 **요청을 받음**. 실행이 실제로 중단됐다는 뜻은 아니다. 같은 요청을 다시 보내도 중복 취소하지 않는다.
- 실패 (404): 해당 jobId가 없음.

취소와 완료가 동시에 발생하면 사용자 API 서버가 삭제 여부와 현재 작업을 확인해 늦은 결과가 공개되지 않게 한다. 내부 CANCELLED는 사용자 화면의 상태 목록에 추가하지 않는다.

### B-4. 사용자 API 서버가 받는 내부 API

#### B-4-1. 분석할 영상 읽기

**기능 개요:** 분석 서버가 PostgreSQL에 저장된 발표 영상을 사용자 API 서버에서 읽는다. 이 경로는 브라우저에서 사용할 수 없다.

**요청**

- Method: `GET`
- URL: `/internal/analysis-jobs/{jobId}/video`
- 인증: 서버 간 서비스 인증. Body는 없음.

**응답**

- 성공 (200): 영상 **바이너리 스트림**. JSON이 아니다. `Content-Type`은 영상 형식, `Content-Length`는 바이트 크기다.
- 실패 (404): 작업이 없거나 삭제된 회차에 속함.
- 실패 (409): 영상 업로드가 아직 완료되지 않음.

서버는 현재 작업·회차·삭제 여부를 검사한다. 영상 전체를 한꺼번에 메모리에 올리지 않고 전송하도록 구현·검증한다. 영상 바이트를 로그나 오류 메시지에 넣지 않는다.

#### B-4-2. STT 전사와 시각 저장

**기능 개요:** 분석 서버가 음성을 글로 바꾼 결과를 **발화 한 문장씩** DB에 저장하도록 사용자 API 서버에 전달한다.

**요청**

- Method: `POST`
- URL: `/internal/analysis-jobs/{jobId}/utterances`
- Body (JSON):

```json
{
  "attempt": 1,
  "utterances": [
    {"seq": 1, "startSec": 0.5, "endSec": 3.2, "text": "안녕하세요. 발표를 시작하겠습니다."},
    {"seq": 2, "startSec": 3.4, "endSec": 6.1, "text": "오늘은 서비스 계획을 설명하겠습니다."}
  ]
}
```

| 값 | 의미 |
| --- | --- |
| `attempt` | 이 전사가 속한 분석 시도. URL의 jobId와 일치해야 한다. |
| `utterances` | 시간 순서대로 나열한 발화 목록. 이 행들을 순서대로 합치면 해당 시도의 전사 전문이 된다. |
| `seq` | 발화 순서. 1부터 연속 증가한다. |
| `startSec` / `endSec` | **영상 시작부터 지난 초**로 표현한 발화 시작·끝. 영상 길이 안에 있어야 한다. |
| `text` | 해당 구간에서 인식한 말. |

**응답**

- 성공 (204): 저장 완료. 응답 본문 없음. 같은 jobId·seq·같은 내용의 재전송도 성공한다.
- 실패 (409): 같은 순서에 다른 내용을 보냈거나 현재 작업 시도와 맞지 않음.
- 실패 (400): 순서·시각 범위 등 입력이 잘못됨.

`0 ≤ startSec < endSec ≤ durationSec`를 검사한다. STT 단계의 전사 행은 해당 작업에 원자적으로 저장하고 분석 중에는 사용자에게 공개하지 않는다. 삭제된 회차나 오래된 작업의 전사는 저장하지 않으며, 전사 전문을 로그·콜백에 싣지 않는다.

#### B-4-3. 분석 진행·완료·실패 알림

**기능 개요:** 분석 서버가 작업 상태가 바뀔 때 사용자 API 서버에 알린다. 완료 시에는 최종 리포트 JSON의 위치만 전달한다.

**요청**

- Method: `POST`
- URL: `/internal/analysis-jobs/{jobId}/events`
- 진행 중 Body (JSON) 예시:

```json
{
  "eventId": "33333333-3333-4333-8333-333333333333",
  "analysisId": "22222222-2222-4222-8222-222222222222",
  "attempt": 1,
  "status": "ANALYZING",
  "stage": "AUDIO",
  "progress": 43,
  "occurredAt": "2026-11-09T06:00:00Z"
}
```

| 값 | 의미 |
| --- | --- |
| `eventId` | 이 알림의 고유 ID. 재전송돼도 한 번만 처리한다. |
| `analysisId` / `attempt` | 어느 회차의 몇 번째 분석인지 확인한다. |
| `status` / `stage` / `progress` | 큰 상태, 내부 단계, 진행률. |
| `occurredAt` | 분석 서버에서 이 이벤트가 발생한 UTC 시각. |
| `result` | DONE일 때만 `{reportKey}`. 최종 결과 JSON 위치. |
| `failure` | FAILED일 때만 `{code,retryable}`. 실패 원인과 재시도 가능 여부. |

**응답**

- 성공 (204): 이벤트 처리 완료. 같은 eventId, 오래된 attempt, 삭제된 회차의 알림은 무해하게 무시한다.
- 실패 (422): 결과 형식·점수·시간 범위 등 검증 오류.
- 실패 (5xx): 일시적인 서버 장애. 분석 서버가 같은 eventId로 재전송한다.

DONE 이벤트는 최종 JSON을 검증해 DB에 저장한 뒤에만 성공 처리한다. 원본 영상과 STT 전문은 콜백 본문에 넣지 않는다.

### B-5. 영상 분석의 실제 처리 단계

아래 `stage`는 **HTTP API가 아니라 한 분석 작업 안에서 진행되는 순서**다. 음성과 영상 분석은 동시에 실행할 수 있고, 두 결과가 준비되면 같은 시각 기준으로 결합한다.

| 순서·stage | 무엇을 입력받아 하는가 | 나오는 값과 의미 | 화면에 보이는 status |
| --- | --- | --- | --- |
| 1. QUEUED | 분석할 회차를 대기열에 등록 | 아직 분석 결과 없음 | QUEUED |
| 2. PREPROCESS | DB 영상을 읽고 형식·길이를 검사 | 추출한 오디오, 샘플링한 프레임, 영상 시작을 0초로 하는 시각 기준 | EXTRACTING |
| 3. AUDIO / VIDEO | 오디오는 STT·음향 분석, 프레임은 YOLO 계열 모델 조합으로 분석 | `utterances`: 발화 문장·시각, 음향 창: 속도·휴지·음량·높낮이, 영상 창: 자세·동작·얼굴 가시성 등 | ANALYZING |
| 4. ALIGN | 음성과 영상의 관찰값을 같은 시각에 맞춤 | 시간 구간마다 함께 나타난 특징과 측정 불가 신호 | ANALYZING |
| 5. RUBRIC_RULE | 루브릭의 수치 기준을 특징 JSON에 적용 | 규칙 점수·감점·관찰 근거. LLM 수정 금지 | SCORING |
| 6. RUBRIC_HEURISTIC | 지정된 휴리스틱 기준만 LLM에 전달 | 기준별 판단·근거. 임의 점수 조정 금지 | SCORING |
| 7. SCORE_AGGREGATE | 서버가 기준별 결과를 검증·합산 | 네 항목 점수와 동일 가중 평균 총점 | SCORING |
| 8. FEEDBACK | 확정 점수·근거와 전사를 LLM에 전달 | 강점·개선점·코칭·예상 질문. 숫자 점수는 변경하지 않음 | SCORING |
| 9. DONE / FAILED | 결과를 검증·저장하거나 실패 원인을 기록 | DONE은 공개 가능한 리포트, FAILED는 오류 코드 | DONE / FAILED |

STT 내부 출력은 `utterances[{seq,startSec,endSec,text}]`, 음향 출력은 발화 속도·휴지·음량·높낮이 등의 시간 창이다. 영상 출력은 자세·제스처·얼굴 가시성·방향 등의 시간 창이다. YOLO 모델별 실제 측정 가능 항목을 확정하고, 지원하지 않는 지표는 계약에서 제거한다. 관찰 불가는 null과 사유로 표현하며 0점으로 대체하지 않는다. 얼굴 관찰로 감정·성격·자신감을 직접 측정했다고 주장하지 않는다.

### B-6. 특징 JSON과 네 가지 채점 계약

아래 단계는 **worker 내부 함수/JSON 계약**이다. 별도 HTTP API를 추가하지 않는다. 서버 간 HTTP 메서드·경로는 3~4장을 그대로 사용한다. 예시는 구조 설명용이며 수치는 실측 결과나 확정된 채점 기준이 아니다. `null`은 측정값이 없음을 뜻하며 0점이 아니다.

#### B-6-1. 음성·Vision 특징 추출

**기능 개요:** 같은 영상 시간축에서 STT 전사·음향 특징과 제스처·정면 응시 관찰값을 추출한다.

**요청**

- 호출: worker 내부 STT/ACOUSTIC/VISION 모듈.
- 입력: 원본 영상에서 추출한 오디오·샘플링 프레임, 고정된 모델 설정, jobId.
- 출력 형식: JSON. 아래는 핵심 필드 예시다.

```json
{
  "jobId": "11111111-1111-4111-8111-111111111111",
  "audio": {
    "rate": {"value": null, "unit": null, "durationBasis": null},
    "fluency": {"pauseRatio": null, "fillerCount": null, "repetitionCount": null},
    "coverageRatio": 0.9
  },
  "vision": {
    "gaze": {"observableSeconds": 80, "frontFacingSeconds": 60, "frontFacingRatio": 0.75},
    "gestureEvents": [
      {"eventId": "gesture-1", "kind": "FACE_OCCLUSION", "startSec": 12.0, "endSec": 14.5, "confidence": 0.9}
    ],
    "handObservableSeconds": 70,
    "handStillSeconds": 20
  },
  "limitations": []
}
```

| 값 | 의미·주의 |
| --- | --- |
| `audio.rate.value/unit` | 발화속도 수치와 단위. 음절/분·어절/분 등 **아직 미정**. 단위가 다른 값을 비교하지 않는다. |
| `durationBasis` | 전체 발표 시간인지 실제 발화 시간인지 등 속도의 시간 분모. 아직 미정. |
| `pauseRatio` | 정해진 분석 시간 중 휴지 비율. 휴지 길이 기준·분모는 루브릭 설정으로 확정해야 한다. |
| `fillerCount/repetitionCount` | 필러·반복어의 관찰 건수. 인식 오류와 의도적 반복을 구분해야 한다. |
| `coverageRatio` | 음성 지표를 신뢰할 수 있게 관찰한 시간의 비율. 단순 STT 문장 수와 다르다. |
| `observableSeconds` | 정면 응시 여부를 실제로 측정할 수 있었던 시간. 가림·미검출은 제외. |
| `frontFacingSeconds/Ratio` | 측정 가능한 시간 중 정면 응시 시간과 비율. 예시는 60/80=0.75다. |
| `gestureEvents` | 시작·끝이 있는 행동 사건. 같은 행동이 연속 프레임에 나타나도 매 프레임 별도 감점하지 않는다. |
| `confidence` | 모델이 반환하거나 정의된 절차로 계산한 신뢰도. 근거 없이 만들어 넣지 않는다. |
| `handObservableSeconds/handStillSeconds` | 손이 보인 시간과 그중 움직임이 없었던 시간. 손이 안 보이는 시간을 정지로 처리하지 않는다. |

**결과**

- 성공: 측정값과 구간·품질 정보를 다음 단계에 전달한다. STT 발화와 시각은 4-2의 API로 DB에 저장한다.
- 측정 불가: 해당 값은 null, 원인은 limitations에 기록한다. 필수 지표가 부족하면 점수를 생성하지 않는다.

STT 발화 텍스트만으로 음향 휴지·머뭇거림을 모두 얻는다고 가정하지 않는다. 필요하면 오디오의 발화 구간 검출·음향 분석을 함께 사용한다. 선택한 YOLO 조합이 실제 눈의 시선까지 제공하는지 검증해야 한다. 얼굴 방향만 제공하면 이를 실제 시선으로 단정하지 않고 ‘정면 방향 추정’과 그 한계를 표시한다.

#### B-6-2. 루브릭의 1차 규칙 채점

**기능 개요:** 직접 계산할 수 있는 수치를 고정된 규칙에 대입한다. 휴리스틱 기준의 점수는 이 단계에서 임의로 채우지 않는다.

**요청**

- 호출: worker 내부 `RUBRIC_RULE`.
- 입력: 특징 JSON, 루브릭 버전과 기준별 계산 설정.

| 항목 키 | 평가 방식 | 확정된 내용 | 아직 정할 내용 |
| --- | --- | --- | --- |
| `SPEECH_RATE` | 규칙 | 0~100점으로 환산 | 속도 단위·시간 분모·적정 구간·환산식 |
| `FLUENCY` | 규칙 + 지정된 LLM 기준 | 관찰 지표와 휴리스틱 평가를 구분 | 세부 기준·가중치·규칙/LLM 비율 |
| `GESTURE` | 100점에서 감점 | 아래 세 행동을 평가 대상으로 사용 | 행동별 감점값·발동 지속시간·중복/상한 규칙 |
| `GAZE` | 규칙 | 측정 가능한 시간 중 정면 응시 비율 | 정면 판정 기준·최소 유효 시간·비율→점수 환산식 |

제스처 감점 대상:

| 기준 키 | 사용자 지정 행동 | 관찰과 판단의 경계 |
| --- | --- | --- |
| `FACE_OCCLUSION` | 손이나 물건이 얼굴을 가리는 행동 | 실제 가림 구간을 관찰. 탐지 실패 자체를 가림 행동으로 판단하지 않음. |
| `HAND_STILLNESS` | 아예 손을 움직이지 않는 행동 | 손이 보이는 구간에서 일정 시간 이상 정지했는지 판정. ‘아예’의 시간 기준은 미정. |
| `UNRELATED_OBJECT_TOUCH` | 발표와 상관없는 물건을 만지는 행동 | 물건 접촉과 발표와의 관련성 판단을 구분. 관련성을 판단할 문맥이 없으면 임의 감점 금지. |

제스처 점수 구조는 `max(0, 100 - 중복 제거된 감점 합계)`다. 같은 사건의 프레임별 반복 감점은 금지한다. 사용자가 승인하지 않은 행동을 감점 목록에 추가하지 않는다. 정면 응시 비율은 `frontFacingSeconds / observableSeconds`이고 분모가 0이면 null이다. 이 비율에 100을 곱해 바로 점수로 쓸지는 아직 확정되지 않았다.

**결과**

- 성공: 규칙 세부 점수·감점 내역·관찰 근거를 생성한다.
- 실패: 필요한 계산 설정이 없으면 `UNSCORABLE_RUBRIC_ITEM`, 필수 측정값이 없으면 `INSUFFICIENT_REQUIRED_SIGNAL`. 임의 기본 점수로 통과시키지 않는다.

#### B-6-3. LLM의 휴리스틱 기준 평가

**기능 개요:** 수치 규칙으로 해결되지 않는 **루브릭에 명시된 세부 기준만** LLM이 판단한다. 규칙 점수를 재작성하거나 네 항목 전체를 다시 채점하지 않는다.

**요청**

- 호출: worker 내부 `RUBRIC_HEURISTIC`.
- Body에 해당하는 내부 JSON 예시:

```json
{
  "rubricVersion": "r1",
  "criteria": [
    {"criterionKey": "UNRELATED_OBJECT_TOUCH", "itemKey": "GESTURE", "allowedVerdicts": ["APPLIES", "DOES_NOT_APPLY", "UNDETERMINED"]}
  ],
  "evidenceRefs": ["gesture-1"],
  "context": null
}
```

| 값 | 의미 |
| --- | --- |
| `criteria` | 이번 LLM 호출에 배정된 세부 기준. 활성 루브릭에서 가져오며 예시의 목록 자체가 확정 배정은 아님. |
| `criterionKey/itemKey` | 세부 평가 기준과 그 기준이 속한 네 항목 중 하나. |
| `allowedVerdicts` | 적용·비적용·판단 불가 중 허용된 판단. |
| `evidenceRefs` | 실제 특징 JSON·전사 구간으로 해석 가능한 참조. 단순 사건 ID만으로 뜻이 전달되지 않으므로 해당 관찰 내용을 함께 제공해야 함. |
| `context` | 판단에 필요한 발표 상황·허용 물건 정보 등. 확보 방법은 미정이며 없으면 null. |

**결과**

```json
{
  "criterionKey": "UNRELATED_OBJECT_TOUCH",
  "verdict": "UNDETERMINED",
  "reason": "관찰된 물건이 발표에 필요한지 판단할 문맥이 없습니다.",
  "evidenceRefs": ["gesture-1"]
}
```

LLM은 행동을 관찰하지 않았는데 추론으로 만들어내거나 관련성 판단 불가를 곧바로 감점으로 바꾸면 안 된다. 숫자 세부 점수가 필요한 유창성 기준은 점수 앵커·비율을 확정한 뒤 별도 스키마를 정의한다. LLM에 임의로 비율을 결정하게 하지 않는다. 하나의 세부 기준은 RULE 또는 LLM 중 한쪽이 담당하며 같은 행동을 중복 채점하지 않는다.

필수 휴리스틱 판단이 실패하거나 UNDETERMINED이면 점수 산출 실패로 처리한다. 선택 기준이 UNDETERMINED이면 점수에서 제외하고 limitations에 기록한다. 이 경우의 LLM 실패는 설명 문장만 대체할 수 있는 FEEDBACK 실패와 다르다. 선택 기준 제외 후 재가중 방식은 활성 루브릭 설정에 명시해야 하며, 미정 상태에서는 정상 점수로 공개하지 않는다.

#### B-6-4. 네 항목·총점 합산 및 최종 리포트

**기능 개요:** 서버가 규칙과 허용된 LLM 판단을 합쳐 항목별 최종 점수를 만들고, 네 항목을 동일 가중 평균한다. 아래 숫자는 형식 설명용이다.

**요청**

- 호출: worker 내부 `SCORE_AGGREGATE`, 이후 `FEEDBACK`.
- 입력: 규칙 결과·검증된 휴리스틱 결과·루브릭의 확정 합산식.
- `FEEDBACK` 입력에는 확정 점수·근거와 예상 질문용 전사를 전달한다. 이 단계는 점수를 변경할 수 없다.

**결과(JSON 예시)**

```json
{
  "scores": [
    {"itemKey": "SPEECH_RATE", "score": 80, "scoreSource": "RULE"},
    {"itemKey": "FLUENCY", "score": 70, "scoreSource": "HYBRID"},
    {"itemKey": "GESTURE", "score": 90, "scoreSource": "HYBRID"},
    {"itemKey": "GAZE", "score": 76, "scoreSource": "RULE"}
  ],
  "totalScore": 79,
  "coaching": {"strengths": [], "improvements": [], "actions": []},
  "contentCheck": null,
  "quality": "NORMAL",
  "limitations": []
}
```

| 값 | 의미 |
| --- | --- |
| `itemKey` | 네 항목의 고정 식별자. 이름·순서와 무관하게 사용한다. |
| `score` | 해당 항목의 확정 점수(0~100 정수). |
| `scoreSource` | RULE=규칙만, LLM=지정된 LLM 기준만, HYBRID=둘을 합산. 실제 경로를 기록하며 예시처럼 고정하지 않는다. |
| `totalScore` | 네 확정 항목 점수의 평균. 예시는 (80+70+90+76)/4=79. |
| `coaching` | 강점·개선점·실천 조언. |
| `quality/limitations` | NORMAL 또는 DEGRADED와 관찰·생성 제한 목록. 점수 누락을 NORMAL로 숨기지 않는다. |

위 예시는 점수 부분을 설명한 것으로 전체 DONE 응답은 아니다. 실제 결과는 기존 `analysisId, jobId, versions, rubricItemId, evidence, timeline, segments, expectedQuestions`도 포함해야 한다. `scores`는 네 항목이 정확히 하나씩 있어야 하고, 점수 하나라도 미확정이면 총점을 산출하지 않는다. 평균의 .5 반올림 규칙은 명세 확정 때 고정해야 한다. 휴리스틱 계산 설정이 미정인 현재는 예시 점수를 검증된 성적으로 제공하지 않는다.

#### B-6-5. ERD v10과의 대응 및 남은 확정 사항

| 데이터 | 현재 저장 위치 | 판단 |
| --- | --- | --- |
| 원본 영상·STT 전사·발화 시각 | uploads.video_data, stt_utterances | 기존 구조로 가능 |
| 네 항목의 최종 점수 | rubric_items.item_key + report_scores.score | 가능. 네 키의 중복 방지·항목 집합 검증 필요 |
| 총점 | reports.total_score | 네 항목 동일 가중 평균으로 ERD v10 주석 수정 |
| 최종 시간축 특징·관찰 근거 | reports.timeline, report_scores.evidence | JSON으로 가능하지만 스키마가 필요함. 모든 프레임을 DB에 저장할 필요는 없음 |
| 규칙/LLM 담당 경로와 세부 합산 내역 | report_scores.score_source / breakdown | ERD v10에 반영. breakdown 내부 JSON 스키마는 미정 |
| 감점값·지속시간·유창성 비율·측정 품질 하한 | rubric_items.scoring_config | 필드 구조의 위치만 반영. 수치·계산식은 확정 전이며 ACTIVE에서는 누락 불가 |
| LLM 코칭 | reports.coaching | 가능. 코칭 단계의 숫자 점수 변경 금지 주석은 그대로 유효 |

ERD v10에 저장 컬럼과 활성 전 검증 조건을 반영했다. 감점값·혼합 비율·환산식이 확정되기 전에는 실제 점수를 공개하지 않는다. 사용자 API의 표시 계약은 본 문서 A부에 반영했다. 사용자 리포트는 본 문서 A부의 네 항목·scoreSource 계약을 따른다.

### B-7. 실패·보안·미확정 사항

입력·정책 오류는 자동 재시도하지 않는다. 일시적 STT·모델·DB 장애는 `api`가 전체 작업 자동 재시도를 최대 1회 지시한다. 새 attempt는 새 jobId이며 재시도 시 기존 전사 행은 별도 job에 남아 공개되지 않는다. 사용자 수동 재시도는 자동 1회 한도와 별도로 검토한다. 동시 배치 분석은 최대 3개, 초과는 QUEUED다.

영상·음성·STT 전문·QA 답변을 애플리케이션 로그나 콜백에 기록하지 않는다. 사용자 또는 회차 삭제 시 DB 영상·전사·리포트의 실제 삭제 절차와 보존 기간을 정해야 한다. 영상 바이트를 PostgreSQL에 두므로 500 MiB·30분 파일에 대한 요청 제한, 스트리밍, 트랜잭션 지속 시간, 저장 용량, 백업·복구 시간을 운영 검증한다.

**확정 필요:** 발화속도 단위·분모·적정 구간, 유창성 세부 기준·규칙/LLM 비율, 세 제스처 행동의 감점값·지속시간·중복 처리, 정면 판정·비율 환산식·최소 유효 시간, 점수 반올림, 루브릭 전달 방식, YOLO 조합의 실제 출력, STT 품질 하한, 전사·영상 보존 기간, DB 대용량 영상의 성능. 점수 품질은 별도 사람 평가 데이터로 검증한다.
