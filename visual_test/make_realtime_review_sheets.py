"""Make raw frame pairs for human arm and wrist-motion annotation."""

from pathlib import Path

import cv2
import numpy as np

from realtime_yolo_benchmark import FPS, windows


def main():
    output = Path('results/realtime_yolo/review_sheets')
    upper_output = Path('results/realtime_yolo/review_sheets_upper')
    output.mkdir(parents=True, exist_ok=True)
    upper_output.mkdir(parents=True, exist_ok=True)
    for job_index, (path, start, count) in enumerate(windows(10)):
        cap = cv2.VideoCapture(str(path))
        tiles = []
        upper_tiles = []
        for second in range(count // FPS):
            pair = []
            upper_pair = []
            for offset in (0, FPS // 2):
                frame_index = start + second * FPS + offset
                assert cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ok, frame = cap.read()
                assert ok, (path, frame_index)
                pair.append(cv2.resize(frame, (400, 225)))
                assert frame.shape[:2] == (1080, 1920)
                upper_pair.append(cv2.resize(frame[:700, 700:1200], (400, 560)))
            tile = np.concatenate(pair, axis=1)
            header = np.full((32, 800, 3), 255, np.uint8)
            cv2.putText(header, f'{path.stem[:3]} window {job_index % 3} sample {second}: frame {start + second * FPS} -> +0.5s',
                        (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
            tiles.append(np.concatenate((header, tile), axis=0))
            upper_tiles.append(np.concatenate((header, np.concatenate(upper_pair, axis=1)), axis=0))
        cap.release()
        sheet = np.concatenate([np.concatenate(tiles[i:i + 2], axis=1) for i in range(0, 10, 2)], axis=0)
        out = output / f'{job_index:02d}_{path.stem[:3]}_window{job_index % 3}.jpg'
        assert cv2.imwrite(str(out), sheet)
        upper_sheet = np.concatenate([np.concatenate(upper_tiles[i:i + 2], axis=1) for i in range(0, 10, 2)], axis=0)
        upper_path = upper_output / out.name
        assert cv2.imwrite(str(upper_path), upper_sheet)
        print(out)


if __name__ == '__main__':
    main()
