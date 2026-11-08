"""Verified native-image segmentation and recorded depth-grid correspondence."""
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates


def segmentation_source(run, event, metadata):
    recorded = Image.open(Path(run) / event['asset_paths']['rgb']).convert('RGB')
    mapping = metadata.get('source_to_preprocessed_mapping')
    path = metadata.get('source_path')
    if not path or not mapping or not Path(path).is_file():
        return recorded, None, 'recorded RGB; native source/mapping unavailable'
    native = Image.open(path).convert('RGB')
    if list(native.size) != mapping['source_size_wh']:
        return recorded, None, 'recorded RGB; native dimensions changed'
    resized = native.resize(tuple(mapping['resized_size_wh']), Image.Resampling.BICUBIC)
    cropped = resized.crop((0, mapping['crop_top'], resized.width,
                            mapping['crop_top'] + min(resized.height, 518)))
    reference = Image.new('RGB', recorded.size)
    reference.paste(cropped, (0, mapping['batch_pad_top']))
    error = float(np.abs(np.asarray(reference, float)-np.asarray(recorded, float)).mean())
    if error > 2:
        return recorded, None, f'recorded RGB; native mismatch mean={error:.3f}'
    return native, np.asarray(mapping['pixel_center_source_to_output'], float), f'verified native RGB; mean pixel difference={error:.3f}'


def mask_to_depth(mask, source_to_output, shape):
    mask = np.asarray(mask, bool).squeeze()
    if source_to_output is None:
        if mask.shape != tuple(shape):
            raise ValueError('segmentation/depth dimensions do not match')
        return mask
    y, x = np.indices(shape)
    pixels = np.stack((x, y, np.ones_like(x)), axis=-1) @ np.linalg.inv(source_to_output).T
    coordinates = [pixels[..., 1]/pixels[..., 2], pixels[..., 0]/pixels[..., 2]]
    return map_coordinates(mask.astype(np.uint8), coordinates, order=0, mode='constant', cval=0).astype(bool)


def confidence_percentile(manifest):
    return float(manifest.get('execution_args', {}).get('conf_threshold',
                 manifest.get('config', {}).get('conf_threshold', 25)))
