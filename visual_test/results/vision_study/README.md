# ProPitch Vision 실험 1–3

2026-11-10, 공개 영상 2개에서 9개 10초 구간, 5 FPS 450표본.
HTML은 확인 영상 36개와 검토 이미지를 내장한 독립 파일입니다. Chrome에서 여는 것을 검증했습니다.
공용 backend 코드·계약·DB는 변경하지 않았습니다.

## 핵심 산출물
- ProPitch_Vision_실측_실험보고서.html: 구간별 영상·JSON 선택, 모델 비교, 오류 사례, 한계.
- json/*.json: 실제 클립별 측정값. 채점 준비 상태 false, 손 관찰 시간이 0이면 정지 시간 null.
- observations.json: 450표본의 시간별 관찰·후처리·오류 사유.
- raw_observations.json: 모델 원시 관찰(복원된 좌표, 손 점, 물건 마스크 다각형, CPU 시간).
- videos/*_baseline.mp4 / *_hands.mp4 / *_standard.mp4 / *_open.mp4: 4개 표시 방식, 9구간, 총36개.
- vision-experiment.schema.json, validation.json, browser_validation.json: 스키마·의미·영상·브라우저 검사.
- error_review.json: 조수의 사후 육안 점검. 독립 사람 정답 아님.
- setup.json, frame_manifest.json, model_hashes.json: 설정·시각·가중치 재현 정보.

## 재현
기존 모델 비교 Python 환경에서 저장소 루트를 작업 디렉터리로 실행:
python visual_test/vision_study.py
python visual_test/summarize_vision_study.py
python visual_test/build_vision_report.py
python visual_test/check_vision_report.py

이 스크립트는 기존 realtime_yolo_benchmark.py의 OLD_ROOT와 YOLO5Face vendor를 재사용합니다.
원본 영상·기존 가중치·vendor·라이브러리는 번들에 포함되지 않습니다.
HTML은 별도 환경 없이 열 수 있으나 스크립트는 해당 기존 환경과 경로가 필요합니다.
보고서 도구 jsonschema/playwright는 visual_test/.report_tools에 격리 설치했습니다. backend 의존성 변경 없음.

추가 가중치 출처:
https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n-seg.pt
https://github.com/ultralytics/assets/releases/download/v8.4.0/yoloe-11s-seg-pf.pt

## 주의
이전 existing_pipeline_check의 Jack 175초 표본은 명목 FPS=1000을 사용한 탐색으로 시각 대응이 신뢰되지 않습니다.
이번 실험은 PTS 순차 추출로 교정했습니다. 이전 Jack 미검출을 175초의 검출 성능으로 인용하지 마세요.
5 FPS 시간 추정, 고정 실험 임계값, 재사용 영상이며 독립 정확도 평가가 아닙니다.
실제 감점·LLM·외부 API 호출 없음. 손·물건 가림/접촉은 후보만 존재합니다.
