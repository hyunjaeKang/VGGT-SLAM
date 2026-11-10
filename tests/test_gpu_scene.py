import json,struct
from types import SimpleNamespace
import numpy as np
from vggt_slam.demo.gpu_scene import DenseGPUScene,pack_points
from vggt_slam.demo.smooth_runtime import CameraPath


def test_packet_layout_has_aligned_positions_and_exact_colors():
    pts=np.array([[1.,2,3],[4,5,6]])
    rgb=np.array([[1,2,3],[250,251,252]],np.uint8)
    data=pack_points(pts,rgb)
    magic,n,a,b=struct.unpack('<4sIII',data[:16]);assert magic==b'VGP2' and n==2
    np.testing.assert_array_equal(np.frombuffer(data,dtype='<f4',count=6,offset=a).reshape(2,3),pts)
    np.testing.assert_array_equal(np.frombuffer(data,dtype=np.uint8,count=6,offset=b).reshape(2,3),rgb)


def make_run(path):
    snap=path/'snapshots/1';snap.mkdir(parents=True)
    np.savez(snap/'after.npz',node_ids=np.arange(5),homographies=np.tile(np.eye(4),(5,1,1)))
    pts=np.column_stack([np.arange(5000),np.zeros(5000),np.ones(5000)])
    return SimpleNamespace(path=path,preview_groups=[(0,i,pts,np.full((5000,3),100,np.uint8)) for i in range(5)],sky_groups={})


def test_gpu_lod_retains_density_budget_and_never_reuploads_old_buffers(tmp_path):
    run=make_run(tmp_path);scene=DenseGPUScene()
    a=scene.update(run,1,'after',[0,1,2,3],3,19000,False,32,'RGB')
    assert a['map_points']==19000 and scene.uploads==4
    packet=scene.packet(a['epoch'],'0_0_dense')
    b=scene.update(run,1,'after',[0,1,2,3,4],4,19000,False,32,'RGB')
    assert b['map_points']==19000 and scene.uploads==5
    assert scene.packet(b['epoch'],'0_0_dense') is packet
    assert sum(c['count'] for c in b['chunks'] if c['near'])==15000
    earlier=scene.update(run,1,'after',[0],0,19000,False,32,'RGB')
    assert [c['id'] for c in earlier['chunks']]==['0_0_dense']
    assert earlier['map_points']==5000
    uploads=scene.uploads;data=scene.packet(earlier['epoch'],'0_0_dense')
    lower=scene.update(run,1,'after',[0],0,2000,False,32,'RGB')
    assert lower['map_points']==2000 and lower['epoch']==earlier['epoch']
    assert scene.uploads==uploads and scene.packet(lower['epoch'],'0_0_dense') is data


def test_calibrated_camera_path_preserves_skew_and_lens_shift_at_endpoints(tmp_path):
    snap=tmp_path/'snapshots/1';snap.mkdir(parents=True)
    k=np.array([[300.,31,450],[0,280,38],[0,0,1.]])
    p=np.column_stack([k,np.zeros(3)])
    p2=p.copy();p2[:,3]=-k@np.array([1.,0,0])
    matrices=[]
    for projection in [p,p2]:
        matrix=np.eye(4);matrix[:3]=projection;matrices.append(matrix)
    np.savez(snap/'after.npz',node_ids=[0,1],projection_matrices=matrices)
    frames=[]
    for i in range(2):
        name=f'{i}.json';(tmp_path/name).write_text(json.dumps({'submap_frame_index':i,'resolution_hw':[140,518]}))
        frames.append({'submap_id':0,'asset_paths':{'metadata':name}})
    path=CameraPath(SimpleNamespace(path=tmp_path,frames=frames),1,'after',[0,1])
    points=np.array([[.1,.2,2,1],[.3,-.1,3,1]])
    for t,projection in [(0,p),(1,p2)]:
        expected=points@projection.T;actual=points@path.at(t)['projection'].T
        np.testing.assert_allclose(actual[:,:2]/actual[:,2:],expected[:,:2]/expected[:,2:],atol=1e-8)
    assert path.at(.5)['intrinsic'][0,1]==31


def test_gpu_scene_filters_sky_and_invalidates_old_snapshot_packets(tmp_path):
    run=make_run(tmp_path)
    run.sky_groups={(0,0):np.r_[255,np.zeros(4999)].astype(np.uint8)}
    scene=DenseGPUScene()
    first=scene.update(run,1,'after',[0],0,20000,True,32,'RGB')
    assert first['map_points']==4999
    class Scene:
        def add_point_cloud(self,name,**kwargs):return SimpleNamespace(**kwargs,visible=True,remove=lambda:None)
    fake=Scene();scene.sync_viser(fake,True,.01)
    transform=np.eye(4);transform[0,3]=2.;transform[3,0]=.001
    np.savez(tmp_path/'snapshots/1/before.npz',node_ids=[0],homographies=[transform])
    newer=scene.update(run,1,'before',[0],0,20000,True,32,'RGB')
    assert newer['epoch']!=first['epoch']
    assert scene.packet(first['epoch'],'0_0_dense') is None
    data=scene.packet(newer['epoch'],'0_0_dense')
    _,n,offset,_=struct.unpack('<4sIII',data[:16])
    p=np.frombuffer(data,dtype='<f4',count=n*3,offset=offset).reshape(-1,3)
    # x'=(x+2)/(.001*x+1), z'=1/(.001*x+1).
    scene.sync_viser(fake,True,.01)
    np.testing.assert_allclose(scene.viser_handles['0_0_dense'].points,p)
    x=(1/p[:,2]-1)/.001
    np.testing.assert_allclose(p[:,0],(x+2)/(.001*x+1),rtol=1e-4)
