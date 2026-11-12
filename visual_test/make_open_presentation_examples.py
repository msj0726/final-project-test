"""Draw selected raw YOLO outputs on the two open presentation videos."""

import csv
import json
from pathlib import Path

import cv2


ROOT = Path('data/open_presentations')
OUT = Path('results/open_presentations_yolo')
TIMES = {
    'erik_hanberg_lightning_2024': [10.3, 41.3, 72.2, 103.2],
    'jack_andraka_talk_2013': [2, 78.6, 150, 175.7, 224.3, 230.2, 272.9, 295.9, 321.5, 370, 390],
}


def label(value):
    return {'True': 'Y', 'False': 'N', '': '?'}.get(value, '?')


def main():
    for stem, times in TIMES.items():
        with (OUT / f'{stem}_frames.csv').open(newline='') as file:
            rows = list(csv.DictReader(file))
        chosen = [min(rows, key=lambda row: abs(float(row['timestamp_s']) - time)) for time in times]
        targets = {int(row['frame']): row for row in chosen}
        cap = cv2.VideoCapture(str(ROOT / f'{stem}.webm'))
        assert cap.isOpened()
        panels = []
        frame_id = 0
        while targets:
            ok, frame = cap.read()
            if not ok:
                break
            row = targets.pop(frame_id, None)
            frame_id += 1
            if row is None:
                continue
            for box in json.loads(row['face_boxes_xyxy_conf']):
                x1, y1, x2, y2, conf = box
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 220, 0), 4)
                cv2.putText(frame, f'face {conf:.2f}', (int(x1), max(24, int(y1) - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 220, 0), 2)
            person = json.loads(row['person_box_xyxy'])
            if person:
                x1, y1, x2, y2 = person
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (255, 255, 0), 4)
            points = json.loads(row['shoulder_elbow_wrist_xy_valid']) or {}
            for a, b in [(5, 7), (7, 9), (6, 8), (8, 10)]:
                pa, pb = points.get(str(a)), points.get(str(b))
                if pa and pb and pa[2] and pb[2]:
                    cv2.line(frame, tuple(map(int, pa[:2])), tuple(map(int, pb[:2])), (255, 255, 0), 4)
            for j, (x, y, valid) in points.items():
                if valid:
                    cv2.circle(frame, (int(x), int(y)), 7, (0, 165, 255), -1)
                    cv2.putText(frame, j, (int(x) + 5, int(y) - 5), cv2.FONT_HERSHEY_SIMPLEX,
                                0.7, (0, 165, 255), 2)
            panel = cv2.resize(frame, (640, 360))
            cv2.rectangle(panel, (0, 0), (640, 42), (0, 0, 0), -1)
            text = (f"t={row['timestamp_s']}s face={row['face_count']} person={row['person_count']} "
                    f"arm={label(row['arm_raised'])} gesture={label(row['large_wrist_motion_proxy'])}")
            cv2.putText(panel, text, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            panels.append((float(row['timestamp_s']), panel))
            print(stem, text)
        cap.release()
        assert not targets and len(panels) == len(times), (stem, len(targets))
        panels = [panel for _, panel in sorted(panels)]
        columns = 2
        sheet = cv2.vconcat([cv2.hconcat(panels[i:i + columns])
                             for i in range(0, len(panels) - len(panels) % columns, columns)])
        if len(panels) % columns:
            sheet = cv2.vconcat([sheet, cv2.hconcat([panels[-1], panels[-1] * 0])])
        assert cv2.imwrite(str(OUT / f'{stem}_examples.jpg'), sheet)


if __name__ == '__main__':
    main()
