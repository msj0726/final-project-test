# 공통 계약

정본은 사용자 API v3.5 / AI API v1.4 / ERD v10. [적용 기준](../docs/SPEC_ALIGNMENT.md)과 [개발용 결정·미정 정책](../docs/CONTRACT_DECISIONS.md)을 먼저 읽는다.

- models.py: 공통 envelope·오류·프로젝트·업로드 요청. HTTP camelCase, Python snake_case.
- analysis.py: UUID 작업·이벤트·STT·Report, 시간/버전/항목 집합 검증.
- schemas/: `uv run python -m contracts.export`로 생성한다. 프론트·다른 언어도 이 스키마를 기준으로 샘플을 읽는다.
- examples/: 계약 형식을 검증하는 합성 JSON 예시. 실제 영상·모델 출력이 아니다.
- endpoint-catalog.json: 계획된 제품 경로와 현재 구현 상태 목록. 운영 앱의 실제 경로는 OpenAPI에서 확인한다.

analysisId=round UUID는 재시도에도 유지하고 jobId는 새 attempt마다 새 UUID다. STT와 Report의 모든 시간은 영상 0초 기준이다. 선언적 Schema만으로 영상 길이·현재 버전·삭제 여부를 검증할 수 없으므로 api의 문맥 검증을 함께 수행한다.

PATCH는 `model_dump(exclude_unset=True, by_alias=False)`로 생략값을 제외하고 DB 필드로 변환한다. 요청용 선택 필드의 None 기본값은 생략 표시이며 명시적 null 허용과 다르다. 이 요청 모델을 응답으로 재사용하지 않는다.

중첩 evidence/timeline/LLM 배열은 원본 미정 부분을 계약 초안으로 구체화했다. 실제 신호·채점식·루브릭 전달 방식이 승인되면 소비 팀과 함께 버전을 갱신한다. JSON 예시가 실제 평가 결과나 최종 정책을 뜻하지는 않는다.
