"""Derived, camera-local display points from recorded depth; no model inference."""
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import maximum_filter

from vggt_slam.demo.search_assets import confidence_percentile


def source_digest(run):
    return hashlib.sha256((Path(run) / 'events.jsonl').read_bytes()).hexdigest()


def depth_display_points(depth, confidence, valid, projection, threshold, rgb, limit, sky=None):
    """Unproject recorded depth through the full camera-local projective matrix."""
    depth = np.asarray(depth)
    y, x = np.indices(depth.shape)
    pixels = np.stack((x * depth, y * depth, depth, np.ones_like(depth)), axis=-1)
    homogeneous = pixels @ np.linalg.inv(projection).T
    with np.errstate(divide='ignore', invalid='ignore'):
        points = homogeneous[..., :3] / homogeneous[..., 3:]
    good = valid & (confidence > threshold) & (depth > 0) & np.isfinite(points).all(axis=-1)
    indices = np.flatnonzero(good)
    if len(indices) > limit:
        indices = indices[np.linspace(0, len(indices) - 1, limit, dtype=np.int64)]
    scores = np.zeros(depth.shape, np.uint8) if sky is None else maximum_filter(sky, size=5)
    return (points.reshape(-1, 3)[indices].astype(np.float32),
            np.asarray(rgb).reshape(-1, 3)[indices].astype(np.uint8), scores.ravel()[indices])


def prepare_dense_display(run, output, per_frame=20000, max_frames=None):
    run, output = Path(run).resolve(), Path(output).resolve()
    if not output.is_relative_to(run / 'evidence'):
        raise ValueError('Display cache must be inside run/evidence')
    if not 1000 <= per_frame <= 100000:
        raise ValueError('per_frame must be 1000..100000')
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    events = [json.loads(line) for line in (run / 'events.jsonl').read_text().splitlines()]
    frames = [e for e in events if e['event_type'] == 'frame_selected']
    if max_frames is not None:
        frames = frames[:max_frames]
    manifest = json.loads((run / 'manifest.json').read_text())
    step = max(int(p.name) for p in (run / 'snapshots').iterdir() if p.name.isdigit() and (p/'after.npz').is_file())
    snapshot_path = run / 'snapshots' / str(step) / 'after.npz'
    with np.load(snapshot_path) as data:
        projections = {int(n): p @ h for n, p, h in zip(data['node_ids'], data['projection_matrices'], data['homographies'])}
    sky_dir, sky_index = None, None
    for path in sorted((run / 'evidence').glob('sky_*/index.json'), reverse=True):
        candidate = json.loads(path.read_text())
        if candidate.get('status') == 'completed' and candidate.get('source_run') == str(run):
            sky_dir, sky_index = path.parent, candidate
            break
    thresholds, grouped, records = {}, {}, []
    for i, event in enumerate(frames):
        sid = int(event['submap_id'])
        paths = event['asset_paths']
        metadata = json.loads((run / paths['metadata']).read_text())
        node = sid + metadata['submap_frame_index']
        if sid not in thresholds:
            confidences = []
            for path in (run / 'submaps' / str(sid) / 'frames').glob('*/depth.npz'):
                with np.load(path) as data:
                    confidences.append(data['confidence'].copy())
            thresholds[sid] = np.percentile(np.stack(confidences), confidence_percentile(manifest)) + 1e-6
        sky = None
        if sky_index is not None:
            name = sky_index['frames'].get(paths['metadata'])
            if name is None:
                raise ValueError('Sky cache does not cover this frame')
            sky = np.asarray(Image.open(sky_dir / name))
        rgb = np.asarray(Image.open(run / paths['rgb']).convert('RGB'))
        with np.load(run / paths['depth']) as data:
            points, colors, scores = depth_display_points(data['depth'], data['confidence'], data['valid'],
                projections[node], thresholds[sid], rgb, per_frame, sky)
        grouped.setdefault(sid, []).append((points, colors, np.full(len(points), node, np.int64), scores))
        records.append({'metadata': paths['metadata'], 'source_frame_id': event['source_frame_id'],
                        'node_id': node, 'points': len(points), 'non_sky_points_32': int((scores < 32).sum())})
        if i % 25 == 0:
            print(f'dense {i+1}/{len(frames)} · {time.monotonic()-started:.1f}s', flush=True)
    submaps = {}
    for sid, groups in grouped.items():
        arrays = [np.concatenate(parts) for parts in zip(*groups)]
        name = f'submap_{sid}.npz'
        np.savez_compressed(output / name, points=arrays[0], colors=arrays[1], node_ids=arrays[2], sky_scores=arrays[3])
        submaps[str(sid)] = name
    index = {'schema_version': 1, 'status': 'completed', 'source_run': str(run),
             'events_sha256': source_digest(run), 'snapshot_step': step,
             'snapshot_sha256': hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
             'per_frame_limit': per_frame, 'frame_count': len(frames), 'complete_run': max_frames is None,
             'points': sum(r['points'] for r in records), 'frames': records, 'submaps': submaps,
             'sky_index': str(sky_dir/'index.json') if sky_dir else None,
             'seconds': time.monotonic()-started,
             'limitations': ['Derived display cache; geometry and original assets unchanged',
                             'Recorded depth resolution bounds available detail; not new inference']}
    (output / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
    return index
