# DB 모델 구현 위치

정본은 docs/specs/erd-v10.dbml, 적용 메모는 docs/DATABASE_RULES.md다. 아직 ORM·migration은 없다.

핵심: users/agreements/projects/단일 rubrics/rubric_items/uploads.video_data/rounds/analysis_jobs/stt_utterances/reports/report_scores/report_segments. 영상은 uploads에 한 번만, 전사는 job별 발화 행으로 저장한다. scoring_policies·공통/전문가 이중 점수·영상 storage_key는 만들지 않는다. PDF/QA 테이블은 후속 범위다.

ERD v10 추가 컬럼: rubrics.status, rubric_items.scoring_config, report_scores.score_source/breakdown. ACTIVE 제약과 네 항목 weight=0.25 검증을 migration 및 서비스 트랜잭션 설계에 반영한다. 현재 DB 모델과 migration은 아직 없다.
