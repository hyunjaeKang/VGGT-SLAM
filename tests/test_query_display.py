import json

import numpy as np
from PIL import Image

from vggt_slam.demo.cache import CachedRun
from vggt_slam.demo.query_display import overlay_query_rgb, result_observations


def test_result_frames_exclude_zero_boxes():
    records = [{'mask_count': 0, 'valid_boxes': 0}, {'mask_count': 2, 'valid_boxes': 0},
               {'mask_count': 2, 'valid_boxes': 1}]
    assert result_observations({'search': {'observations': records}}) == records[2:]


def test_rgb_overlay_matches_frame_and_combines_classes(tmp_path):
    folder = tmp_path / 'query'
    folder.mkdir()
    records = []
    for index in range(2):
        mask = np.zeros((3, 4), dtype=np.uint8)
        mask[index, index] = 255
        Image.fromarray(mask).save(folder / f'{index}.png')
        (folder / f'{index}.json').write_text(json.dumps({'detections': [{'mask_path': f'{index}.png'}]}))
        records.append({'playback_index': 7, 'mask_count': 1, 'result': f'{index}.json'})
    query = {'_asset_path': 'query/result.json', 'search': {'observations': records}}
    image = np.full((3, 4, 3), 100, dtype=np.uint8)
    assert np.array_equal(overlay_query_rgb(image, tmp_path, query, 8), image)
    result = overlay_query_rgb(image, tmp_path, query, 7)
    assert not np.array_equal(result[0, 0], image[0, 0])
    assert not np.array_equal(result[1, 1], image[1, 1])
    assert np.array_equal(result[2, 2], image[2, 2])
    assert (image == 100).all()


def test_query_delete_persists_without_removing_evidence(tmp_path):
    (tmp_path / 'manifest.json').write_text('{}')
    folder = tmp_path / 'evidence/query_jobs/test'
    folder.mkdir(parents=True)
    result = {'query_id': 'test', 'query': 'car'}
    (folder / 'result.json').write_text(json.dumps(result))
    (folder / 'status.json').write_text(json.dumps({'state': 'completed', 'result': 'evidence/query_jobs/test/result.json'}))
    run = CachedRun(tmp_path)
    assert len(run.object_queries) == 1
    run.delete_query('test')
    assert run.object_queries == []
    assert CachedRun(tmp_path).object_queries == []
    assert json.loads((folder / 'result.json').read_text()) == result


def test_rgb_boxes_can_be_shown_without_masks(tmp_path):
    folder=tmp_path/'query';folder.mkdir()
    mask=np.zeros((10,10),np.uint8);mask[2:8,2:8]=255
    Image.fromarray(mask).save(folder/'mask.png')
    q={'_asset_path':'query/result.json','detections':[{'mask_path':'mask.png'}]}
    image=np.full((10,10,3),100,np.uint8)
    result=overlay_query_rgb(image,tmp_path,q,0,show_masks=False,show_boxes=True)
    assert (result[4,4]==100).all()
    assert result[2,2,0]==255
    np.testing.assert_array_equal(overlay_query_rgb(image,tmp_path,q,0,show_masks=False),image)


def test_overlap_frame_uses_same_source_observation_only(tmp_path):
    import json
    from PIL import Image
    from vggt_slam.demo.query_display import overlay_query_rgb
    folder=tmp_path/'observation';folder.mkdir()
    Image.fromarray(np.full((4,5),255,np.uint8)).save(folder/'mask.png')
    (folder/'result.json').write_text(json.dumps({'detections':[{'mask_path':'mask.png'}]}))
    query={'_asset_path':'result.json','search':{'observations':[{'playback_index':33,'source_frame_id':'256','mask_count':1,'result':'observation/result.json'}]}}
    image=np.zeros((4,5,3),np.uint8)
    assert overlay_query_rgb(image,tmp_path,query,34,source_frame_id='256').any()
    assert not overlay_query_rgb(image,tmp_path,query,34,source_frame_id='257').any()
