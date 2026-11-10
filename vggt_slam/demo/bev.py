"""Bounded RGB top-down preview, shared by cached and incremental viewers."""
import numpy as np
from PIL import Image, ImageDraw


def raster_bev(points, colors, trajectory, *, plane='XZ', size=480, zoom=1., show_trajectory=True, road_points=None, pan=(0., 0.), mask_points=None, boxes=(), mask_colors=None):
    """Project the visible map only; unknown cells stay dark, not free space.

    XZ is the initial camera horizontal plane (camera Y points down).
    This is a surface preview in reconstruction units, not metric occupancy.
    """
    axes = {'XZ': (0, 2), 'XY': (0, 1), 'YZ': (1, 2)}
    if plane not in axes:
        raise ValueError('unsupported BEV plane')
    if not .5 <= zoom <= 8:
        raise ValueError('BEV zoom must be .5..8')
    a, b = axes[plane]
    points, colors = np.asarray(points).reshape(-1, 3), np.asarray(colors).reshape(-1, 3)
    trajectory = np.asarray(trajectory).reshape(-1, 3)
    if len(points) != len(colors):
        raise ValueError('point/color mismatch')
    finite = np.isfinite(points).all(axis=1)
    points, colors = points[finite], colors[finite]
    trajectory = trajectory[np.isfinite(trajectory).all(axis=1)]
    xy, path = points[:, [a, b]], trajectory[:, [a, b]]
    if len(xy):
        low, high = np.quantile(xy, [.01, .99], axis=0)
    elif len(path):
        low, high = path.min(axis=0), path.max(axis=0)
    else:
        low, high = np.array([-1., -1.]), np.array([1., 1.])
    if len(path):
        low, high = np.minimum(low, path.min(axis=0)), np.maximum(high, path.max(axis=0))
    pan = np.asarray(pan, float)
    if pan.shape != (2,) or not np.isfinite(pan).all() or np.abs(pan).max() > 10:
        raise ValueError('Invalid BEV pan')
    base_span = max(float(np.max(high-low))*1.12, 1e-3)
    center = (low + high) / 2 + pan * base_span
    span = max(float(np.max(high - low)) * 1.12, 1e-3) / zoom
    low, high = center - span / 2, center + span / 2
    pad = 24
    scale = (size - 2 * pad - 1) / span

    def pixels(data):
        p = (data - low) * scale + pad
        p[:, 1] = size - 1 - p[:, 1]
        return np.rint(p).astype(np.int64)

    canvas = np.full((size, size, 3), (15, 23, 42), dtype=np.uint8)
    uv = pixels(xy)
    good = ((uv >= pad) & (uv < size - pad)).all(axis=1)
    uv, rgb = uv[good], colors[good]
    cell = uv[:, 1] * size + uv[:, 0]
    counts = np.bincount(cell, minlength=size * size)
    occupied = counts > 0
    for c in range(3):
        sums = np.bincount(cell, weights=rgb[:, c], minlength=size * size)
        canvas[:, :, c].reshape(-1)[occupied] = np.clip(sums[occupied] / counts[occupied], 0, 255).astype(np.uint8)
    mask_cells = 0
    if mask_points is not None:
        semantic = np.asarray(mask_points).reshape(-1, 3)
        semantic_colors=np.tile([34,211,238],(len(semantic),1)) if mask_colors is None else np.asarray(mask_colors).reshape(-1,3)
        if len(semantic_colors)!=len(semantic):raise ValueError('mask point/color mismatch')
        finite=np.isfinite(semantic).all(axis=1)
        semantic,semantic_colors=semantic[finite],semantic_colors[finite]
        uv_mask = pixels(semantic[:, [a,b]])
        good=((uv_mask >= pad) & (uv_mask < size-pad)).all(axis=1)
        uv_mask,semantic_colors=uv_mask[good],semantic_colors[good]
        unique,first = np.unique(uv_mask[:,1]*size+uv_mask[:,0],return_index=True)
        mask_cells = len(unique)
        flat = canvas.reshape(-1,3)
        flat[unique] = (flat[unique]*.3 + semantic_colors[first]*.7).astype(np.uint8)
    image = Image.fromarray(canvas)
    draw = ImageDraw.Draw(image)
    for i in range(5):
        v = pad + int(i * (size - 2 * pad) / 4)
        draw.line([(v, pad), (v, size-pad)], fill=(45, 58, 78), width=1)
        draw.line([(pad, v), (size-pad, v)], fill=(45, 58, 78), width=1)
    connectivity = None
    if road_points is not None:
        from vggt_slam.demo.road import connectivity_grid
        graph = connectivity_grid(road_points, plane)
        centers = graph['origin'] + (graph['nodes_yx'][:, ::-1] + .5) * graph['cell_width']
        uv_road = pixels(centers)
        for a_index, b_index in graph['edges']:
            a_pixel, b_pixel = uv_road[a_index], uv_road[b_index]
            if ((a_pixel >= pad) & (a_pixel < size-pad)).all() and ((b_pixel >= pad) & (b_pixel < size-pad)).all():
                draw.line([tuple(a_pixel), tuple(b_pixel)], fill=(74,222,128), width=2)
        for x, y in uv_road:
            if pad <= x < size-pad and pad <= y < size-pad:
                draw.point((int(x), int(y)), fill=(134,239,172))
        connectivity = {'occupied_cells': len(graph['nodes_yx']), 'edges': len(graph['edges']),
                        'components': graph['component_count']}
    if len(path) and show_trajectory:
        positions = [tuple(p) for p in pixels(path)]
        if len(positions) > 1:
            draw.line(positions, fill=(251, 146, 60), width=3)
        x, y = positions[-1]
        draw.ellipse((x-5, y-5, x+5, y+5), fill=(34, 211, 238), outline='white')
    for box in boxes:
        for segment in np.asarray(box):
            if np.isfinite(segment).all():
                xy_box = pixels(segment[:, [a,b]])
                if np.abs(xy_box).max() < size*100:
                    draw.line([tuple(p) for p in xy_box], fill=(255,80,80), width=2)
    draw.text((pad, 6), f'BEV / {plane} / visible surface', fill=(203, 213, 225))
    draw.text((pad, size-18), f'{span:.3g} reconstruction units / orange: path', fill=(148, 163, 184))
    return np.asarray(image), {'plane': plane, 'span': span, 'visible_points': int(len(points)),
                               'occupied_cells': int(occupied.sum()), 'trajectory_points': int(len(path)), 'trajectory_visible': show_trajectory, 'zoom': zoom,
                               'connectivity': connectivity, 'pan': pan.tolist(), 'mask_cells': mask_cells, 'box_count': len(boxes)}


class LiveBEV:
    """Keep a bounded per-submap display sample; replace it after optimization."""
    def __init__(self, server):
        import threading
        self.lock = threading.RLock()
        self.clouds, self.paths = {}, {}
        with server.gui.add_folder('실시간 2D 맵 · BEV'):
            self.image = server.gui.add_image(np.full((480, 480, 3), (15, 23, 42), np.uint8), label='BEV map', format='png')
            self.status = server.gui.add_markdown('지도 생성을 기다리는 중 · XZ 상대 좌표의 표면 투영')

    def set_cloud(self, name, points, colors):
        with self.lock:
            points, colors = np.asarray(points).reshape(-1, 3), np.asarray(colors).reshape(-1, 3)
            idx = np.linspace(0, len(points)-1, min(len(points), 5000), dtype=int)
            self.clouds[str(name)] = (points[idx].copy(), colors[idx].copy())

    def set_poses(self, name, positions):
        with self.lock:
            self.paths[str(name)] = np.asarray(positions).reshape(-1, 3).copy()
            points = np.concatenate([p for p, _ in self.clouds.values()]) if self.clouds else np.empty((0, 3))
            colors = np.concatenate([c for _, c in self.clouds.values()]) if self.clouds else np.empty((0, 3), np.uint8)
            if len(points) > 200000:
                idx = np.linspace(0, len(points)-1, 200000, dtype=int)
                points, colors = points[idx], colors[idx]
            path = np.concatenate([self.paths[k] for k in sorted(self.paths, key=int)])
            image, stats = raster_bev(points, colors, path)
            self.image.image = image
            self.status.content = (f"**BEV 갱신됨** · {len(self.clouds)} 서브맵 · {stats['visible_points']:,} 표시점  \n"
                                   '주황: 궤적 · 청록: 현재 위치 · 미관측 셀은 어둡게 표시 · 거리/지면 검증 전')
