"""Describe the pixel geometry of the current VGGT crop preprocessing."""
from PIL import Image


def crop_mappings(paths, output_shape, target_size=518):
    """Return mappings for an entire batch, including mixed-height padding.

    Coordinates refer to pixel centres, not image edges. The resize dimensions,
    crop and batch padding mirror third_party/vggt/vggt/utils/load_fn.py.
    """
    if target_size < 14 or target_size % 14:
        raise ValueError("VGGT target width must be a positive multiple of 14")
    sizes = []
    for path in paths:
        with Image.open(path) as image:
            width, height = image.size
        resized_h = round(height * (target_size / width) / 14) * 14
        if resized_h <= 0:
            raise ValueError(f"invalid VGGT resized height for {path}")
        sizes.append((width, height, resized_h))
    batch_h = max(min(h, target_size) for _, _, h in sizes)
    if tuple(output_shape) != (batch_h, target_size):
        raise ValueError("actual preprocessed dimensions do not match VGGT crop mapping")
    result = []
    for width, height, resized_h in sizes:
        crop_top = max((resized_h - target_size) // 2, 0)
        pad_top = (batch_h - min(resized_h, target_size)) // 2
        sx, sy = target_size / width, resized_h / height
        result.append({"mode": "vggt_crop", "source_size_wh": [width, height],
                       "resized_size_wh": [target_size, resized_h], "crop_top": crop_top,
                       "batch_pad_top": pad_top, "batch_size_hw": [batch_h, target_size],
                       "pixel_center_source_to_output": [[sx, 0, (sx - 1) / 2],
                                                         [0, sy, (sy - 1) / 2 - crop_top + pad_top],
                                                         [0, 0, 1]],
                       "resampling": "PIL bicubic; EXIF orientation not applied",
                       "note": "cropped source regions have no output pixel; padding has no source pixel"})
    return result
