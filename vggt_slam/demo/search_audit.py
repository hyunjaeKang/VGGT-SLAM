"""Recheck every saved mask/depth/OBB without rerunning a model."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from vggt_slam.demo.search_assets import confidence_percentile


def audit_search_result(run, result_path):
    run, result_path = Path(run), Path(result_path)
    result = json.loads(result_path.read_text())
    search = result['search']
    events = [json.loads(line) for line in (run/'events.jsonl').read_text().splitlines()]
    frames = [e for e in events if e['event_type']=='frame_selected']
    manifest = json.loads((run/'manifest.json').read_text())
    percentile = confidence_percentile(manifest)
    with np.load(run/'snapshots'/str(result['snapshot']['step'])/(result['snapshot']['phase']+'.npz')) as data:
        projections = {int(n):p.copy() for n,p in zip(data['node_ids'],data['projection_matrices'])}
    thresholds={}; seen=set(); masks=boxes=contained=0; classes={}
    for observation in search['observations']:
        event=frames[observation['playback_index']]
        assert event['source_frame_id']==observation['source_frame_id']
        seen.add(event['source_frame_id'])
        meta=json.loads((run/event['asset_paths']['metadata']).read_text())
        sid=event['submap_id']; node=int(sid)+meta['submap_frame_index']
        if sid not in thresholds:
            arrays=[]
            for path in (run/'submaps'/str(sid)/'frames').glob('*/depth.npz'):
                with np.load(path) as data:arrays.append(data['confidence'])
            thresholds[sid]=np.percentile(np.stack(arrays),percentile)+1e-6
        with np.load(run/event['asset_paths']['depth']) as data:
            depth,confidence,valid=data['depth'],data['confidence'],data['valid']
        y,x=np.indices(depth.shape)
        homogeneous=np.stack((x*depth,y*depth,depth,np.ones_like(depth)),axis=-1)@np.linalg.inv(projections[node]).T
        with np.errstate(divide='ignore',invalid='ignore'):points=homogeneous[...,:3]/homogeneous[...,3:]
        valid=valid&(confidence>thresholds[sid])&np.isfinite(points).all(axis=2)
        path=result_path.parent/observation['result']; child=json.loads(path.read_text())
        count=0
        for detection in child['detections']:
            mask=np.asarray(Image.open(path.parent/detection['mask_path']))>0
            assert mask.shape==depth.shape
            assert int(mask.sum())==detection['mask_pixels']
            native=np.asarray(Image.open(path.parent/f"native_mask_{detection['index']:02d}.png"))>0
            assert int(native.sum())==detection['native_mask_pixels']
            support=points[valid&mask]
            if 'point_count' in detection:assert len(support)==detection['point_count']
            masks+=1
            if not detection['valid']:continue
            center,extent,rotation=[np.asarray(detection[key]) for key in ('center','extent','rotation')]
            assert np.isfinite(center).all() and np.isfinite(extent).all() and (extent>0).all()
            np.testing.assert_allclose(rotation.T@rotation,np.eye(3),atol=1e-6)
            local=(support-center)@rotation
            tolerance=max(float(extent.max())*1e-5,1e-6)
            assert (np.abs(local)<=extent/2+tolerance).all()
            count+=1;boxes+=1;contained+=len(support)
        assert len(child['detections'])==observation['mask_count']
        assert count==observation['valid_boxes']
        entry=classes.setdefault(observation['query'],{'masks':0,'valid_3d':0})
        entry['masks']+=len(child['detections']);entry['valid_3d']+=count
    assert masks==search['mask_count'] and boxes==search['valid_observations']
    assert len(seen)==search['inspected_frames']
    if search['mode']=='all':
        expected={e['source_frame_id'] for e in frames if not e.get('payload',{}).get('overlap')}
        assert seen==expected
    return {'status':'passed','frames':len(seen),'masks':masks,'valid_3d':boxes,
            'support_points_inside_saved_boxes':contained,'classes':classes,
            'unique_objects':None,'limitations':['Consistency audit, not ground-truth recall or precision']}
