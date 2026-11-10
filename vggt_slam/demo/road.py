"""Frame-aligned road surface and conservative BEV cell adjacency."""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import label

from vggt_slam.demo.dense_display import depth_display_points


def best_road_query(queries):
    candidates = [q for q in queries if any(o.get('prompt', o.get('query', '')).strip().lower() == 'road'
                  for o in q.get('search', {}).get('observations', []))]
    return max(candidates, key=lambda q: (q['search'].get('inspected_frames', 0), q['query_id']), default=None)


class RoadLayer:
    def __init__(self, run, query, per_frame=6000, prompt='road'):
        self.query_id = query['query_id']
        self.coverage = query.get('search', {}).get('inspected_frames', 0)
        self.total_frames = query.get('search', {}).get('total_frames', 0)
        self.groups = []
        self.group_classes=[]
        base = run.path / Path(query['_asset_path']).parent
        snapshot = query['snapshot']
        with np.load(run.path/'snapshots'/str(snapshot['step'])/(snapshot['phase']+'.npz')) as data:
            cameras = {int(n): p @ h for n, p, h in zip(data['node_ids'], data['projection_matrices'], data['homographies'])}
        for observation in query['search']['observations']:
            if prompt is not None and observation.get('prompt', observation.get('query', '')).strip().lower() != prompt:
                continue
            index = observation['playback_index']
            event = run.frames[index]
            if event['source_frame_id'] != observation['source_frame_id']:
                raise ValueError('Road result frame does not match run timeline')
            paths = event['asset_paths']
            metadata = json.loads((run.path / paths['metadata']).read_text())
            node = int(event['submap_id']) + metadata['submap_frame_index']
            detail_path = base / observation['result']
            detail = json.loads(detail_path.read_text())
            with np.load(run.path / paths['depth']) as data:
                depth, confidence, valid = [data[k].copy() for k in ('depth', 'confidence', 'valid')]
            mask = np.zeros(depth.shape, bool)
            for detection in detail.get('detections', []):
                name = detection.get('mask_path')
                if name:
                    pixels = np.asarray(Image.open(detail_path.parent / name)) > 0
                    if pixels.shape != depth.shape:
                        raise ValueError('Road mask is not on the recorded depth grid')
                    mask |= pixels
            rgb = np.asarray(Image.open(run.path / paths['rgb']).convert('RGB'))
            points, _, _ = depth_display_points(depth, confidence, valid & mask, cameras[node],
                         observation['confidence_threshold'], rgb, per_frame)
            if len(points):
                self.groups.append((index, node, points))
                self.group_classes.append(observation.get('prompt') or observation.get('query','object'))
        self.point_count = sum(len(g[2]) for g in self.groups)
        self._snapshot_key = None
        self._world_groups = []

    def world(self, run, step, phase, frame_index, only_frame=None):
        key = (step, phase)
        if key != self._snapshot_key:
            with np.load(run.path/'snapshots'/str(step)/(phase+'.npz')) as data:
                matrices = {int(n): h for n, h in zip(data['node_ids'], data['homographies'])}
            self._world_groups = []
            self._world_classes=[]
            for (index, node, points),name in zip(self.groups,getattr(self,'group_classes',['road']*len(self.groups))):
                if node not in matrices:
                    continue
                h = matrices[node]
                q = np.column_stack([points, np.ones(len(points))]) @ h.T
                with np.errstate(divide='ignore', invalid='ignore'):
                    xyz = q[:, :3] / q[:, 3:]
                xyz = xyz[np.isfinite(xyz).all(axis=1)].astype(np.float32)
                self._world_groups.append((index, xyz))
                self._world_classes.append(name)
            self._snapshot_key = key
        parts = [pts for index, pts in self._world_groups if index <= frame_index and (only_frame is None or index == only_frame)]
        return np.concatenate(parts) if parts else np.empty((0, 3), np.float32)

    def world_colored(self, run, step, phase, frame_index, only_frame=None):
        from vggt_slam.demo.object_colors import class_color
        points=self.world(run,step,phase,frame_index,only_frame)
        parts=[np.tile(class_color(name),(len(pts),1)) for (index,pts),name in zip(self._world_groups,self._world_classes)
               if index<=frame_index and (only_frame is None or index==only_frame)]
        colors=np.concatenate(parts).astype(np.uint8) if parts else np.empty((0,3),np.uint8)
        return points,colors


def connectivity_grid(points, plane='XZ', cells=128):
    """4-neighbour graph of observed road cells; never fill gaps or infer links."""
    if plane not in ('XZ', 'XY', 'YZ') or not 8 <= cells <= 256:
        raise ValueError('Invalid connectivity grid')
    axes = {'XZ': (0, 2), 'XY': (0, 1), 'YZ': (1, 2)}[plane]
    points = np.asarray(points).reshape(-1, 3)
    points = points[np.isfinite(points).all(axis=1)]
    xy = points[:, axes]
    low = xy.min(axis=0) if len(xy) else np.zeros(2)
    span = max(float(np.ptp(xy, axis=0).max()), 1e-3) if len(xy) else 1.
    width = span / (cells - 1)
    uv = np.floor((xy - low) / width + 1e-6).astype(int)
    uv = np.clip(uv, 0, cells - 1)
    counts = np.zeros((cells, cells), np.int64)
    np.add.at(counts, (uv[:, 1], uv[:, 0]), 1)
    occupied = counts > 0
    components, count = label(occupied, structure=np.array([[0,1,0],[1,1,1],[0,1,0]]))
    nodes = np.argwhere(occupied)
    ids = np.full((cells, cells), -1, np.int64)
    ids[occupied] = np.arange(len(nodes))
    edges = []
    for dy, dx in ((0, 1), (1, 0)):
        y, x = np.nonzero(occupied[:cells-dy, :cells-dx] & occupied[dy:, dx:])
        edges.extend(zip(ids[y, x].tolist(), ids[y+dy, x+dx].tolist()))
    return {'counts': counts, 'components': components, 'component_count': int(count),
            'nodes_yx': nodes, 'edges': np.asarray(edges, dtype=np.int64).reshape(-1, 2),
            'origin': low, 'cell_width': width, 'plane': plane}


def raster_connectivity(points, trajectory, plane='XZ', cells=128, size=480):
    graph = connectivity_grid(points, plane, cells)
    palette = np.array([[34,197,94], [56,189,248], [250,204,21], [192,132,252], [251,113,133]], np.uint8)
    canvas = np.full((cells, cells, 3), (15, 23, 42), np.uint8)
    components = graph['components']
    occupied = components > 0
    canvas[occupied] = palette[(components[occupied]-1) % len(palette)]
    # The cell graph connects only touching observed road cells, never the trajectory.
    image = Image.fromarray(canvas[::-1]).resize((size-48, size-48), Image.Resampling.NEAREST)
    result = Image.new('RGB', (size, size), (15, 23, 42))
    result.paste(image, (24, 24))
    draw = ImageDraw.Draw(result)
    centers = 24 + (graph['nodes_yx'][:, ::-1].astype(float) + .5) * (size-48) / cells
    centers[:, 1] = size - centers[:, 1]
    for a, b in graph['edges']:
        draw.line([tuple(centers[a]), tuple(centers[b])], fill=(166,230,192), width=1)
    draw.text((24, 5), f'ROAD connectivity / {plane} / 4-neighbour cells', fill='white')
    draw.text((24, size-19), f"{len(graph['nodes_yx'])} cells / {len(graph['edges'])} links / {graph['component_count']} components", fill='white')
    return np.asarray(result), {'mode': 'road_connectivity', 'plane': plane,
        'occupied_cells': len(graph['nodes_yx']), 'edges': len(graph['edges']),
        'components': graph['component_count'], 'cell_width': graph['cell_width'],
        'trajectory_points': len(trajectory), 'visible_points': len(points),
        'limitations': 'Observed 2D cell adjacency, not verified drivable connectivity; unknown cells remain empty'}
