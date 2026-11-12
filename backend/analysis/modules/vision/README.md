# Vision 관찰 모듈

`analyze_video(video_path, model_paths)`는 **로컬 영상 파일을 읽어 루브릭 단계에 전달할 관찰 JSON**을 반환한다. 점수·Report·작업 상태는 만들지 않는다. `isScoringReady=false`이며 `vision.gaze`는 눈동자 시선이 아닌 얼굴의 카메라 정면 방향 추정이다. 손·물건 영역이 눈 주변과 겹치면 해당 프레임의 얼굴 방향을 관찰 불가(`EYE_REGION_OVERLAP`)로 처리해 정면 시간과 관찰 시간에서 제외한다. 얼굴 자체를 찾지 못하면 기존 `NO_ASSOCIATED_FACE`다.

모델 조합은 `yolo11n-pose.pt`, `yolov5n-face.pt`, `yolo11n-seg.pt`와 손·얼굴 겹침 후보용 MediaPipe Hand Landmarker다. 양손목 5초 정지, 물건의 손목 근접·1초 동반 이동, 손 특징점 외곽 또는 물건 마스크와 얼굴 박스 겹침 후보, 0.4초 미검출 추적 ID 유지 및 빈 구간 보간 금지를 적용한다. 손 모델을 제공하지 않으면 손·얼굴 겹침 후보는 생성되지 않는다. [내부 JSON Schema](vision_observation.schema.json)는 실험 v4 형식을 따른다.

## 실행 환경

```sh
cd backend
uv sync --locked --extra vision
```

네 모델 파일과 YOLO5Face 저장소 코드는 **신뢰할 수 있는 로컬 경로**로 별도 제공한다. 코드·가중치는 이 저장소에 포함하지 않는다. YOLO5Face는 PyTorch 체크포인트 역직렬화와 저장소 코드 import가 필요하므로 출처가 확인되지 않은 파일을 경로로 넘기지 않는다. 테스트한 모델 환경은 Python 3.11, Ultralytics 8.4.198, CPU다. 실험과 같이 PyTorch CPU 스레드를 프로세스당 1개로 설정하므로 다른 PyTorch 분석과는 별도 Vision 워커 프로세스에서 실행한다.

```python
from pathlib import Path

from analysis.modules.vision import VisionModelPaths, analyze_video

model_paths = VisionModelPaths(
    pose=Path("/trusted-models/yolo11n-pose.pt"),
    face=Path("/trusted-models/yolov5n-face.pt"),
    segmentation=Path("/trusted-models/yolo11n-seg.pt"),
    face_repository=Path("/trusted-models/yolov5-face"),
    hand=Path("/trusted-models/hand_landmarker.task"),
)
observation = analyze_video(Path("/temporary-job-video.mp4"), model_paths)
```

업로드 API/워커가 아직 없으므로, 영상 bytea를 소유한 API가 인증된 내부 영상 전달 경로를 구현한 뒤 워커가 임시 파일 경로를 이 함수에 넘겨야 한다. 이 모듈은 DB를 읽거나 쓰지 않는다. 루브릭 담당자는 반환값의 `vision`, `evidence`, `contextJudgments`, `limitations`를 소비한다. `candidateEvents`의 `HAND_FACE_OVERLAP_CANDIDATE`는 손 특징점 외곽과 얼굴 박스가 겹친 0.4초 이상 구간이다. 실제 가림·접촉·발표 관련성의 확정 사건이 아니며, `contextJudgments`의 `NOT_RUN`은 LLM 판단 불가(`UNDETERMINED`)와 다르다. 관찰 불가를 0점 또는 감점 없음으로 해석하지 않는다.

5 FPS 프레임 샘플마다 0.2초를 대표한다. `handStillSeconds`는 **5초 이상 지속된 정지 사건들의 시간 합**이다. 0은 모든 관찰 프레임에서 손이 움직였다는 뜻이 아니다. 임계값과 정확도는 독립 데이터에서 검증하지 않았다. 현재 9개 공개 영상 구간 실험은 출력 형식과 재현성을 확인한 것이며 채점 품질 검증이 아니다.

`vision.gaze.nonFrontFacingEvents`는 중앙 카메라를 관객 정면 방향으로 가정했을 때 얼굴 방향이 5초 이상 연속 비정면으로 판정된 후보 구간이다. 각 사건의 `evidenceRefs`는 최상위 `evidence`와 연결된다. 얼굴 미검출·눈 주변 가림은 연속 시간을 끊는다. 짧은 곁눈질을 합산하지 않으며, 실제 눈동자 시선이나 관객과의 눈맞춤을 확정하지 않는다. 이 사건은 제스처용 `candidateEvents`와 별개다.

눈 주변 겹침은 2D 좌표의 후보이며 실제 앞뒤 깊이를 증명하지 않는다. 손이 얼굴 옆에 있는 장면은 제외하지 않도록 눈 주변만 검사하지만, 독립 정답 영상에서 오제외·누락을 확인하기 전 시선 점수로 확정하지 않는다. v4는 `nonFrontFacingEvents`를 추가하고 `schemaVersion`과 `observationConfigVersion`을 갱신한다.
