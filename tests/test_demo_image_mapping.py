import numpy as np
from PIL import Image

from vggt_slam.demo.image_mapping import crop_mappings


def test_crop_mapping_matches_vggt_batch_geometry(tmp_path):
    from vggt.utils.load_fn import load_and_preprocess_images

    paths = []
    for index, shape in enumerate(((160, 90), (100, 200))):
        path = tmp_path / f"{index}.png"
        Image.new("RGB", shape, (30 + index, 80, 120)).save(path)
        paths.append(str(path))
    batch = load_and_preprocess_images(paths).numpy()
    mappings = crop_mappings(paths, batch.shape[-2:])
    for index, mapping in enumerate(mappings):
        resized = Image.open(paths[index]).convert("RGB").resize(tuple(mapping["resized_size_wh"]), Image.Resampling.BICUBIC)
        pixels = np.asarray(resized).astype(np.float32) / 255
        crop = mapping["crop_top"]
        pixels = pixels[crop:crop + 518]
        pad = mapping["batch_pad_top"]
        actual = batch[index].transpose(1, 2, 0)
        np.testing.assert_allclose(actual[pad:pad + len(pixels)], pixels, atol=1e-7)
        transform = np.asarray(mapping["pixel_center_source_to_output"])
        assert np.isclose(transform[0, 2], (transform[0, 0] - 1) / 2)
        assert np.isclose(transform[1, 2], (transform[1, 1] - 1) / 2 - crop + pad)
