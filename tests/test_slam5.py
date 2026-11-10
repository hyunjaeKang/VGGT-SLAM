import json
from pathlib import Path
import numpy as np
from PIL import Image
import pytest
from vggt_slam.demo.live_studio5 import LiveStudioV5,v5_configuration
from vggt_slam.demo.slam_preprocess import load_images
from vggt_slam.demo.image_mapping import crop_mappings


def test_v5_defaults_preserve_full_slam_and_do_not_enable_semantics(tmp_path):
    config=v5_configuration({})
    assert config['image_size']==378 and config['max_loops']==1 and config['min_disparity']==45
    studio=LiveStudioV5(jobs_root=tmp_path/'v5')
    path=studio.reserve('test.mp4',config)
    assert path.parent.parent==tmp_path/'v5'
    assert studio.job['semantic_enabled'] is False
    assert not studio.job['search_ready']


@pytest.mark.parametrize('query',[{'image_size':['320']},{'max_loops':['2']},{'max_frames':['-1']}])
def test_bad_configuration_rejected(query):
    with pytest.raises(ValueError):v5_configuration(query)


@pytest.mark.parametrize('width',[224,322,378,518])
def test_actual_model_resolution_and_pixel_mapping(width,tmp_path):
    paths=[]
    for i,shape in enumerate([(376,1408),(800,640)]):
        path=tmp_path/f'{i}.png';Image.fromarray(np.full((*shape,3),128,np.uint8)).save(path);paths.append(path)
    batch=load_images(paths,width)
    assert batch.shape==(2,3,width,width)
    maps=crop_mappings(paths,batch.shape[-2:],target_size=width)
    for mapping in maps:
        assert mapping['batch_size_hw']==[width,width]
        assert mapping['resized_size_wh'][0]==width
        matrix=np.array(mapping['pixel_center_source_to_output']);p=np.array([50,50,1.])
        np.testing.assert_allclose(np.linalg.inv(matrix)@(matrix@p),p)


def test_standard_loader_matches_upstream_for_mixed_shapes(tmp_path):
    from vggt.utils.load_fn import load_and_preprocess_images
    paths=[]
    for i,shape in enumerate([(376,1408),(800,640)]):
        path=tmp_path/f'{i}.png';Image.fromarray(np.random.default_rng(i).integers(0,256,(*shape,3),dtype=np.uint8)).save(path);paths.append(path)
    np.testing.assert_array_equal(load_images(paths,518).numpy(),load_and_preprocess_images(paths).numpy())


def test_no_loop_mode_skips_retrieval_model(monkeypatch):
    import vggt_slam.solver as module
    def forbidden(*a,**k):raise AssertionError('Retrieval model must not load')
    monkeypatch.setattr(module,'ImageRetrieval',forbidden)
    solver=module.Solver(25,device='cpu',enable_viewer=False,enable_retrieval=False,image_size=322)
    assert solver.image_retrieval is None and solver.image_size==322


def test_temporal_filter_searches_past_near_best_match(tmp_path):
    import torch
    from vggt_slam.map import GraphMap
    from vggt_slam.submap import Submap
    mapping=GraphMap();mapping.loop_min_seconds=10.
    paths=[tmp_path/'near.png',tmp_path/'far.png'];query=tmp_path/'query.png'
    mapping.loop_frame_records={str(p.resolve()):{'timestamp':t} for p,t in zip([*paths,query],[99.,20.,100.])}
    submap=Submap(0);submap.set_img_names(list(map(str,paths)));submap.set_all_retrieval_vectors(torch.tensor([[0.,0.],[.2,0.]]));mapping.add_submap(submap)
    result=mapping.retrieve_best_score_frame(torch.tensor([0.,0.]),100,ignore_last_submap=False,query_path=query)
    assert result[1:]==(0,1) and result[0]==pytest.approx(.2)
    mapping.loop_min_seconds=0
    assert mapping.retrieve_best_score_frame(torch.tensor([0.,0.]),100,False)[1:]==(0,0)


def test_temporal_filter_missing_timestamps_fail_closed(tmp_path):
    import torch
    from vggt_slam.map import GraphMap
    mapping=GraphMap();mapping.loop_min_seconds=10.
    with pytest.raises(ValueError,match='timestamp'):
        mapping.retrieve_best_score_frame(torch.zeros(2),0,query_path=tmp_path/'missing.png')


def test_v5_rejects_invalid_loop_time_gap():
    for value in ['nan','-1','601']:
        with pytest.raises(ValueError):v5_configuration({'min_loop_seconds':[value]})
    assert v5_configuration({})['min_loop_seconds']==10


def test_completed_v5_jobs_appear_immediately_in_history(tmp_path):
    studio=LiveStudioV5(jobs_root=tmp_path/'v5')
    studio.reserve('one.mp4',v5_configuration({}))
    studio.update(state='completed',run='one')
    first=studio.job['id']
    studio.reserve('two.mp4',v5_configuration({}))
    studio.update(state='completed',run='two')
    assert [j['id'] for j in studio.history]==[studio.job['id'],first]
    studio.update(message='updated')
    assert len(studio.history)==2 and studio.history[0]['message']=='updated'


def test_completed_v5_plays_decoded_rgb_tail_without_new_camera_estimates(tmp_path):
    from types import SimpleNamespace
    from vggt_slam.demo.playback5 import playback_clock
    (tmp_path/'keyframes').mkdir();(tmp_path/'meta.json').write_text(json.dumps({'source_timestamp':10.}))
    (tmp_path/'keyframes/video_frames.jsonl').write_text(''.join(json.dumps({'source_timestamp_seconds':t})+'\n' for t in [10.,11.,12.]))
    run=SimpleNamespace(path=tmp_path,manifest={'status':'completed'},frames=[{'asset_paths':{'metadata':'meta.json'}}])
    clock=playback_clock(run,[0.,1.]);assert clock.duration==2.
    clock.seek(2.,False);assert clock.target()==1
    run.manifest['status']='running'
    assert playback_clock(run,[0.,1.]).duration==1.
