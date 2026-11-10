import json
import struct
from types import SimpleNamespace
import numpy as np
from PIL import Image
from vggt_slam.demo.object_colors import class_color, query_legend
from vggt_slam.demo.query_display import overlay_query_rgb
from vggt_slam.demo.bev import raster_bev
from vggt_slam.demo.gpu_scene import DenseGPUScene


def test_rgb_legend_and_bev_share_exact_class_palette(tmp_path):
    image=np.zeros((80,100,3),np.uint8)
    ds=[]
    for i,name in enumerate(('car','person')):
        mask=np.zeros(image.shape[:2],np.uint8);mask[30:60,10+i*45:40+i*45]=255
        Image.fromarray(mask).save(tmp_path/f'{i}.png')
        ds.append({'class_name':name,'mask_path':f'{i}.png'})
    query={'_asset_path':'result.json','detections':ds}
    out=overlay_query_rgb(image,tmp_path,query,0,class_colors=True)
    for x,name in ((20,'car'),(65,'person')):
        np.testing.assert_array_equal(out[50,x],np.asarray(class_color(name))*.55//1)
    legend=query_legend(query)
    assert {e['name']:e['color'] for e in legend}=={n:list(class_color(n)) for n in ('car','person')}
    pts=np.array([[-1,0,-1],[1,0,1]],float)
    maskpts=np.array([[-.4,0,.3],[.4,0,-.3]])
    palette=np.array([class_color('car'),class_color('person')],np.uint8)
    bev,_=raster_bev(pts,np.zeros((2,3),np.uint8),[],mask_points=maskpts,mask_colors=palette,show_trajectory=False)
    for color in palette:
        expected=(np.array([15,23,42])*.3+color*.7).astype(np.uint8)
        assert (bev==expected).all(axis=2).any()


def test_gpu_semantic_packet_colors_and_color_only_cache_invalidation(tmp_path):
    snap=tmp_path/'snapshots/1';snap.mkdir(parents=True)
    np.savez(snap/'after.npz',node_ids=[0],homographies=[np.eye(4)])
    run=SimpleNamespace(path=tmp_path,preview_groups=[],sky_groups={})
    scene=DenseGPUScene();points=np.array([[0,0,1],[1,0,1]],np.float32)
    colors=np.array([class_color('car'),class_color('person')],np.uint8)
    first=scene.update(run,1,'after',[],0,10,False,32,'RGB',road_points=points,road_colors=colors)
    packet=scene.packet(first['epoch'],first['chunks'][0]['id'])
    _,n,_,offset=struct.unpack('<4sIII',packet[:16])
    np.testing.assert_array_equal(np.frombuffer(packet,np.uint8,count=n*3,offset=offset).reshape(-1,3),colors)
    second=scene.update(run,1,'after',[],0,10,False,32,'RGB',road_points=points,road_colors=colors[::-1])
    assert first['chunks'][0]['id']!=second['chunks'][0]['id']
