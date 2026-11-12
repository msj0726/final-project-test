"""Measure the existing YOLO pose + YOLO5Face stack on presentation video clips."""

import argparse
import csv
import json
import platform
import sys
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

OLD_ROOT = Path('/Users/minseojang/Documents/ChatGPT/자소서/비언어행동_모델비교')
sys.path.insert(0, str(OLD_ROOT))
from benchmark import attempt_load, letterbox, non_max_suppression_face, scale_coords, yolo_face  # noqa: E402

torch.set_num_threads(1)
FPS = 30
POSE_CONF = FACE_CONF = 0.5
IMG_SIZE = 640
GESTURE_WINDOW_S = 0.5
GESTURE_DISTANCE = 0.25  # shoulder widths; an unvalidated geometric proxy
POINT_CONF = 0.5


def windows(seconds):
    paths = sorted((OLD_ROOT / 'data/videos').glob('*.mp4'))
    assert len(paths) == 6, f'Expected 6 videos, got {len(paths)}'
    result = []
    for path in paths:
        cap = cv2.VideoCapture(str(path))
        assert cap.isOpened(), path
        fps = cap.get(cv2.CAP_PROP_FPS)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        assert abs(fps - FPS) < 0.05 and count > seconds * FPS, (path, fps, count)
        for fraction in (0.2, 0.5, 0.8):
            start = max(0, min(round(count * fraction - seconds * FPS / 2), count - seconds * FPS))
            result.append((path, start, seconds * FPS))
    return result


def pose_points(result):
    if len(result.boxes) == 0 or result.keypoints is None:
        return None
    boxes = result.boxes.xyxy.cpu().numpy()
    i = int(np.argmax((boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])))
    xy = result.keypoints.xy[i].cpu().numpy()
    confidence = result.keypoints.conf
    valid = confidence[i].cpu().numpy() >= POINT_CONF if confidence is not None else np.all(xy > 0, axis=1)
    return xy, valid


def behavior(points, timestamp, history):
    if points is None:
        return None, None
    xy, valid = points
    if not all(valid[j] for j in (5, 6)):
        return None, None
    width = float(np.linalg.norm(xy[5] - xy[6]))
    if width < 1:
        return None, None
    sides = [(5, 9), (6, 10)]
    arm = (any(xy[w, 1] < xy[s, 1] - 0.1 * width for s, w in sides if valid[s] and valid[w])
           if any(valid[s] and valid[w] for s, w in sides) else None)
    target = timestamp - GESTURE_WINDOW_S
    earlier = min(history, key=lambda item: abs(item[0] - target), default=None)
    gesture = None
    if earlier is not None and abs(earlier[0] - target) <= 0.1:
        old_xy, old_valid, old_width = earlier[1:]
        displacement = [np.linalg.norm((xy[w] - xy[s]) - (old_xy[w] - old_xy[s])) /
                        ((width + old_width) / 2)
                        for s, w in sides if valid[s] and valid[w] and old_valid[s] and old_valid[w]]
        gesture = bool(displacement and max(displacement) >= GESTURE_DISTANCE) if displacement else None
    history.append((timestamp, xy, valid, width))
    while history and history[0][0] < timestamp - 1:
        history.popleft()
    return arm, gesture


def face_on_device(model, frame, device):
    if device == 'cpu':
        return yolo_face(model, frame, FACE_CONF)
    height, width = frame.shape[:2]
    scaled = cv2.resize(frame, (round(width * min(IMG_SIZE / max(height, width), 1)),
                                round(height * min(IMG_SIZE / max(height, width), 1))))
    image = letterbox(scaled, new_shape=IMG_SIZE)[0][:, :, ::-1].transpose(2, 0, 1).copy()
    tensor = torch.from_numpy(image).float().unsqueeze(0).to(device) / 255
    with torch.inference_mode():
        prediction = model(tensor)[0].cpu()  # Synchronize GPU before CPU NMS and timing.
        detections = non_max_suppression_face(prediction, FACE_CONF, 0.45)[0]
    if len(detections):
        detections = detections.clone()
        detections[:, :4] = scale_coords(tensor.shape[2:], detections[:, :4], frame.shape).round()
    return detections


def infer(frame, timestamp, pose, face, history, pose_device='cpu', face_device='cpu', executor=None):
    start = time.perf_counter()
    def run_face():
        began = time.perf_counter()
        result = face_on_device(face, frame, face_device)
        return result, (time.perf_counter() - began) * 1000

    def run_pose():
        began = time.perf_counter()
        result = pose.predict(frame, imgsz=IMG_SIZE, conf=POSE_CONF, device=pose_device, verbose=False)[0]
        if pose_device == 'mps':
            torch.mps.synchronize()
        return result, (time.perf_counter() - began) * 1000

    if executor is None:
        faces, face_ms = run_face()
        poses, pose_ms = run_pose()
    else:
        face_future = executor.submit(run_face)
        pose_future = executor.submit(run_pose)
        faces, face_ms = face_future.result()
        poses, pose_ms = pose_future.result()
    pose_end = time.perf_counter()
    points = pose_points(poses)
    arm, gesture = behavior(points, timestamp, history)
    end = time.perf_counter()
    person_box = None
    body_keypoints = None
    if points is not None:
        boxes = poses.boxes.xyxy.cpu().numpy()
        i = int(np.argmax((boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])))
        person_box = boxes[i].round(1).tolist()
        xy, valid = points
        body_keypoints = {str(j): [round(float(xy[j, 0]), 1), round(float(xy[j, 1]), 1), bool(valid[j])]
                          for j in (5, 6, 7, 8, 9, 10)}
    return {
        'face_count': len(faces), 'person_count': len(poses.boxes),
        'face_boxes_xyxy_conf': json.dumps(faces[:, :5].cpu().numpy().round(2).tolist()),
        'person_box_xyxy': json.dumps(person_box),
        'shoulder_elbow_wrist_xy_valid': json.dumps(body_keypoints),
        'arm_raised': arm, 'large_wrist_motion_proxy': gesture,
        'face_ms': face_ms,
        'pose_ms': pose_ms,
        'action_ms': (end - pose_end) * 1000,
        'inference_ms': (end - start) * 1000,
    }


def frames(path, start, count):
    cap = cv2.VideoCapture(str(path))
    assert cap.isOpened(), path
    assert cap.set(cv2.CAP_PROP_POS_FRAMES, start), (path, start)
    for offset in range(count):
        read_start = time.perf_counter()
        ok, frame = cap.read()
        read_end = time.perf_counter()
        if not ok:
            cap.release()
            raise RuntimeError(f'Could not decode {path.name} frame {start + offset}')
        yield start + offset, frame, read_start, read_end
    cap.release()


def offline(jobs, pose, face, pose_device='cpu', face_device='cpu', executor=None):
    rows = []
    start_time = time.perf_counter()
    for job_index, (path, start, count) in enumerate(jobs):
        history = deque()
        for index, frame, read_start, read_end in frames(path, start, count):
            out = infer(frame, index / FPS, pose, face, history, pose_device, face_device, executor)
            rows.append({'mode': 'offline', 'video': path.name, 'window': job_index % 3,
                         'frame': index, 'read_ms': (read_end - read_start) * 1000,
                         'end_to_end_ms': (time.perf_counter() - read_start) * 1000,
                         **out})
        print(f'offline {job_index + 1}/{len(jobs)}', flush=True)
    return rows, time.perf_counter() - start_time


def paced(jobs, pose, face, pose_device='cpu', face_device='cpu', executor=None):
    rows = []
    condition = threading.Condition()
    slot = {'item': None, 'done': False, 'decoded': 0, 'overwritten': 0, 'read_ms': []}
    start_time = time.perf_counter()

    def producer():
        for job_index, (path, start, count) in enumerate(jobs):
            segment_start = None
            for offset, (index, frame, read_start, read_end) in enumerate(frames(path, start, count)):
                if segment_start is None:
                    segment_start = read_end
                due = segment_start + offset / FPS
                wait = due - time.perf_counter()
                if wait > 0:
                    time.sleep(wait)
                with condition:
                    slot['decoded'] += 1
                    slot['read_ms'].append((read_end - read_start) * 1000)
                    if slot['item'] is not None:
                        slot['overwritten'] += 1
                    # Latest-frame policy keeps age bounded when inference is slower than capture.
                    slot['item'] = (job_index, path.name, index, frame, due)
                    condition.notify()
        with condition:
            slot['done'] = True
            condition.notify()

    thread = threading.Thread(target=producer, daemon=True)
    thread.start()
    histories = [deque() for _ in jobs]
    while True:
        with condition:
            condition.wait_for(lambda: slot['item'] is not None or slot['done'])
            if slot['item'] is None and slot['done']:
                break
            job_index, name, index, frame, due = slot['item']
            slot['item'] = None
        picked = time.perf_counter()
        out = infer(frame, index / FPS, pose, face, histories[job_index], pose_device, face_device, executor)
        end = time.perf_counter()
        rows.append({'mode': 'paced', 'video': name, 'window': job_index % 3,
                     'frame': index, 'queue_ms': (picked - due) * 1000,
                     'capture_to_output_ms': (end - due) * 1000, **out})
        if len(rows) % 300 == 0:
            print(f'paced outputs {len(rows)}', flush=True)
    thread.join()
    return rows, {'elapsed_s': time.perf_counter() - start_time,
                  'decoded': slot['decoded'], 'overwritten': slot['overwritten'],
                  'read_ms': slot['read_ms']}


def stats(values):
    array = np.asarray(values, dtype=float)
    return {'median': round(float(np.median(array)), 2),
            'p95': round(float(np.percentile(array, 95)), 2),
            'p99': round(float(np.percentile(array, 99)), 2)}


def write_csv(path, rows):
    with path.open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds-per-window', type=int, default=10)
    parser.add_argument('--output', type=Path, default=Path('results/realtime_yolo'))
    parser.add_argument('--threads', type=int, default=1)
    parser.add_argument('--pose-device', choices=('cpu', 'mps'), default='cpu')
    parser.add_argument('--face-device', choices=('cpu', 'mps'), default='cpu')
    parser.add_argument('--parallel-stages', action='store_true')
    args = parser.parse_args()
    assert args.seconds_per_window > 0 and args.threads > 0
    if 'mps' in (args.pose_device, args.face_device) and not torch.backends.mps.is_available():
        raise RuntimeError('MPS is unavailable in this PyTorch environment')
    jobs = windows(args.seconds_per_window)
    args.output.mkdir(parents=True, exist_ok=True)
    pose = YOLO(str(OLD_ROOT / 'models/yolo11n-pose.pt'))
    face = attempt_load(str(OLD_ROOT / 'models/yolov5n-face.pt'), map_location='cpu')
    face = face.to(args.face_device).eval()
    torch.set_num_threads(args.threads)
    cap = cv2.VideoCapture(str(jobs[0][0]))
    cap.set(cv2.CAP_PROP_POS_FRAMES, jobs[0][1])
    ok, warmup = cap.read()
    cap.release()
    assert ok
    executor = ThreadPoolExecutor(max_workers=2) if args.parallel_stages else None
    try:
        for _ in range(5):
            infer(warmup, 0, pose, face, deque(), args.pose_device, args.face_device, executor)
        torch.set_num_threads(args.threads)
        offline_rows, offline_seconds = offline(jobs, pose, face, args.pose_device, args.face_device, executor)
        paced_rows, paced_info = paced(jobs, pose, face, args.pose_device, args.face_device, executor)
    finally:
        if executor is not None:
            executor.shutdown()
    assert len(offline_rows) == sum(job[2] for job in jobs)
    assert paced_info['decoded'] == len(offline_rows)
    assert len(paced_rows) + paced_info['overwritten'] == paced_info['decoded']
    write_csv(args.output / 'offline_frames.csv', offline_rows)
    write_csv(args.output / 'paced_frames.csv', paced_rows)
    summary = {
        'setup': {'hardware': platform.platform(), 'torch': torch.__version__,
                  'opencv': cv2.__version__, 'pose_device': args.pose_device, 'face_device': args.face_device,
                  'parallel_stages': args.parallel_stages, 'torch_threads': torch.get_num_threads(),
                  'models': ['yolo11n-pose.pt', 'yolov5n-face.pt'], 'pose_conf': POSE_CONF,
                  'face_conf': FACE_CONF, 'keypoint_conf': POINT_CONF, 'image_size': IMG_SIZE,
                  'arm_rule': 'wrist_y < shoulder_y - 0.1 * shoulder_width',
                  'gesture_rule': f'wrist-minus-shoulder displacement >= {GESTURE_DISTANCE} shoulder widths in {GESTURE_WINDOW_S}s',
                  'videos': len(set(job[0] for job in jobs)), 'windows': len(jobs),
                  'seconds_per_window': args.seconds_per_window, 'source_fps': FPS,
                  'warmup_frames': 5, 'face_ground_truth': 'unavailable: faces masked',
                  'behavior_ground_truth': 'unavailable: no arm/gesture time labels'},
        'offline': {'frames': len(offline_rows), 'elapsed_s': round(offline_seconds, 2),
                    'throughput_fps': round(len(offline_rows) / offline_seconds, 2),
                    **{key: stats([row[key] for row in offline_rows]) for key in
                       ('read_ms', 'face_ms', 'pose_ms', 'action_ms', 'end_to_end_ms')}},
        'paced': {'decoded_frames': paced_info['decoded'], 'output_frames': len(paced_rows),
                  'overwritten_frames': paced_info['overwritten'],
                  'drop_rate': round(paced_info['overwritten'] / paced_info['decoded'], 4),
                  'elapsed_s': round(paced_info['elapsed_s'], 2),
                  'output_fps': round(len(paced_rows) / (len(jobs) * args.seconds_per_window), 2),
                  'wall_output_fps': round(len(paced_rows) / paced_info['elapsed_s'], 2),
                  'read_ms': stats(paced_info['read_ms']),
                  **{key: stats([row[key] for row in paced_rows]) for key in
                     ('face_ms', 'pose_ms', 'action_ms', 'queue_ms', 'capture_to_output_ms')}},
        'outputs': {mode: {
            'face_output_rate': round(sum(row['face_count'] > 0 for row in rows) / len(rows), 4),
            'person_output_rate': round(sum(row['person_count'] > 0 for row in rows) / len(rows), 4),
            'arm_yes_rate': round(sum(row['arm_raised'] is True for row in rows) / len(rows), 4),
            'gesture_yes_rate': round(sum(row['large_wrist_motion_proxy'] is True for row in rows) / len(rows), 4),
            'gesture_unknown_rate': round(sum(row['large_wrist_motion_proxy'] is None for row in rows) / len(rows), 4),
        } for mode, rows in (('offline', offline_rows), ('paced', paced_rows))},
    }
    (args.output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
