"""Score frozen visual review labels and model-only event timing."""

import csv
import json
import statistics
import argparse
from collections import defaultdict
from pathlib import Path

from realtime_yolo_benchmark import FPS, windows

OUT = Path('results/realtime_yolo')
LABELS = None


def read_rows(name):
    with (OUT / name).open(newline='') as file:
        return list(csv.DictReader(file))


def score(rows, positive, uncertain, field, max_distance):
    by_window = defaultdict(list)
    for row in rows:
        by_window[(row['video'], int(row['window']))].append(row)
    counts = dict(tp=0, fp=0, fn=0, tn=0, missing=0, unknown_prediction=0)
    for job_index, (path, start, _) in enumerate(windows(10)):
        candidates = by_window[(path.name, job_index % 3)]
        for second in range(10):
            key = f'{job_index:02d}:{second}'
            if key in uncertain:
                continue
            target = start + second * FPS + FPS // 2
            row = min(candidates, key=lambda item: abs(int(item['frame']) - target), default=None)
            if row is None or abs(int(row['frame']) - target) > max_distance:
                counts['missing'] += 1
                predicted = False
            else:
                predicted = row[field] == 'True'
                if row[field] == '':
                    counts['unknown_prediction'] += 1
            actual = key in positive
            counts[('tp' if predicted else 'fn') if actual else ('fp' if predicted else 'tn')] += 1
    tp, fp, fn, tn = (counts[k] for k in ('tp', 'fp', 'fn', 'tn'))
    assert tp + fp + fn + tn == 180 - len(uncertain)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    return {**counts, 'samples': tp + fp + fn + tn, 'positives': tp + fn,
            'precision': precision, 'recall': recall, 'f1': f1}


def event_timing(offline, paced, field):
    original = defaultdict(list)
    replay = defaultdict(list)
    for rows, dest in ((offline, original), (paced, replay)):
        for row in rows:
            dest[(row['video'], int(row['window']))].append(row)
    delays = []
    events = misses = 0
    for key, full_rows in original.items():
        full_rows.sort(key=lambda row: int(row['frame']))
        live_rows = sorted(replay[key], key=lambda row: int(row['frame']))
        start = None
        for i in range(len(full_rows) + 1):
            active = i < len(full_rows) and full_rows[i][field] == 'True'
            if active and start is None:
                start = i
            if not active and start is not None:
                if i - start >= 3:
                    first = int(full_rows[start]['frame'])
                    last = int(full_rows[i - 1]['frame'])
                    events += 1
                    found = next((row for row in live_rows if first <= int(row['frame']) <= last + 6 and row[field] == 'True'), None)
                    if found is None:
                        misses += 1
                    else:
                        delays.append((int(found['frame']) - first) / FPS * 1000 + float(found['capture_to_output_ms']))
                start = None
    return {'offline_model_events_ge_0.1s': events, 'paced_missed': misses,
            'model_onset_to_paced_output_ms_median': statistics.median(delays) if delays else None,
            'model_onset_to_paced_output_ms_p95': sorted(delays)[int(0.95 * (len(delays) - 1))] if delays else None,
            'note': 'Onsets are defined by the offline model, not independent human behavior annotations.'}


def main():
    global OUT, LABELS
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--labels', type=Path, default=OUT / 'review_labels.json')
    args = parser.parse_args()
    OUT = args.output
    LABELS = json.loads(args.labels.read_text())
    offline = read_rows('offline_frames.csv')
    paced = read_rows('paced_frames.csv')
    report = {}
    for name, positive_key, uncertain_key, field in (
        ('arm', 'arm_positive', 'arm_uncertain', 'arm_raised'),
        ('large_wrist_motion', 'large_wrist_motion_positive', 'large_wrist_motion_uncertain', 'large_wrist_motion_proxy'),
    ):
        positive = set(LABELS[positive_key])
        uncertain = set(LABELS[uncertain_key])
        assert not positive & uncertain
        report[name] = {'offline': score(offline, positive, uncertain, field, 0),
                        'paced': score(paced, positive, uncertain, field, 3),
                        'model_event_timing': event_timing(offline, paced, field)}
    (OUT / 'behavior_review_summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
