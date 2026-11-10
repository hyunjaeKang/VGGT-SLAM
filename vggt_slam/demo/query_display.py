"""Frame-aligned saved query overlays for the main RGB view."""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from vggt_slam.demo.object_colors import class_color


def result_observations(query):
    """Keep result-frame entries with valid 3D detections."""
    return [o for o in query.get('search', {}).get('observations', [])
            if o.get('valid_boxes', 0) > 0]


def overlay_query_rgb(image, run_path, query, playback_index, legacy_target=0, show_masks=True, show_boxes=False, source_frame_id=None, class_colors=False):
    """Overlay only masks belonging to the currently displayed RGB frame."""
    base = Path(run_path) / Path(query['_asset_path']).parent
    observations = query.get('search', {}).get('observations', [])
    if observations:
        details = []
        for observation in observations:
            same_source = source_frame_id is not None and str(observation.get('source_frame_id')) == str(source_frame_id)
            if (observation['playback_index'] == playback_index or same_source) and observation.get('mask_count', 0):
                path = base / observation['result']
                details.append((path.parent, json.loads(path.read_text())))
    else:
        details = [(base, query)] if playback_index == legacy_target else []
    mask = np.zeros(image.shape[:2], dtype=bool)
    rectangles = []
    mask_colors=np.zeros_like(image)
    for folder, detail in details:
        for detection in detail.get('detections', []):
            name = detection.get('mask_path')
            if name and (folder / name).is_file():
                with Image.open(folder / name) as source:
                    pixels = np.asarray(source) > 0
                if pixels.shape == mask.shape:
                    mask |= pixels
                    label=detection.get('class_name') or detection.get('query') or detail.get('query','object')
                    mask_colors[pixels]=class_color(label) if class_colors else (34,211,238)
                    y, x = np.nonzero(pixels)
                    if len(x):rectangles.append(((int(x.min()),int(y.min()),int(x.max()),int(y.max())), detection.get('class_name') or detection.get('query') or detail.get('query','')))
    output = image.copy()
    if not show_masks:mask[:] = False
    output[mask] = (image[mask] * .45 + mask_colors[mask] * .55).astype(np.uint8)
    if show_boxes or show_masks:
        from PIL import ImageDraw
        picture = Image.fromarray(output)
        draw = ImageDraw.Draw(picture)
        for rectangle,label in rectangles:
            if show_boxes:draw.rectangle(rectangle, outline=class_color(label) if class_colors and label else (255,80,80), width=2)
            if label and class_colors:
                position=(rectangle[0],max(0,rectangle[1]-12))
                draw.text(position,str(label),fill=(255,255,255),stroke_width=1,stroke_fill=(0,0,0))
        output = np.asarray(picture)
    return output
