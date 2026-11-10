"""Explicit current/candidate/sampled/full-run PE/SAM3 search with evidence."""
import argparse
import json
import os
from pathlib import Path
import site
import sys
import time

import numpy as np
import torch
import torchvision  # noqa: F401

root = Path(__file__).resolve().parents[1]
site.addsitedir(str(root/'.venv'/'lib'/f'python{sys.version_info.major}.{sys.version_info.minor}'/'site-packages'))
sys.path.insert(0, str(root))
from PIL import Image
from huggingface_hub import hf_hub_download
from vggt_slam.demo.object_query import boxes_from_masks, save_query_evidence
from vggt_slam.demo.search_policy import parse_queries, scope_frames, candidate_order
from vggt_slam.demo.search_assets import segmentation_source, mask_to_depth, confidence_percentile
from vggt_slam.demo.search_cache import cached_masks


class RecordedFrame:
    def __init__(self, points, valid):
        self.points, self.valid = points, valid

    def get_points_in_mask(self, frame_index, mask, graph):
        return self.points[self.valid & mask]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--query', required=True)
    parser.add_argument('--all-classes', action='store_true')
    parser.add_argument('--backend', choices=['sam3','yoloe','yolo26','yolo11','rfdetr'], default='sam3')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=['current','candidate','sampled','all'], default='candidate')
    parser.add_argument('--max-frames', type=int, default=48)
    parser.add_argument('--frame-index', type=int)
    parser.add_argument('--candidates', type=int, default=5)
    parser.add_argument('--stream-results', action='store_true', help='publish atomic partial results for Live V3')
    args = parser.parse_args()
    if args.all_classes and (args.backend not in ('rfdetr','yolo26','yolo11') or args.mode=='candidate'):
        parser.error('전체 클래스는 RF-DETR/YOLO26/YOLO11의 현재/표본/전수 범위에서 지원합니다.')
    queries = [{'label':'전체 객체','prompt':'*'}] if args.all_classes else parse_queries(args.query)
    if not 1 <= args.max_frames <= 512:
        parser.error('max-frames must be 1..512')
    args.run, args.output = args.run.resolve(), args.output.resolve()
    args.output.relative_to(args.run)
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output/'status.json').exists():
        parser.error('use a new output directory; existing evidence is preserved')
    started = time.monotonic()
    status = args.output/'status.json'
    partial = {}
    torch.set_num_threads(4)

    def progress(message, **extra):
        temporary = status.with_suffix('.tmp')
        temporary.write_text(json.dumps({'state':'running','message':message,'mode':args.mode,'query':args.query,'worker_pid':os.getpid(),**partial,**extra},ensure_ascii=False)+'\n')
        os.replace(temporary, status)
        print(message, flush=True)

    try:
        events = [json.loads(line) for line in (args.run/'events.jsonl').read_text().splitlines()]
        all_frames = [e for e in events if e['event_type']=='frame_selected']
        frames = [e for e in all_frames if not e.get('payload',{}).get('overlap')]
        current = all_frames[args.frame_index] if args.frame_index is not None and 0<=args.frame_index<len(all_frames) else None
        if not frames:
            raise ValueError('No recorded RGB/depth frames')
        frame_indexes = {e['asset_paths']['metadata']:i for i,e in enumerate(all_frames)}
        scores_by_prompt = {}
        if args.mode=='candidate':
            from core.vision_encoder import pe, transforms
            sampled = scope_frames(frames,'sampled',args.max_frames)
            progress(f'PE 후보 검색 · {len(sampled)}/{len(frames)} 프레임')
            encoder = pe.CLIP.from_config('PE-Core-L14-336',pretrained=True).eval().cpu()
            transform = transforms.get_image_transform(encoder.image_size)
            tokenizer = transforms.get_text_tokenizer(encoder.context_length)
            ranking_frames = sampled + ([current] if current and current['source_frame_id'] not in {f['source_frame_id'] for f in sampled} else [])
            with torch.inference_mode():
                vectors = torch.cat([encoder.encode_image(transform(Image.open(args.run/e['asset_paths']['rgb']).convert('RGB')).unsqueeze(0),normalize=True) for e in ranking_frames])
                texts = encoder.encode_text(tokenizer([q['prompt'] for q in queries]),normalize=True)
                scores = (vectors@texts.T).numpy()
            selected = []
            for j,q in enumerate(queries):
                scores_by_prompt[q['prompt']] = {f['source_frame_id']:float(s) for f,s in zip(ranking_frames,scores[:,j])}
                selected.extend(candidate_order(sampled,scores[:len(sampled),j],current,min(max(args.candidates,1),8)))
            selected = list({e['source_frame_id']:e for e in selected}.values())
            del vectors,texts,encoder
        else:
            selected = scope_frames(frames,args.mode,args.max_frames,current)
        progress(f'검색 준비 · {args.mode} · {len(selected)}/{len(frames)} 프레임 · {len(queries)} 검색어')
        model_name = 'SAM3 native RGB; PE only for candidate scope'
        if args.backend == 'sam3':
            checkpoint = hf_hub_download('facebook/sam3','sam3.pt',local_files_only=True)
            stat = Path(checkpoint).stat()
            model_identity = {'checkpoint':str(Path(checkpoint).resolve()),'size':stat.st_size,'mtime_ns':stat.st_mtime_ns,'torch':torch.__version__,'confidence':.5}
            processor = None
            encoded_image = None
            inference_state = None

            def infer(image,prompt):
                nonlocal processor,encoded_image,inference_state
                if processor is None:
                    from sam3.model_builder import build_sam3_image_model
                    from sam3.model.sam3_image_processor import Sam3Processor
                    model = build_sam3_image_model(device='cpu',checkpoint_path=checkpoint,load_from_HF=False)
                    processor = Sam3Processor(model,device='cpu')
                with torch.inference_mode():
                    if image is not encoded_image:
                        inference_state = processor.set_image(image)
                        encoded_image = image
                    output = processor.set_text_prompt(state=inference_state,prompt=prompt)
                return output['masks'].cpu().numpy(),output['scores'].cpu().numpy()
        else:
            from vggt_slam.demo.search_models import detector_inference
            infer, model_identity, model_name = detector_inference(root,args.backend,queries)
            if args.all_classes:
                queries=[{'label':name,'prompt':name} for name in model_identity['classes']]

        step = max(int(p.name) for p in (args.run/'snapshots').iterdir() if p.name.isdigit())
        with np.load(args.run/'snapshots'/str(step)/'after.npz') as snapshot:
            projections = {int(n):p.copy() for n,p in zip(snapshot['node_ids'],snapshot['projection_matrices'])}
        manifest = json.loads((args.run/'manifest.json').read_text())
        percentile = confidence_percentile(manifest)
        thresholds = {}
        observations,attempts,combined = [],[],[]
        found_prompts = set()
        aggregate_id = f'search_{time.time_ns()}'
        def assemble_result():
            inspected=len({o['source_frame_id'] for o in observations})
            representative=max(observations,key=lambda o:(o['valid_boxes'],o['mask_count']))
            child=json.loads((args.output/representative['result']).read_text())
            valid_count=sum(bool(d['valid']) for d in combined)
            result={'schema_version':3,'query_id':aggregate_id,'query':'전체 객체' if args.all_classes else args.query,'retrieval_score':child['retrieval_score'],
                    'submap_id':child['submap_id'],'frame_index':child['frame_index'],
                    'frame_image':str((Path(representative['result']).parent/child['frame_image'])),
                    'detections':combined,'snapshot':{'step':step,'phase':'after'},
                    'search':{'schema_version':3,'mode':args.mode,'queries':queries,'total_frames':len(frames),
                              'planned_frames':len(selected),'inspected_frames':inspected,'observations':observations,'attempts':attempts,
                              'mask_count':len(combined),'valid_observations':valid_count,'unique_object_count':None,
                              'all_classes':args.all_classes,'class_counts':{name:sum(d.get('query')==name for d in combined) for name in sorted({d.get('query') for d in combined})},
                              'source_run':str(args.run),'backend':args.backend,'model':model_name,
                              'current_frame_index':args.frame_index,'seconds':time.monotonic()-started},
                    'limitations':['Counts are frame observations, not unique tracked objects','No object-recall ground truth',
                                   '3D coordinates inherit projective reconstruction and unverified scale']}
            return result

        for index,event in enumerate(selected):
            meta = json.loads((args.run/event['asset_paths']['metadata']).read_text())
            sid = int(event['submap_id']);node=sid+meta['submap_frame_index']
            recorded = Image.open(args.run/event['asset_paths']['rgb']).convert('RGB')
            image,mapping,source_reason = segmentation_source(args.run,event,meta)
            with np.load(args.run/event['asset_paths']['depth']) as data:
                depth,confidence,valid=data['depth'],data['confidence'],data['valid']
            if sid not in thresholds:
                arrays=[]
                for path in (args.run/'submaps'/str(sid)/'frames').glob('*/depth.npz'):
                    with np.load(path) as data:arrays.append(data['confidence'])
                thresholds[sid]=float(np.percentile(np.stack(arrays),percentile)+1e-6)
            y,x=np.indices(depth.shape)
            pixels=np.stack((x*depth,y*depth,depth,np.ones_like(depth)),axis=-1)
            world=pixels@np.linalg.inv(projections[node]).T
            with np.errstate(divide='ignore',invalid='ignore'):points=world[...,:3]/world[...,3:]
            support=valid&(confidence>thresholds[sid])&np.isfinite(points).all(axis=2)
            frame_queries=queries
            if args.all_classes:
                active=infer.active_classes(image)
                frame_queries=[q for q in queries if q['prompt'] in active] or [{'label':'미검출','prompt':'__none__'}]
            for qindex,q in enumerate(frame_queries):
                if args.mode=='candidate' and q['prompt'] in found_prompts:continue
                progress(f'{args.backend.upper()} {index+1}/{len(selected)} · frame {event["source_frame_id"]} · {q["label"]}',completed_frames=index,total_frames=len(selected),mask_count=len(combined),valid_boxes=sum(bool(d['valid']) for d in combined))
                masks,scores,cache_hit,cache_key=cached_masks(args.run/'evidence/segmentation_cache_v3',image,q['prompt'],model_identity,infer)
                mapped=[mask_to_depth(mask,mapping,depth.shape) for mask in masks]
                detections=boxes_from_masks(RecordedFrame(points,support),0,None,mapped,scores)
                for d,mask in zip(detections,masks):
                    d['query']=q['label']
                    d['class_name']=q['prompt']
                    d['native_mask_pixels']=int(mask.sum())
                    if d.get('reason')=='empty mask' and mask.any():d['reason']='native mask outside recorded depth crop'
                folder=args.output/'observations'/f'{index:04d}'/str(qindex)
                score=scores_by_prompt.get(q['prompt'],{}).get(event['source_frame_id'],0.)
                path=save_query_evidence(q['label'],score,sid,meta['submap_frame_index'],recorded,detections,run_dir=folder)
                image.save(path.parent/'segmentation_input.png')
                for i,mask in enumerate(masks):Image.fromarray(np.uint8(mask)*255).save(path.parent/f'native_mask_{i:02d}.png')
                child=json.loads(path.read_text())
                count=sum(bool(d['valid']) for d in detections)
                item={'source_frame_id':event['source_frame_id'],'playback_index':frame_indexes[event['asset_paths']['metadata']],
                      'query':q['label'],'prompt':q['prompt'],'mask_count':len(masks),'valid_boxes':count,
                      'result':str(path.relative_to(args.output)),'source':source_reason,'native_size_wh':list(image.size),
                      'cache_hit':cache_hit,'cache_key':cache_key,'confidence_threshold':thresholds[sid]}
                observations.append(item)
                attempts.append(dict(item,result=str(path.relative_to(args.run))))
                for detection in child['detections']:
                    d=dict(detection,index=len(combined),query=q['label'],source_frame_id=event['source_frame_id'],
                           playback_index=item['playback_index'],submap_id=sid,submap_frame_index=meta['submap_frame_index'])
                    if d.get('mask_path'):d['mask_path']=str((path.parent/d['mask_path']).relative_to(args.output))
                    combined.append(d)
                if count:found_prompts.add(q['prompt'])
            if args.stream_results:
                from vggt_slam.demo.status import write_json_atomic
                write_json_atomic(args.output/'partial_result.json', assemble_result())
                partial['partial_result']=str((args.output/'partial_result.json').relative_to(args.run))
            progress(f'검사 완료 {index+1}/{len(selected)} 프레임',completed_frames=index+1,total_frames=len(selected),mask_count=len(combined),valid_boxes=sum(bool(d['valid']) for d in combined))
            if args.mode=='candidate' and len(found_prompts)==len(queries):break
        result=assemble_result()
        inspected=result['search']['inspected_frames']
        valid_count=result['search']['valid_observations']
        (args.output/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
        progress(f'검색 완료 · {inspected}/{len(frames)} 프레임 · 2D {len(combined)}건 / 3D {valid_count}건',
                 state='completed',result=str((args.output/'result.json').relative_to(args.run)),valid_boxes=valid_count,
                 mask_count=len(combined),attempted_frames=inspected,mode=args.mode,total_frames=len(frames),
                 elapsed_seconds=time.monotonic()-started)
    except Exception as exc:
        progress(str(exc),state='failed',error_type=type(exc).__name__)
        raise


if __name__=='__main__':main()
