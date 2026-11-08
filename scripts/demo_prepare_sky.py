"""Create a separate sky overlay for an existing run; never overwrite SLAM assets.

Model and preprocessing follow the VGGT official skyseg example:
https://github.com/facebookresearch/vggt/blob/main/visual_util.py
The network predicts high values on sky (verified by RGB/mask inspection).
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vggt_slam.demo.sky import sky_scores_for_points


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    cv2.setNumThreads(4)
    net = cv2.dnn.readNetFromONNX(str(args.model))
    events = [json.loads(line) for line in (args.run / 'events.jsonl').read_text().splitlines()]
    frames = [e for e in events if e['event_type'] == 'frame_selected']
    previews = [e for e in events if e['event_type'] == 'submap_preview_saved']
    step = max(int(p.name) for p in (args.run / 'snapshots').iterdir() if p.name.isdigit())
    with np.load(args.run / 'snapshots' / str(step) / 'after.npz') as snap:
        projections = {int(n): p @ h for n, p, h in zip(snap['node_ids'], snap['projection_matrices'], snap['homographies'])}
    started = time.monotonic()
    by_node, records, reused = {}, {}, {}
    for i, event in enumerate(frames):
        meta = json.loads((args.run / event['asset_paths']['metadata']).read_text())
        node = int(event['submap_id']) + meta['submap_frame_index']
        rgb = np.asarray(Image.open(args.run / event['asset_paths']['rgb']).convert('RGB'))
        digest = hashlib.sha256(rgb.tobytes()).hexdigest()
        if digest not in reused:
            x = cv2.resize(rgb, (320, 320)).astype(np.float32) / 255.
            x = (x - np.array([.485, .456, .406], np.float32)) / np.array([.229, .224, .225], np.float32)
            net.setInput(x.transpose(2, 0, 1)[None])
            values = net.forward().squeeze()
            if values.ndim != 2 or not np.isfinite(values).all():
                raise ValueError('invalid sky model output')
            probability = np.uint8(np.clip(cv2.resize(values, (rgb.shape[1], rgb.shape[0])), 0, 1) * 255)
            name = f'frame_{node}.png'
            Image.fromarray(probability).save(args.output / name)
            reused[digest] = name
        name = reused[digest]
        by_node[node] = name
        records[event['asset_paths']['metadata']] = name
        if i % 25 == 0:
            print(f'sky {i+1}/{len(frames)} ({time.monotonic()-started:.1f}s)', flush=True)
    projected = total = 0
    for event in previews:
        sid = int(event['submap_id'])
        with np.load(args.run / event['asset_paths']['preview']) as data:
            points, nodes = data['points'], data['node_ids']
        scores = np.zeros(len(points), np.uint8)
        for node in np.unique(nodes):
            idx = np.flatnonzero(nodes == node)
            probability = np.asarray(Image.open(args.output / by_node[int(node)]))
            scores[idx], count = sky_scores_for_points(points[idx], projections[int(node)], probability)
            projected += count
        total += len(points)
        np.savez_compressed(args.output / f'submap_{sid}.npz', scores=scores)
    result = {'schema_version': 1, 'status': 'completed', 'source_run': str(args.run.resolve()),
              'model': str(args.model.resolve()), 'model_sha256': hashlib.sha256(args.model.read_bytes()).hexdigest(),
              'model_url': 'https://huggingface.co/JianyuanWang/skyseg/resolve/main/skyseg.onnx',
              'probability_convention': '0 non-sky, 255 sky', 'margin_pixels': 2,
              'frames': records, 'frame_count': len(frames), 'unique_images': len(reused),
              'preview_points': total, 'projected_points': projected, 'seconds': time.monotonic()-started,
              'limitations': ['Segmentation is predicted, not ground truth', 'Preview display overlay; original PCD unchanged']}
    (args.output / 'index.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
