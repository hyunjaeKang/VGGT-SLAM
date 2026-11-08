import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.spatial.transform import Rotation, Slerp
from vggt_slam.demo.smooth_runtime import PlaybackClock, CameraPath, PersistentMap, frame_times


def test_clock_advances_during_slow_render_skips_late_frames_and_pauses():
    wall=[0.]
    clock=PlaybackClock([0,.5,.5,1,1.5,2],now=lambda:wall[0])
    clock.set_playing(True)
    wall[0]=1.2
    assert clock.target()==3 and clock.position()==1.2
    clock.set_playing(False);wall[0]=10
    assert clock.position()==1.2
    clock.seek(.5)
    assert clock.target()==2
    clock.set_playing(True);wall[0]=11
    assert clock.position()==1.5


def test_camera_position_and_quaternion_interpolation():
    path=CameraPath.__new__(CameraPath)
    path.times=np.array([0.,1.])
    path.samples=[{'position':np.array([0.,0,0]),'fov':1.}, {'position':np.array([2.,0,0]),'fov':1.2}]
    rotations=Rotation.from_euler('y',[[0],[90]],degrees=True)
    path.slerp=Slerp(path.times,rotations)
    pose=path.at(.5)
    np.testing.assert_allclose(pose['position'],[1,0,0])
    np.testing.assert_allclose(pose['forward'],[2**-.5,0,2**-.5],atol=1e-8)
    assert abs(pose['fov']-1.1)<1e-8


def test_persistent_map_uploads_only_new_nodes_and_seek_hides_future(tmp_path):
    snap=tmp_path/'snapshots/1';snap.mkdir(parents=True)
    np.savez(snap/'after.npz',node_ids=[0,1],homographies=[np.eye(4),np.eye(4)])
    run=SimpleNamespace(path=tmp_path,preview_groups=[(0,i,np.array([[i,0.,1.]]),np.array([[255,0,0]],np.uint8)) for i in [0,1]],sky_groups={})
    class Scene:
        def add_point_cloud(self,name,**kw):return SimpleNamespace(visible=True,point_size=kw['point_size'],remove=lambda:None)
    chunks=PersistentMap(Scene())
    chunks.update(run,1,'after',[0],.01,False,32,'RGB');assert chunks.uploads==1
    chunks.update(run,1,'after',[0],.01,False,32,'RGB');assert chunks.uploads==1
    chunks.update(run,1,'after',[0,1],.01,False,32,'RGB');assert chunks.uploads==2
    chunks.update(run,1,'after',[0],.01,False,32,'RGB');assert not chunks.handles[0,1].visible


def test_frame_times_uses_source_spacing_and_labels_fps_assumption(tmp_path):
    frames=[]
    for i in [508,513,513,520]:
        file=f'{len(frames)}.json';(tmp_path/file).write_text(json.dumps({'source_timestamp':None}))
        frames.append({'source_frame_id':str(i),'asset_paths':{'metadata':file}})
    times,reason=frame_times(SimpleNamespace(path=tmp_path,frames=frames),10)
    np.testing.assert_allclose(times,[0,.5,.5,1.2])
    assert 'timestamps unavailable' in reason
    empty, reason = frame_times(SimpleNamespace(path=tmp_path,frames=[]),10)
    assert empty.tolist()==[0.] and 'unavailable' in reason


def test_clock_restarts_from_zero_after_end_without_old_elapsed_time():
    wall=[0.]
    clock=PlaybackClock([0.,1.,2.],now=lambda:wall[0])
    clock.set_playing(True);wall[0]=5
    assert clock.position()==2 and clock.target()==2
    clock.set_playing(False)
    clock.seek(0,False);clock.set_playing(True);wall[0]=5.5
    assert clock.position()==.5 and clock.target()==0
