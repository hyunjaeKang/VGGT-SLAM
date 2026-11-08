import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from vggt_slam.demo.search_assets import mask_to_depth, segmentation_source, confidence_percentile
from vggt_slam.demo.search_cache import cached_masks
from vggt_slam.demo.search_policy import parse_queries, scope_frames


def test_comma_queries_split_aliases_and_preserve_adjectives():
    assert parse_queries('자동차, car; white building\ntree') == [
        {'label':'자동차','prompt':'car'}, {'label':'white building','prompt':'white building'},
        {'label':'tree','prompt':'tree'}]
    with pytest.raises(ValueError): parse_queries(' , ; ')
    with pytest.raises(ValueError): parse_queries(','.join(map(str,range(9))))


def test_all_scope_never_stops_at_first_success_and_removes_overlap():
    frames=[{'source_frame_id':str(i)} for i in range(10)]
    assert scope_frames(frames+[frames[3]],'all') == frames
    assert scope_frames(frames,'sampled',3) == [frames[0],frames[4],frames[9]]
    assert scope_frames(frames,'current',current=frames[6]) == [frames[6]]
    with pytest.raises(ValueError): scope_frames(frames,'current')


def test_native_mask_maps_pixel_centers_and_padding_to_depth():
    native=np.zeros((4,6),bool);native[2,3]=True
    matrix=np.array([[1.,0.,-2.],[0.,1.,1.],[0.,0.,1.]])
    mapped=mask_to_depth(native,matrix,(6,4))
    assert mapped.sum()==1 and mapped[3,1]
    assert not mapped[0].any()
    with pytest.raises(ValueError):mask_to_depth(native,None,(5,5))


def test_changed_native_source_is_rejected(tmp_path):
    Image.new('RGB',(518,140),'red').save(tmp_path/'record.png')
    Image.new('RGB',(518,140),'blue').save(tmp_path/'native.png')
    metadata={'source_path':str(tmp_path/'native.png'),'source_to_preprocessed_mapping':{
        'source_size_wh':[518,140],'resized_size_wh':[518,140],'crop_top':0,'batch_pad_top':0,
        'pixel_center_source_to_output':np.eye(3).tolist()}}
    image,matrix,reason=segmentation_source(tmp_path,{'asset_paths':{'rgb':'record.png'}},metadata)
    assert matrix is None and 'mismatch' in reason and image.getpixel((0,0))==(255,0,0)


def test_confidence_uses_actual_execution_args():
    assert confidence_percentile({'config':{'run_id':'x'},'execution_args':{'conf_threshold':70}})==70


def test_mask_cache_reuses_only_identical_image_prompt_and_model(tmp_path):
    calls=[]
    def infer(image,prompt):
        calls.append(prompt)
        return np.ones((1,2,3),bool),np.array([.9])
    image=Image.new('RGB',(3,2),'red')
    first=cached_masks(tmp_path,image,'car',{'model':'a'},infer)
    second=cached_masks(tmp_path,image,'car',{'model':'a'},infer)
    assert not first[2] and second[2] and calls==['car']
    cached_masks(tmp_path,image,'tree',{'model':'a'},infer)
    cached_masks(tmp_path,Image.new('RGB',(3,2),'blue'),'car',{'model':'a'},infer)
    cached_masks(tmp_path,image,'car',{'model':'b'},infer)
    assert len(calls)==4


def test_empty_masks_are_valid_cache_results(tmp_path):
    def infer(image,prompt):return np.zeros((0,1,2,3),bool),np.zeros(0)
    result=cached_masks(tmp_path,Image.new('RGB',(3,2)),'absent',{},infer)
    assert result[0].shape==(0,2,3)
