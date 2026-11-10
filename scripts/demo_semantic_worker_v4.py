"""Resident V4 live detector + exact-frame archival depth join (one model load)."""
import argparse
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import site
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
# Optional SAM3 invocation uses its own modern-Torch environment.
site.addsitedir(str(ROOT/'.venv/lib/python3.11/site-packages'))
import cv2
import numpy as np
from PIL import Image,ImageDraw
from vggt_slam.cameras import VideoFileCamera,EndOfStream
from vggt_slam.demo.live_studio import read_json,complete_events
from vggt_slam.demo.status import write_json_atomic
from vggt_slam.demo.search_assets import segmentation_source,mask_to_depth,confidence_percentile
from vggt_slam.demo.semantic_models import PersistentDetector,PersistentSurfaces,PersistentSAM3
from vggt_slam.demo.semantic_store import SemanticStore,frame_uid,world_support,robust_box


def image_hash(image):return hashlib.sha256(np.asarray(image).tobytes()).hexdigest()


def atomic_image(path,array):
    temp=Path(path).with_suffix('.tmp.jpg');Image.fromarray(array).save(temp,quality=88);os.replace(temp,path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);args=parser.parse_args()
    config=read_json(args.config);folder=args.config.parent;sem=folder/'semantic';sem.mkdir(exist_ok=True)
    store=SemanticStore(folder)
    timing=(folder/'timings.jsonl').open('a');counts={'live_decoded':0,'live_inspected':0,'live_skipped':0,'archive_inspected':0,'cache_hits':0,'model_loads':0,'surface_loads':0,'model_calls':0,'surface_calls':0}
    stop=threading.Event();lock=threading.Lock();slot=[None];eof=threading.Event();error=[]
    control_file=folder/'semantic_control.json';stats_file=folder/'semantic_status.json'
    classes=config['classes'];all_classes=classes+(['road'] if config.get('surfaces',True) else [])
    sky_groups={};sky_frames={};sky_masks={};sky_ready_sids=set();sky_done_sids=set();preview_cache=OrderedDict()
    results={name:[] for name in all_classes};anchors={};processed=set();thresholds={};snapshot_step=None;snapshot_h={};snapshot_p={};revision=0;run=None
    report={'state':'loading','message':'의미 모델 로딩','classes':classes,**counts}
    write_json_atomic(stats_file,report)
    started=time.monotonic()
    try:
        import torch
        torch.set_num_threads(2)
        detector=PersistentSAM3(classes) if config.get('backend')=='sam3' else PersistentDetector(config['checkpoint'],classes,config.get('device','auto'),config.get('image_size',640))
        surfaces=PersistentSurfaces(config['surface_checkpoint'],device=detector.device,size=384) if config.get('surfaces',True) else None
        counts['model_loads']=detector.loads;counts['surface_loads']=surfaces.loads if surfaces else 0
        load_seconds=time.monotonic()-started
        timing_lock=threading.Lock()
        def log(stage,**data):
            with timing_lock:timing.write(json.dumps({'stage':stage,'wall_time':time.time(),'monotonic':time.monotonic(),**data},allow_nan=False)+'\n');timing.flush()
        log('model_load',seconds=load_seconds,device=detector.device,model_hash=detector.model_hash)
        def capture():
            camera=VideoFileCamera(config['input'],pacing='offline');camera.start();origin=time.monotonic();first_pts=None;last_emit=-1e9
            try:
                while not stop.is_set():
                    try:bgr=camera.capture()
                    except EndOfStream:break
                    fid=camera.source_frame_id
                    if config.get('max_frames') and fid>=config['max_frames']:break
                    counts['live_decoded']+=1;pts=camera.source_timestamp or fid/config['source_fps']
                    if first_pts is None:first_pts=pts
                    if config.get('live_pacing','realtime')=='realtime' and stop.wait(max(0,origin+pts-first_pts-time.monotonic())):break
                    if pts-last_emit<1/config['detect_hz']-1e-6:continue
                    last_emit=pts
                    with lock:
                        if slot[0] is not None:counts['live_skipped']+=1
                        slot[0]=(fid,pts,bgr[:,:,::-1].copy(),time.monotonic())
            except Exception as exc:error.append(repr(exc))
            finally:camera.stop();eof.set()
        thread=threading.Thread(target=capture,daemon=True);thread.start()
        cache=sem/'frame_cache';cache.mkdir(exist_ok=True)
        detector_lock=threading.Lock()
        def predict(fid,rgb,track=False):
            digest=image_hash(rgb);path=cache/f'{fid}_{digest[:16]}.npz'
            # Only detector/cache access is serialized. Slow surface inference
            # never holds this lock, so live 2D keeps running during depth joins.
            with detector_lock:
                if path.exists():
                    with np.load(path,allow_pickle=False) as data:
                        records=json.loads(str(data['records']));masks=data['masks']
                    for item in records:
                        idx=item.pop('mask_index');item['mask']=masks[idx] if idx>=0 else None
                    counts['cache_hits']+=1
                else:
                    records,seconds=detector.infer(rgb,track=track);counts['model_calls']=detector.calls
                    log('detector',source_frame_id=fid,seconds=seconds,live=track,model_hash=detector.model_hash)
                    metadata=[];masks=[]
                    for item in records:
                        meta={k:v for k,v in item.items() if k!='mask'};meta['mask_index']=len(masks) if item['mask'] is not None else -1
                        metadata.append(meta)
                        if item['mask'] is not None:masks.append(item['mask'])
                    np.savez_compressed(path,records=json.dumps(metadata),masks=np.stack(masks) if masks else np.empty((0,*rgb.shape[:2]),bool))
            surface_masks={}
            if surfaces is not None and not track:
                surface_masks,elapsed=surfaces.infer(rgb);counts['surface_calls']=surfaces.calls
                log('surfaces',source_frame_id=fid,seconds=elapsed,live=False)
            return records,surface_masks,digest
        def live_frame(payload):
            fid,pts,rgb,ingested=payload
            records,surface_masks,digest=predict(fid,rgb,True)
            image=Image.fromarray(rgb);draw=ImageDraw.Draw(image)
            for item in records:
                draw.rectangle(item['bbox_native'],outline='#22d3ee',width=3)
                draw.text(tuple(item['bbox_native'][:2]),f"{item['class_name']} #{item['track_id_2d']}",fill='yellow')
            atomic_image(folder/'live_rgb.jpg',np.asarray(image))
            uid=frame_uid(config['id'],fid,digest)
            meta={'revision':counts['live_inspected']+1,'source_frame_id':str(fid),'pts':pts,'frame_uid':uid,'image_hash':digest,
                  'detections':[{k:v for k,v in d.items() if k!='mask'} for d in records],
                  'status':'detected_2d' if records else 'no_detection','depth_status':'waiting_for_exact_frame_depth',
                  'ingest_to_result_seconds':time.monotonic()-ingested,'clock':'same-process monotonic; realtime source replay'}
            write_json_atomic(folder/'live_latest.json',meta);store.record_frame(uid,meta)
            log('live_result',source_frame_id=fid,seconds=meta['ingest_to_result_seconds'],detections=len(records))
            counts['live_inspected']+=1
        live_done=threading.Event()
        def live_detection():
            try:
                while not stop.is_set():
                    with lock:payload=slot[0];slot[0]=None
                    if payload is not None:live_frame(payload)
                    elif eof.is_set():break
                    else:stop.wait(.01)
            except Exception as exc:error.append(repr(exc));stop.set()
            finally:live_done.set()
        live_thread=threading.Thread(target=live_detection,daemon=True);live_thread.start()
        def archive_frame(event,playback_index):
            nonlocal revision
            meta=read_json(run/event['asset_paths']['metadata']);fid=str(event['source_frame_id'])
            image,mapping,source=segmentation_source(run,event,meta);rgb=np.asarray(image)
            records,surface_masks,digest=predict(fid,rgb)
            sid=int(event['submap_id']);node=sid+meta['submap_frame_index']
            with np.load(run/event['asset_paths']['depth']) as d:depth=d['depth'];conf=d['confidence'];valid=d['valid']
            if sid not in thresholds:
                data=[]
                for p in (run/'submaps'/str(sid)/'frames').glob('*/depth.npz'):
                    with np.load(p) as d:data.append(d['confidence'])
                thresholds[sid]=float(np.percentile(np.stack(data),confidence_percentile(read_json(run/'manifest.json')))+1e-6)
            if 'sky' in surface_masks:
                sky=mask_to_depth(surface_masks['sky'],mapping,depth.shape)
                sky_folder=run/'evidence/v4_live_sky';sky_folder.mkdir(parents=True,exist_ok=True)
                sky_path=sky_folder/f'node_{node}.png';Image.fromarray(np.uint8(sky)*255).save(sky_path)
                sky_ready_sids.add(sid);sky_masks[node]=str(sky_path.relative_to(run));sky_frames[event['asset_paths']['metadata']]=str(sky_path.relative_to(run))
            y,x=np.indices(depth.shape);pixels=np.stack((x*depth,y*depth,depth,np.ones_like(depth)),axis=-1)
            local_h=pixels@np.linalg.inv(snapshot_p[node]@snapshot_h[node]).T
            with np.errstate(divide='ignore',invalid='ignore'):local=local_h[...,:3]/local_h[...,3:]
            support=valid&(conf>thresholds[sid])&np.isfinite(local).all(axis=2)
            for name in all_classes:
                matches=[r for r in records if r['class_name']==name]
                if name=='road':matches=[{'mask':surface_masks['road'],'score':None,'track_id_2d':None}] if surface_masks.get('road',np.zeros((1,1))).any() else []
                path=run/'evidence/v4_semantics'/name/'observations'/str(playback_index)
                path.mkdir(parents=True,exist_ok=True)
                Image.open(run/event['asset_paths']['rgb']).convert('RGB').save(path/'frame.png')
                detection_records=[]
                for i,item in enumerate(matches):
                    if item['mask'] is None:continue  # a box alone is never treated as foreground depth
                    mask=mask_to_depth(item['mask'],mapping,depth.shape)
                    if name!='road' and 'sky' in surface_masks:mask&=~mask_to_depth(surface_masks['sky'],mapping,depth.shape)
                    points=local[support&mask];sample=points[np.linspace(0,len(points)-1,min(len(points),600),dtype=int)] if len(points) else np.empty((0,3),np.float32)
                    np.savez_compressed(path/f'local_{i}.npz',points=sample,node=node)
                    Image.fromarray(np.uint8(mask)*255).save(path/f'mask_{i:02d}.png')
                    d=robust_box(world_support(sample,snapshot_h[node]));d.update(index=i,mask_path=f'mask_{i:02d}.png',score=item['score'],track_id_2d=item['track_id_2d'],source_frame_id=fid,playback_index=playback_index,
                        class_name=name,query=name,mask_pixels=int(mask.sum()),node_id=node,dynamic_state='possible' if name in ('car','person','bicycle','truck','bus','motorcycle') else 'unconfirmed',global_object_id=None)
                    if name=='road':d.update(valid=False,reason='surface mask; no volumetric object box')
                    detection_records.append(d);anchors[(name,playback_index,i)]=(node,sample)
                detail={'schema_version':3,'query_id':f'v4_{name}_{playback_index}','query':name,'retrieval_score':0.,'submap_id':sid,'frame_index':meta['submap_frame_index'],'frame_image':'frame.png','detections':detection_records}
                write_json_atomic(path/'result.json',detail)
                result_base=run/'evidence/v4_semantics'/name
                obs={'source_frame_id':fid,'playback_index':playback_index,'query':name,'prompt':name,
                     'mask_count':len(detection_records),'valid_boxes':sum(d.get('valid',False) for d in detection_records),'result':str((path/'result.json').relative_to(result_base)),
                     'confidence_threshold':thresholds[sid],'source':source,'frame_uid':frame_uid(config['id'],fid,digest),'image_hash':digest}
                results[name].append(obs)
                store.add(hashlib.sha256(f'{obs["frame_uid"]}:{name}:{detector.model_hash}'.encode()).hexdigest(),fid,name,
                          {'status':'supported_3d' if obs['valid_boxes'] else 'detected_2d' if obs['mask_count'] else 'no_detection','node_id':node,'map_revision':snapshot_step,**obs})
            processed.add(fid);counts['archive_inspected']+=1;revision+=1
        def publish(geometry_done=False):
            if run is None:return {}
            from vggt_slam.demo.sky import sky_scores_for_points
            # Score only newly observed node groups; overlap groups can reuse
            # the same exact-frame sky mask under their current local camera.
            for event in complete_events(run/'events.jsonl'):
                if event['event_type']!='submap_preview_saved':continue
                sid=int(event['submap_id'])
                if sid not in sky_ready_sids or sid in sky_done_sids:continue
                if sid not in preview_cache:
                    with np.load(run/event['asset_paths']['preview']) as data:preview_cache[sid]=(data['points'].copy(),data['node_ids'].copy())
                    if len(preview_cache)>8:preview_cache.popitem(last=False)
                points,nodes=preview_cache[sid]
                for node in np.unique(nodes):
                    node=int(node);key=f'{sid}_{node}'
                    if key in sky_groups or node not in sky_masks or node not in snapshot_p:continue
                    probability=np.asarray(Image.open(run/sky_masks[node]));sample=points[nodes==node]
                    scores,_=sky_scores_for_points(sample,snapshot_p[node]@snapshot_h[node],probability)
                    path=run/'evidence/v4_live_sky'/f'group_{key}.npz';np.savez_compressed(path,scores=scores)
                    sky_groups[key]=str(path.relative_to(run))
                if all(f'{sid}_{int(n)}' in sky_groups for n in np.unique(nodes)):
                    sky_done_sids.add(sid);preview_cache.pop(sid,None)
            paths={}
            for name,observations in results.items():
                if not observations:continue
                base=run/'evidence/v4_semantics'/name;combined=[]
                for obs in observations:
                    p=base/obs['result'];child=read_json(p)
                    for d in child['detections']:
                        node,local=anchors[(name,obs['playback_index'],d['index'])]
                        d.update(robust_box(world_support(local,snapshot_h[node])))
                        if name=='road':d.update(valid=False,reason='surface mask; no volumetric object box')
                        d['map_revision']=snapshot_step
                        combined.append(dict(d,mask_path=str((Path(obs['result']).parent/d['mask_path']))))
                    obs['valid_boxes']=sum(d['valid'] for d in child['detections'])
                    write_json_atomic(p,child)
                representative=next((o for o in observations if o['mask_count']),observations[0]);child=read_json(base/representative['result'])
                result={'schema_version':3,'query_id':f'v4_live_{name}','query':name,'retrieval_score':0.,'submap_id':child['submap_id'],'frame_index':child['frame_index'],
                    'frame_image':str(Path(representative['result']).parent/'frame.png'),'detections':combined,'snapshot':{'step':snapshot_step,'phase':'after'},
                    'search':{'schema_version':3,'mode':'live','total_frames':len(processed),'inspected_frames':len(observations),'observations':observations,
                              'mask_count':len(combined),'valid_observations':sum(d['valid'] for d in combined),
                              'backend':'segformer' if name=='road' else config.get('backend'),
                              'model':str(config.get('surface_checkpoint' if name=='road' else 'checkpoint', '')),
                              'model_hash':detector.model_hash},
                    'limitations':['2D track IDs are not globally unique 3D objects','Dynamic candidates stay timestamped observations; no permanent static fusion','Relative scale; robust boxes are not GT geometry']}
                write_json_atomic(base/'result.json',result);paths[name]=str((base/'result.json').relative_to(run))
            write_json_atomic(folder/'semantic_results.json',{'revision':revision,'map_step':snapshot_step,'results':paths,'geometry_done':geometry_done,'sky_groups':sky_groups,'sky_frames':sky_frames})
            return paths
        last_publish=0;last_step=None;published_revision=-1
        while not stop.is_set():
            control=read_json(control_file,{})
            if control.get('stop'):break
            if control.get('run'):
                run=Path(control['run']);step=control.get('step')
                if step is not None and step!=snapshot_step:
                    with np.load(run/'snapshots'/str(step)/'after.npz') as d:
                        snapshot_h={int(n):h.copy() for n,h in zip(d['node_ids'],d['homographies'])}
                        snapshot_p={int(n):p.copy() for n,p in zip(d['node_ids'],d['projection_matrices'])}
                    snapshot_step=step;revision+=1
                events=complete_events(run/'events.jsonl');frames=[e for e in events if e['event_type']=='frame_selected']
                pending=[(i,e) for i,e in enumerate(frames) if str(e['source_frame_id']) not in processed and int(e['submap_id'])+read_json(run/e['asset_paths']['metadata'])['submap_frame_index'] in snapshot_h]
                if pending:
                    i,event=pending[0];start=time.monotonic();archive_frame(event,i);log('depth_join',source_frame_id=event['source_frame_id'],seconds=time.monotonic()-start,map_revision=snapshot_step)
                if time.monotonic()-last_publish>1 and (revision!=published_revision or snapshot_step!=last_step):
                    publish(control.get('geometry_done',False));last_publish=time.monotonic();last_step=snapshot_step;published_revision=revision
                if control.get('geometry_done') and not pending and live_done.is_set():publish(True);break
            if error:raise RuntimeError(error[0])
            report={'state':'running','message':'2D 검출과 깊이 관측 결합 중','classes':classes,**counts,'device':detector.device,'model_hash':detector.model_hash,'load_seconds':load_seconds,'map_step':snapshot_step,'revision':revision}
            write_json_atomic(stats_file,report)
            stop.wait(.05)
        stop.set();thread.join(timeout=2);live_thread.join(timeout=5)
        if error:raise RuntimeError(error[0])
        if read_json(control_file,{}).get('stop'):report.update(state='cancelled')
        else:
            paths=publish(True)
            for name,relative in paths.items():
                target=run/'evidence/query_jobs'/f'v4_{name}';target.mkdir(parents=True,exist_ok=True)
                write_json_atomic(target/'status.json',{'state':'completed','result':relative,'query':name,'message':'V4 resident worker complete'})
            report.update(state='completed',**counts)
        write_json_atomic(stats_file,report)
    except BaseException as exc:
        stop.set();write_json_atomic(stats_file,{'state':'failed','message':str(exc),**counts});raise
    finally:stop.set();store.close();timing.close()

if __name__=='__main__':main()
