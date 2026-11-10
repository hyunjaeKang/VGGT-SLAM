import json
import numpy as np
import pytest
from vggt_slam.demo.semantic_store import SemanticStore,frame_uid,world_support,robust_box,visible_detections
from vggt_slam.demo.live_studio4 import v4_configuration,LiveStudioV4


def test_frame_identity_separates_run_rotation_and_exact_image():
    reference=frame_uid('run',4,'hash',0)
    assert reference==frame_uid('run','4','hash',0)
    assert len({reference,frame_uid('other',4,'hash'),frame_uid('run',4,'changed'),frame_uid('run',4,'hash',180)})==4


def test_single_writer_is_idempotent_and_preserves_negative_observations(tmp_path):
    store=SemanticStore(tmp_path)
    assert store.add('a',1,'car',{'status':'no_detection'})
    assert not store.add('a',1,'car',{'status':'supported_3d'})
    store.close()
    records=[json.loads(l) for l in (tmp_path/'semantic_observations.jsonl').read_text().splitlines()]
    assert len(records)==1 and records[0]['status']=='no_detection'


def test_projective_revision_reprojects_local_support_not_rigid_boxes():
    local=np.array([[0.,0,1],[1,0,1],[0,1,2]])
    h=np.eye(4);h[:3,3]=[2,0,1];h[3,0]=.2
    expected=np.array([[2,0,2],[3/1.2,0,2/1.2],[2,1,3]])
    np.testing.assert_allclose(world_support(local,h),expected,rtol=1e-6)
    np.testing.assert_allclose(local,[[0,0,1],[1,0,1],[0,1,2]])
    assert not np.allclose(world_support(local,h),world_support(local,np.eye(4)))


def test_robust_boxes_reject_missing_and_degenerate_depth():
    assert not robust_box(np.zeros((7,3)))['valid']
    assert not robust_box(np.column_stack([np.arange(12),np.zeros((12,2))]))['valid']
    rng=np.random.default_rng(42);points=rng.normal(size=(1000,3));points[-1]=[10000,10000,10000]
    box=robust_box(points)
    assert box['valid'] and max(box['extent'])<20


def test_dynamic_objects_do_not_leave_ghost_boxes_in_map_or_bev():
    dynamic={'playback_index':2,'dynamic_state':'possible'}
    static={'playback_index':1,'dynamic_state':'unconfirmed'}
    future={'playback_index':8,'dynamic_state':'unconfirmed'}
    assert visible_detections([dynamic,static,future],2)==[dynamic,static]
    assert visible_detections([dynamic,static,future],3)==[static]


def test_v4_defaults_avoid_v3_highway_over_sampling_and_false_loop_pressure():
    cfg=v4_configuration({})
    assert cfg['min_disparity']==45 and cfg['max_loops']==0 and cfg['classes']==['car','person','bicycle']


@pytest.mark.parametrize('q',[{'objects':['car,car']},{'objects':['']},{'backend':['fake']},{'detect_hz':['nan']},{'objects':['car; shell']}])
def test_invalid_v4_preset_is_rejected(q):
    with pytest.raises(ValueError):v4_configuration(q)


def test_v4_job_roots_do_not_reuse_v3_results(tmp_path):
    studio=LiveStudioV4(jobs_root=tmp_path/'v4')
    target=studio.reserve('test.mp4',v4_configuration({}))
    assert target.parent.parent==tmp_path/'v4'
    assert studio.job['version']=='live-v4' and studio.job['semantic_config']['backend']=='yolo26'


def test_incremental_map_retains_old_previews_and_ignores_uncommitted_tail(tmp_path,monkeypatch):
    from vggt_slam.demo.cache_live4 import IncrementalRun
    run=tmp_path/'run';run.mkdir();(run/'manifest.json').write_text(json.dumps({'run_id':'append','assets':{}}))
    for step in [1,2]:
        folder=run/'snapshots'/str(step);folder.mkdir(parents=True)
        for name in ['before','after']:np.savez(folder/(name+'.npz'),node_ids=[0])
    for sid in [0,1]:np.savez(run/f'p{sid}.npz',points=np.ones((3,3))*sid,colors=np.ones((3,3),np.uint8),node_ids=np.full(3,sid))
    first=[{'event_type':'submap_preview_saved','submap_id':0,'asset_paths':{'preview':'p0.npz'}},{'event_type':'optimization_finished','payload':{'step':1}}]
    events=run/'events.jsonl';events.write_text(''.join(json.dumps(e)+'\n' for e in first))
    cache=IncrementalRun(run);original=cache.previews[0][1]
    old_load=np.load
    def guarded(path,*args,**kwargs):
        assert str(path)!=str(run/'p0.npz'),'old preview was loaded again'
        return old_load(path,*args,**kwargs)
    monkeypatch.setattr(np,'load',guarded)
    tail=[{'event_type':'submap_preview_saved','submap_id':1,'asset_paths':{'preview':'p1.npz'}},{'event_type':'optimization_finished','payload':{'step':2}}]
    events.write_text(''.join(json.dumps(e)+'\n' for e in first+tail)+'{"event_type":')
    cache.refresh_committed()
    assert cache.preview_loads==2 and cache.previews[0][1] is original and cache.steps==[1,2]
    cache.refresh_committed();assert cache.preview_loads==2


def test_sqlite_live_and_archive_threads_share_one_serialized_writer(tmp_path):
    import threading
    store=SemanticStore(tmp_path)
    def live():
        for i in range(20):store.record_frame(str(i),{'i':i})
    thread=threading.Thread(target=live);thread.start()
    for i in range(20):store.add(str(i),i,'car',{'status':'waiting_depth'})
    thread.join();assert store.db.execute('SELECT COUNT(*) FROM frames').fetchone()[0]==20
    assert store.db.execute('SELECT COUNT(*) FROM observations').fetchone()[0]==20
    store.close()


def test_overlap_frames_preserve_query_playback_indices_in_v4_cache(tmp_path):
    from vggt_slam.demo.cache_live4 import IncrementalRun
    (tmp_path/'manifest.json').write_text(json.dumps({'run_id':'overlap','assets':{}}))
    (tmp_path/'snapshots').mkdir()
    events=[{'event_type':'frame_selected','source_frame_id':i} for i in [0,1,1,2]]
    (tmp_path/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
    cache=IncrementalRun(tmp_path,use_dense=False)
    assert [e['source_frame_id'] for e in cache.frames]==[0,1,1,2]
