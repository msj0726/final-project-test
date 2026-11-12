"""Load the three models used in the Vision experiment from trusted local files."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VisionModelPaths:
    pose: Path
    face: Path
    segmentation: Path
    face_repository: Path
    hand: Path | None = None


class VisionDetectors:
    def __init__(self, paths: VisionModelPaths):
        for path in (paths.pose, paths.face, paths.segmentation):
            if not path.is_file():
                raise FileNotFoundError(f"Vision model file is missing: {path}")
        if not (paths.face_repository / "models" / "experimental.py").is_file():
            raise FileNotFoundError("YOLO5Face repository is missing its model code")
        try:
            import cv2
            import numpy as np
            import torch
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("Install the backend vision extra before loading models") from exc

        # YOLO5Face checkpoints require its own trusted model classes at load time.
        repository = str(paths.face_repository.resolve())
        if repository not in sys.path:
            sys.path.insert(0, repository)
        from models.experimental import attempt_load
        from utils.datasets import letterbox
        from utils.general import non_max_suppression_face

        self.cv2 = cv2
        self.np = np
        self.torch = torch
        # The validated CPU experiment used one PyTorch thread per Vision worker.
        torch.set_num_threads(1)
        self.letterbox = letterbox
        self.non_max_suppression_face = non_max_suppression_face
        self.pose = YOLO(str(paths.pose))
        self.face = attempt_load(str(paths.face), map_location="cpu").eval()
        self.segmentation = YOLO(str(paths.segmentation))
        self.hand = None
        self.mp = None
        if paths.hand is not None:
            if not paths.hand.is_file():
                raise FileNotFoundError(f"Vision hand model file is missing: {paths.hand}")
            try:
                import mediapipe as mp
            except ImportError as exc:
                raise RuntimeError("Install the backend vision extra before loading hands") from exc
            self.mp = mp
            self.hand = mp.tasks.vision.HandLandmarker.create_from_options(
                mp.tasks.vision.HandLandmarkerOptions(
                    base_options=mp.tasks.BaseOptions(model_asset_path=str(paths.hand)),
                    num_hands=2,
                )
            )

    def detect(self, frame) -> dict:
        pose_result = self.pose.predict(frame, device="cpu", imgsz=640, conf=0.5, verbose=False)[0]
        body = self._body(pose_result)
        face = self._face(frame, body)
        objects = self._objects(frame)
        hands = []
        if self.hand is not None:
            image = self.mp.Image(
                image_format=self.mp.ImageFormat.SRGB,
                data=self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB),
            )
            height, width = frame.shape[:2]
            hands = [
                [[point.x * width, point.y * height] for point in landmarks]
                for landmarks in self.hand.detect(image).hand_landmarks
            ]
        return dict(body=body, face=face, objects=objects, hands=hands, frameShape=frame.shape[:2])

    def _body(self, result) -> dict | None:
        if len(result.boxes) == 0 or result.keypoints is None:
            return None
        boxes = result.boxes.xyxy.cpu().numpy()
        areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        order = self.np.argsort(areas)[::-1]
        if len(order) > 1 and areas[order[1]] / areas[order[0]] > 0.5:
            return None
        index = int(order[0])
        return dict(
            box=boxes[index].tolist(),
            points=result.keypoints.xy[index].cpu().numpy().tolist(),
            confidence=result.keypoints.conf[index].cpu().numpy().tolist(),
        )

    def _face(self, frame, body: dict | None) -> dict | None:
        if body is None:
            return None
        height, width = frame.shape[:2]
        scale = min(640 / max(height, width), 1)
        small = self.cv2.resize(frame, (round(width * scale), round(height * scale)))
        image, ratio, padding = self.letterbox(small, new_shape=640)
        tensor = self.torch.from_numpy(image[:, :, ::-1].transpose(2, 0, 1).copy())
        tensor = tensor.float()[None] / 255
        with self.torch.inference_mode():
            detections = self.non_max_suppression_face(self.face(tensor)[0], 0.5, 0.45)[0]
        candidates = []
        for detection in detections.cpu().numpy():
            points = detection[5:15].reshape(5, 2).copy()
            points[:, 0] = (points[:, 0] - padding[0]) / ratio[0] * width / small.shape[1]
            points[:, 1] = (points[:, 1] - padding[1]) / ratio[1] * height / small.shape[0]
            box = detection[:4].copy()
            box[[0, 2]] = (box[[0, 2]] - padding[0]) / ratio[0] * width / small.shape[1]
            box[[1, 3]] = (box[[1, 3]] - padding[1]) / ratio[1] * height / small.shape[0]
            body_box = body["box"]
            center_x, center_y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            if body_box[0] <= center_x <= body_box[2] and body_box[1] <= center_y <= body_box[
                1
            ] + 0.45 * (body_box[3] - body_box[1]):
                candidates.append(
                    dict(box=box.tolist(), points=points.tolist(), confidence=float(detection[4]))
                )
        return max(candidates, key=lambda face: face["confidence"], default=None)

    def _objects(self, frame) -> list[dict]:
        result = self.segmentation.predict(
            frame, device="cpu", imgsz=640, conf=0.25, verbose=False
        )[0]
        objects = []
        for index, box in enumerate(result.boxes):
            label = result.names[int(box.cls.item())]
            if label == "person":
                continue
            polygon = result.masks.xy[index].tolist() if result.masks is not None else []
            objects.append(
                dict(
                    label=label,
                    confidence=float(box.conf.item()),
                    box=box.xyxy[0].cpu().numpy().tolist(),
                    polygon=polygon,
                )
            )
        return objects
