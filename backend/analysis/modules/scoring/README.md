# 단일 루브릭 채점 구현 위치

담당 강유성, 관찰 신호 검토 장민서·이지수. 네 항목(SPEECH_RATE, FLUENCY, GESTURE, GAZE)을 규칙과 지정된 휴리스틱 LLM 평가로 산출한다. 서버가 네 정수 점수를 동일 비중 평균하며 FEEDBACK LLM은 확정 점수를 변경하지 않는다. 관찰 불가를 0점으로 치환하지 않는다.

실제 계산식·임계값·결손·반올림·품질 하한은 아직 미정이다. versions.model/rubric을 실제 실행 값으로 기록하고 정책이 정해지기 전 점수 품질을 주장하지 않는다. 계약 예시의 숫자를 채점값으로 재사용하지 않는다.

단계: RUBRIC_RULE → RUBRIC_HEURISTIC → SCORE_AGGREGATE → FEEDBACK. 정면 응시의 분모는 observableSeconds이고 0이면 비율 null이다. 제스처는 동일 사건을 프레임마다 감점하지 않으며 사용자가 지정한 세 행동 외에 추가 감점하지 않는다. 네 항목 정확히 한 번씩 검증하고 총점은 동등 가중이다. .5 반올림 방식은 미정이다.

ERD v10의 rubrics.status와 rubric_items.scoring_config를 사용한다. ACTIVE 전에 네 키와 각 weight=0.25, 계산 설정 완비, 서비스당 ACTIVE 하나를 확인한다. report_scores.score_source와 breakdown은 실제 RULE/LLM/HYBRID 경로·근거를 남긴다. 필수 휴리스틱 판단 불가는 FAILED, 선택 기준은 제외 사유를 limitations에 기록한다. 상세 JSON 스키마는 팀 합의 후 구현한다.
