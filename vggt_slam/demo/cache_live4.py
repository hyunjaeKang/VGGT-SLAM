"""Append-only committed map cache for V4; previously loaded previews stay resident."""
import json
from pathlib import Path
import numpy as np
from vggt_slam.demo.cache import CachedRun
from vggt_slam.demo.live_studio import committed_events


class IncrementalRun(CachedRun):
    def __init__(self,path,use_dense=True):
        super().__init__(path,use_dense=use_dense)
        self.preview_loads=len(self.previews)
        self.loaded_sky=set();self.sky_revision=0
    def refresh_committed(self):
        events=committed_events(self.path)
        if len(events)<len(self.events):raise ValueError('Committed stream went backwards')
        if self.events and events[len(self.events)-1]!=self.events[-1]:raise ValueError('Run event prefix changed')
        incoming=events[len(self.events):]
        for event in incoming:
            if event['event_type']=='frame_selected':self.frames.append(event)
            if event['event_type']=='submap_preview_saved':
                with np.load(self.path/event['asset_paths']['preview']) as d:
                    sid=int(event['submap_id']);local=d['points'].copy();rgb=d['colors'].copy();nodes=d['node_ids'].copy()
                self.previews.append((sid,local,rgb,nodes));self.preview_loads+=1
                edges=[0,*list(np.flatnonzero(nodes[1:]!=nodes[:-1])+1),len(nodes)]
                for a,b in zip(edges[:-1],edges[1:]):
                    if b>a:self.preview_groups.append((sid,int(nodes[a]),local[a:b],rgb[a:b]))
        self.events=events
        self.steps=sorted({int(e['payload']['step']) for e in events if e['event_type']=='optimization_finished'})
        self.manifest=json.loads((self.path/'manifest.json').read_text())
        return len(incoming)
    def refresh_sky(self,groups,frames):
        for key,relative in groups.items():
            if key in self.loaded_sky:continue
            sid,node=map(int,key.split('_'))
            with np.load(self.path/relative) as d:scores=d['scores'].copy()
            source=next((p for s,n,p,_ in self.preview_groups if s==sid and n==node),None)
            if source is None:continue
            if len(source)!=len(scores):raise ValueError('Semantic sky/preview count mismatch')
            self.sky_groups[(sid,node)]=scores;self.loaded_sky.add(key);self.sky_revision+=1
        if self.loaded_sky:
            self.sky_index={'status':'live','frames':frames,'model':'SegFormer Cityscapes labels'}
            self.sky_dir=self.path
