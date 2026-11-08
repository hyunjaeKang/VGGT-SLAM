"""Frame-aligned saved query overlays for the main RGB view."""
import json
from pathlib import Path

import numpy as np
from PIL import Image


def result_observations(query):
    """Keep result-frame entries with valid 3D detections."""
    return [o for o in query.get('search', {}).get('observations', [])
            if o.get('valid_boxes', 0) > 0]


def overlay_query_rgb(image, run_path, query, playback_index, legacy_target=0, show_masks=True, show_boxes=False):
    """Overlay only masks belonging to the currently displayed RGB frame."""
    base = Path(run_path) / Path(query['_asset_path']).parent
    observations = query.get('search', {}).get('observations', [])
    if observations:
        details = []
        for observation in observations:
            if observation['playback_index'] == playback_index and observation.get('mask_count', 0):
                path = base / observation['result']
                details.append((path.parent, json.loads(path.read_text())))
    else:
        details = [(base, query)] if playback_index == legacy_target else []
    mask = np.zeros(image.shape[:2], dtype=bool)
    rectangles = []
    for folder, detail in details:
        for detection in detail.get('detections', []):
            name = detection.get('mask_path')
            if name and (folder / name).is_file():
                with Image.open(folder / name) as source:
                    pixels = np.asarray(source) > 0
                if pixels.shape == mask.shape:
                    mask |= pixels
                    y, x = np.nonzero(pixels)
                    if len(x):rectangles.append((int(x.min()),int(y.min()),int(x.max()),int(y.max())))
    output = image.copy()
    if not show_masks:mask[:] = False
    output[mask] = (image[mask] * .45 + np.array([34, 211, 238]) * .55).astype(np.uint8)
    if show_boxes:
        from PIL import ImageDraw
        picture = Image.fromarray(output)
        draw = ImageDraw.Draw(picture)
        for rectangle in rectangles:draw.rectangle(rectangle, outline=(255,80,80), width=2)
        output = np.asarray(picture)
    return output
