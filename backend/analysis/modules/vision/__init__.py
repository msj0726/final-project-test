"""Video-to-observation entry point for the analysis worker."""

from pathlib import Path

from .models import VisionDetectors, VisionModelPaths
from .observation import SAMPLE_SECONDS, build_observation


def analyze_video(video_path: Path, model_paths: VisionModelPaths) -> dict:
    """Analyze a local video without publishing rubric scores or changing job status."""
    if not video_path.is_file():
        raise FileNotFoundError("The video file is missing")
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Install the backend vision extra before analyzing video") from exc

    detectors = VisionDetectors(model_paths)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError("The video cannot be opened")
    frames = []
    target_seconds = 0.0
    last_timestamp = -1.0
    previous_histogram = None
    try:
        while True:
            decoded, frame = capture.read()
            if not decoded:
                break
            timestamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if timestamp + 1e-6 < last_timestamp:
                raise ValueError("Video timestamps are not monotonic")
            last_timestamp = timestamp
            if timestamp + 1e-3 < target_seconds:
                continue
            if timestamp - target_seconds > SAMPLE_SECONDS + 1e-3:
                raise ValueError("Video has a gap in sampled frames")
            histogram = cv2.calcHist(
                [cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)], [0, 1], None, [16, 16], [0, 180, 0, 256]
            )
            cv2.normalize(histogram, histogram)
            scene_cut = (
                previous_histogram is not None
                and cv2.compareHist(previous_histogram, histogram, cv2.HISTCMP_BHATTACHARYYA) > 0.6
            )
            previous_histogram = histogram
            frames.append(
                dict(
                    startSec=round(target_seconds, 3),
                    sceneCut=bool(scene_cut),
                    **detectors.detect(frame),
                )
            )
            target_seconds = round(target_seconds + SAMPLE_SECONDS, 3)
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
    finally:
        capture.release()
    if not frames:
        raise ValueError("The video has no decodable frames")
    duration = frame_count / fps if 1 <= fps <= 120 and frame_count > 0 else 0
    if duration and duration - last_timestamp > 0.4 + 1e-6:
        raise ValueError("Video ended before its advertised duration")
    duration = max(duration, last_timestamp, frames[-1]["startSec"] + SAMPLE_SECONDS)
    for row in frames:
        row["endSec"] = round(min(row["startSec"] + SAMPLE_SECONDS, duration), 3)
    return build_observation(frames, duration)


__all__ = ["VisionModelPaths", "analyze_video"]
