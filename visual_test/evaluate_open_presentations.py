"""Run the existing YOLO face, pose, and geometric action rules on open talks."""

import csv
import json
from collections import deque
from pathlib import Path

import cv2
import torch
from ultralytics import YOLO

from realtime_yolo_benchmark import OLD_ROOT, attempt_load, infer


DATA = Path('data/open_presentations')
OUT = Path('results/open_presentations_yolo')


def main():
    paths = [DATA / 'erik_hanberg_lightning_2024.webm', DATA / 'jack_andraka_talk_2013.webm']
    assert all(path.is_file() for path in paths)
    assert torch.backends.mps.is_available(), 'This run requires the same Apple GPU as the prior real-time test.'
    OUT.mkdir(parents=True, exist_ok=True)
    pose = YOLO(str(OLD_ROOT / 'models/yolo11n-pose.pt'))
    face = attempt_load(str(OLD_ROOT / 'models/yolov5n-face.pt'), map_location='cpu').to('mps').eval()
    torch.set_num_threads(1)
    summaries = []
    for path in paths:
        cap = cv2.VideoCapture(str(path))
        assert cap.isOpened(), path
        history = deque()
        frames = face_output = person_output = all_six_valid = arm_yes = arm_unknown = motion_yes = motion_unknown = 0
        last_timestamp = -1.0
        with (OUT / f'{path.stem}_frames.csv').open('w', newline='') as file:
            writer = None
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                assert timestamp >= last_timestamp - 0.001, (path.name, frames, timestamp, last_timestamp)
                last_timestamp = timestamp
                out = infer(frame, timestamp, pose, face, history, 'mps', 'mps')
                row = {'video': path.name, 'frame': frames, 'timestamp_s': round(timestamp, 3), **out}
                if writer is None:
                    writer = csv.DictWriter(file, fieldnames=list(row))
                    writer.writeheader()
                writer.writerow(row)
                face_output += out['face_count'] > 0
                person_output += out['person_count'] > 0
                points = json.loads(out['shoulder_elbow_wrist_xy_valid'])
                all_six_valid += points is not None and all(p[2] for p in points.values())
                arm_yes += out['arm_raised'] is True
                arm_unknown += out['arm_raised'] is None
                motion_yes += out['large_wrist_motion_proxy'] is True
                motion_unknown += out['large_wrist_motion_proxy'] is None
                frames += 1
                if frames % 2000 == 0:
                    print(path.name, frames, flush=True)
        cap.release()
        assert frames > 0 and last_timestamp > 0
        summaries.append({'video': path.name, 'frames': frames, 'last_timestamp_s': round(last_timestamp, 2),
                          'approx_input_fps': round(frames / last_timestamp, 2),
                          'any_face_output_frames': face_output, 'any_person_output_frames': person_output,
                          'selected_pose_all_6_major_points_valid_frames': all_six_valid,
                          'arm_raised_evaluable_frames': frames - arm_unknown,
                          'arm_raised_yes_frames': arm_yes, 'large_wrist_motion_evaluable_frames': frames - motion_unknown,
                          'large_wrist_motion_yes_frames': motion_yes,
                          'large_wrist_motion_unknown_frames': motion_unknown,
                          'note': 'Outputs are not ground truth. Largest person may be audience; any face may be audience.'})
        print(summaries[-1], flush=True)
    (OUT / 'summary.json').write_text(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
