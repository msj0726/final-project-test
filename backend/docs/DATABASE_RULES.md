# ERD v10 적용 메모

정본: [erd-v10.dbml](specs/erd-v10.dbml). 아직 ORM·migration·DB 연결은 구현하지 않았다.

- projects.rubric_id 및 analysis_jobs.rubric_id가 단일 불변 루브릭을 참조한다. scoring_policies, rubric kind, common_score/expert_score는 없다.
- uploads.video_data bytea에 영상 한 번만 저장한다. rounds는 upload_id로 참조한다. uploads.storage_key/rounds.video_key는 없다. materials.storage_key는 후속 PDF 기능의 별도 필드다.
- stt_utterances는 (job_id,seq) UNIQUE. 영상 기준 시각 범위와 seq 연속성을 검사한다. 재시도별 jobId를 분리하고 현재 DONE의 STT만 공개한다.
- reports는 round_id와 job_id 각각 UNIQUE. report_scores는 (report_id,rubric_item_id) UNIQUE. STT 검증·Report/항목/구간 저장·DONE 변경을 한 트랜잭션 경계로 만든다.
- 회원가입 users+agreements, 업로드 준비 uploads+rounds를 각각 원자적으로 생성한다. rounds의 (project_id,round_no), upload_id 고유 제약을 유지한다.
- idempotency_keys PK는 (user_id,key). endpoint와 본문 해시가 다르면 충돌이다. 진행 중 예약/동시 요청은 현재 ERD만으로 충분한지 구현 때 점검한다.
- v10의 duration_sec/started_at not null은 준비·대기 상태와 값 확정 시점 조정이 필요하다. 거짓 길이/시각을 실제 측정값처럼 기록하지 않는다.
- rubrics.status는 DRAFT/ACTIVE다. ACTIVE는 서비스당 하나만 허용하도록 PostgreSQL 부분 고유 인덱스와 상태 전이 트랜잭션을 설계한다. 활성 버전은 불변으로 다루고 변경 시 새 버전을 만든다.
- 500 MiB는 int 범위 이내이나 bytea ORM 단순 조회로 영상 전체가 메모리에 올라갈 수 있다. 수신 제한·실제 해시·미디어 검증·부분 Range 읽기·트랜잭션 시간·메모리·백업 비용을 실측한다. 계약 예시 검증은 이 실측을 대신하지 않는다.
- Range 요청의 200/206/416, Content-Range, 권한·삭제·만료를 별도 테스트한다. 브라우저 video 태그에 Bearer를 전달하는 FE 방식도 함께 정한다.
- DB 시각은 UTC aware를 보장한다. 실제 PostgreSQL migration의 timestamptz 사용 여부를 명시한다.
- 삭제 시 접근을 먼저 차단하고 영상·전사·리포트 및 백업 보존 정책을 적용한다. 늦은 콜백이 데이터를 복원하지 않도록 한다.
- PDF/QA 테이블은 후속: pgvector 차원/확장과 QA 활성 세션 부분 고유 인덱스는 해당 기능 도입 시 함께 구현한다.

## v10 채점 컬럼과 활성화 검증

- reports.total_score: 네 항목 점수 동일 가중 평균의 정수. .5 반올림 규칙은 활성 scoring_config에서 고정한다. 값이 미정이면 ACTIVE로 전환하지 않는다.
- report_scores.score_source: RULE/LLM/HYBRID 중 실제 산출 경로. breakdown JSONB에는 적용 규칙·제스처 사건별 감점·LLM 기준 판단과 근거·제외 사유를 담는다. 원시 프레임은 저장하지 않는다. 상세 스키마를 정한 뒤 검증한다.
- rubric_items.scoring_config JSONB는 계산 설정이다. scoring_guide 텍스트를 기계 계산식으로 사용하지 않는다. DRAFT에는 비어 있거나 미정일 수 있지만 ACTIVE 전 신호·단위·시간 분모·임계값·환산식·LLM 기준/필수 여부/앵커·혼합 비율·감점·중복 처리·품질 하한·반올림 버전을 검증한다.
- rubric_items는 (rubric_id,item_key) UNIQUE, item_key는 SPEECH_RATE/FLUENCY/GESTURE/GAZE만 허용. ACTIVE 루브릭에는 네 항목이 정확히 하나씩 있고 각 weight=0.25여야 한다. DB CHECK만으로 다른 행 전체의 개수/합을 검증할 수 없으므로 활성화 트랜잭션에서 확인한다.
- 필수 휴리스틱 UNDETERMINED는 결과를 FAILED 처리한다. 선택 기준이면 점수에서 제외하고 limitations에 이유를 남긴다. 무엇이 필수인지 scoring_config에 명시해야 한다.
- 보고서 저장과 DONE 공개 시 네 report_scores의 정확한 항목 집합·중복·산출 경로·총점·근거 시각을 검증한다.
