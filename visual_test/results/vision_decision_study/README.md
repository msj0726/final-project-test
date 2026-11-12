# 사용자 결정 반영 Vision 재실험 — 2026-11-11

결과: 실측 JSON 9개 생성 및 형식·의미 검증 통과. 행동 검출 정확도 개선은 확인하지 못함.
선택 모델: YOLO11n-pose + YOLO5Face + YOLO11n-seg. 손 모델 및 YOLOE 추론 없음.
사용자 결정: 양손목 정지 5초, 점수 환산 보류, 물건은 근접+동반 이동 조건, 얼굴 겹침 별도 후보.
추가 결정: 0.4초 누락까지 ID 유지 비교. 빈 프레임의 좌표나 사건을 생성하지 않음.

## 파일
- HTML: 자체 내장 영상 9개, 처음 보는 독자를 위한 결과 우선 설명.
- json/: 최종 0.4초 ID 유지+6표본 관찰 규칙의 실측 출력.
- raw_observations.json: 선택 모델 세 개를 실제 CPU 재실행한 결과.
- observations.json: 최종 후처리 관찰값.
- strict/: 즉시 초기화 규칙의 이전 실행 기록.
- gap04_four_samples/: ID 유지+4표본 완화의 추가 탐색 기록. 최종 채택 아님.
- tracking_comparison.json: 동일 모델 출력으로 추적 정책 3개 비교.
- validation.json / browser_validation.json: JSON·합성 경계·영상·브라우저 검사.
- config.json: 사용자 결정과 실험자가 고정한 수치를 구분.
- videos/: 9개 10초 무음 H.264 확인 영상.

## 실행 순서 (원래 저장소 루트, 기존 Python 실험 환경 필요)
python visual_test/vision_decision_study.py
python visual_test/process_vision_decisions.py
python visual_test/compare_vision_tracking.py
python visual_test/validate_vision_decisions.py
python visual_test/build_decision_report.py
python visual_test/check_decision_report.py

기존 visual_test/results/vision_study의 PTS 추출 450개 JPEG를 재사용합니다.
원본·가중치·YOLO5Face vendor·기존 Python 환경은 번들에 포함되지 않습니다.
재현 시 scripts/의 파일은 원래 visual_test/ 위치에 놓고 기존 경로를 사용해야 합니다.
공용 backend 코드·계약·DB는 변경하지 않았습니다.

## 한계
정답 없음·영상 재사용·실제 정지/가림 양성 검증 부족. 정답 없는 후보 감소를 정확도 상승으로 해석하지 않습니다.
NOT_RUN은 LLM 미실행이며 UNDETERMINED 판단과 다릅니다. 빈 사건 배열은 정상 행동 또는 지원 완료를 뜻하지 않습니다.
보고서에는 점수 필드가 없으며 기존 DONE Report로 직접 전송할 수 없습니다.
