"""Recorded projective cameras: exact pixel projection and a free-view pose."""
import numpy as np
from scipy.linalg import rq
from scipy.spatial.transform import Rotation


def overview_distance(diameter, fov, aspect):
    """Fit the robust map bounding sphere in both viewport dimensions."""
    half_angle = min(fov / 2, np.arctan(np.tan(fov / 2) * max(aspect, 1e-3)))
    return max(diameter, .1) / 2 / np.sin(half_angle) * 1.2


def rgb_camera(camera, shape):
    p = np.asarray(camera, dtype=float)[:3].copy()
    if not np.isfinite(p).all():
        raise ValueError('invalid camera')
    if np.linalg.det(p[:, :3]) < 0:
        p = -p
    k, r = rq(p[:, :3])
    signs = np.where(np.diag(k) < 0, -1., 1.)
    k, r = k @ np.diag(signs), np.diag(signs) @ r
    k /= k[2, 2]
    center = -np.linalg.solve(p[:, :3], p[:, 3])
    h, w = shape
    fov = 2 * np.arctan2(h / 2, k[1, 1])
    # Viser's public CameraHandle also uses OpenCV (+Z forward, -Y up).
    # It performs the WebGL conversion internally; doing it here reverses both.
    rotation = r.T
    return {'position': center, 'forward': r.T[:, 2], 'up': -r.T[:, 1],
            'wxyz': Rotation.from_matrix(rotation).as_quat()[[3, 0, 1, 2]],
            'fov': float(fov), 'aspect': w/h, 'projection': p, 'intrinsic': k}


def display_resolution(shape, viewport):
    """Fit calibrated image aspect into the viewport, bounded for CPU rendering."""
    h, w = shape
    width, height, dpr = viewport
    scale = min(width * min(dpr, 2) / w, height * min(dpr, 2) / h, 1920 / w, 1080 / h)
    return max(1, round(h * scale)), max(1, round(w * scale))


def raster_camera(points, colors, camera, shape, point_scale=1., boxes=(), output_shape=None, antialias=1):
    """Render actual 3D points with the complete P (including skew/lens shift).

    Ordinary centered perspective cameras cannot exactly express a projective
    reconstruction's K. This raster is the calibrated default; Viser remains
    available for free 3D orbit. Nearest projected depth wins each pixel.
    """
    from PIL import Image, ImageDraw
    h, w = shape
    output_height, output_width = output_shape or (h * 2, w * 2)
    if not 1 <= antialias <= 2 or not 1 <= output_height <= 2160 or not 1 <= output_width <= 3840:
        raise ValueError('Unsupported raster dimensions or antialias factor')
    height, width = round(output_height * antialias), round(output_width * antialias)
    scale = np.array([width / w, height / h])
    p = rgb_camera(camera, shape)['projection']
    points, colors = np.asarray(points), np.asarray(colors)
    q = points @ p[:, :3].T + p[:, 3]
    valid = np.isfinite(q).all(axis=1) & (q[:, 2] > 1e-8)
    q, colors = q[valid], colors[valid]
    projected = q[:, :2] / q[:, 2:3] * scale
    valid = (projected[:, 0] >= 0) & (projected[:, 0] < width-.5) & (projected[:, 1] >= 0) & (projected[:, 1] < height-.5)
    uv, colors, depths = np.rint(projected[valid]).astype(np.int64), colors[valid], q[valid, 2]
    radius = min(4, max(0, int(round(point_scale * (float(scale.min()) / 2 if output_shape else 1)))))
    offsets = np.array([(x, y) for x in range(-radius, radius+1) for y in range(-radius, radius+1)
                        if output_shape is None or x*x+y*y <= radius*radius])
    expanded = (uv[:, None, :] + offsets).reshape(-1, 2)
    source = np.repeat(np.arange(len(uv)), len(offsets))
    valid = (expanded[:, 0] >= 0) & (expanded[:, 0] < width) & (expanded[:, 1] >= 0) & (expanded[:, 1] < height)
    expanded, source = expanded[valid], source[valid]
    order = np.argsort(depths[source], kind='stable')
    flat = expanded[:, 1] * width + expanded[:, 0]
    cells, first = np.unique(flat[order], return_index=True)
    canvas = np.full((height*width, 3), (15, 23, 42), np.uint8)
    canvas[cells] = colors[source[order[first]]]
    image = Image.fromarray(canvas.reshape(height, width, 3))
    draw = ImageDraw.Draw(image)
    for box in boxes:
        for segment in np.asarray(box):
            xy = segment @ p[:, :3].T + p[:, 3]
            if np.isfinite(xy).all() and (xy[:, 2] > 1e-8).all():
                projected = xy[:, :2] / xy[:, 2:3] * scale
                # Prevent pathological projective lines from overwhelming the rasterizer.
                if np.abs(projected).max() < max(height, width) * 20:
                    draw.line([tuple(v) for v in projected], fill=(255, 80, 80), width=max(1, round(2 * antialias)))
    if antialias != 1:
        image = image.resize((output_width, output_height), Image.Resampling.LANCZOS)
    return np.asarray(image), {'output_shape_hw': [output_height, output_width], 'antialias': antialias, 'projected_points': int(len(uv)), 'occupied_pixels': int(len(cells)),
                               'shape_hw': [h, w], 'projection': p.tolist()}
