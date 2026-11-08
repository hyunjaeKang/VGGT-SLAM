"""Content-addressed SAM masks; 3D boxes are always recalculated for the run."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import numpy as np


def cached_masks(root, image, prompt, model_identity, infer):
    rgb = np.asarray(image.convert('RGB'))
    identity = json.dumps({'prompt': prompt, 'model': model_identity, 'shape': rgb.shape,
                           'schema': 'native-sam3-masks-v1'}, sort_keys=True)
    digest = hashlib.sha256(identity.encode()+rgb.tobytes()).hexdigest()
    folder = Path(root)/digest
    if (folder/'masks.npz').is_file():
        with np.load(folder/'masks.npz') as data:
            masks, scores = data['masks'].copy(), data['scores'].copy()
        if masks.ndim != 3 or masks.shape[1:] != rgb.shape[:2] or len(scores) != len(masks):
            raise ValueError(f'invalid segmentation cache: {folder}')
        return masks, scores, True, digest
    masks, scores = infer(image, prompt)
    masks = np.asarray(masks, bool).reshape(-1, *rgb.shape[:2])
    scores = np.asarray(scores).reshape(-1)
    if len(scores) != len(masks):
        raise ValueError('SAM mask/score count mismatch')
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=folder, suffix='.npz', delete=False) as file:
        temporary = Path(file.name)
    try:
        np.savez_compressed(temporary, masks=masks, scores=scores)
        os.replace(temporary, folder/'masks.npz')
    finally:
        temporary.unlink(missing_ok=True)
    (folder/'identity.json').write_text(identity+'\n')
    return masks, scores, False, digest
