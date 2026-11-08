"""V2 playback clock, immutable map chunks and illustrative camera interpolation."""
import json
import threading
import time
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation, Slerp
from vggt_slam.demo.camera_view import rgb_camera


class PlaybackClock:
    def __init__(self, times, now=time.monotonic):
        self.times = np.asarray(times, float)
        if not len(self.times) or not np.isfinite(self.times).all() or np.any(np.diff(self.times)<0):
            raise ValueError('Expected nondecreasing finite frame times')
        self.now, self.lock = now, threading.RLock()
        self.anchor, self.epoch, self.playing = 0., now(), False
        self.duration = max(float(self.times[-1]), .001)

    def position(self):
        with self.lock:
            return min(self.duration, max(0., self.anchor + (self.now()-self.epoch if self.playing else 0.)))

    def seek(self, seconds, playing=None):
        seconds = float(seconds)
        if not np.isfinite(seconds): raise ValueError('Invalid playback time')
        with self.lock:
            self.anchor, self.epoch = min(self.duration,max(0.,seconds)), self.now()
            if playing is not None:self.playing=bool(playing)

    def set_playing(self, playing):
        self.seek(self.position(), playing)

    def target(self):
        return int(np.clip(np.searchsorted(self.times,self.position(),side='right')-1,0,len(self.times)-1))


def frame_times(run, source_fps=10.):
    if not np.isfinite(source_fps) or source_fps<=0:raise ValueError('Invalid source FPS')
    if not run.frames:return np.array([0.]), 'No recorded RGB frames; playback unavailable'
    metadata=[json.loads((run.path/e['asset_paths']['metadata']).read_text()) for e in run.frames]
    timestamps=[m.get('source_timestamp') for m in metadata]
    if all(isinstance(t,(int,float)) for t in timestamps) and np.all(np.diff(timestamps)>=0):
        return np.asarray(timestamps)-timestamps[0], 'recorded timestamps'
    ids=np.array([int(e['source_frame_id']) for e in run.frames])
    if np.any(np.diff(ids)<0):raise ValueError('Source frame IDs must be monotonic for FPS fallback')
    return (ids-ids[0])/source_fps, f'explicit source FPS {source_fps:g}; timestamps unavailable'


class CameraPath:
    def __init__(self, run, step, phase, times):
        with np.load(run.path/'snapshots'/str(step)/(phase+'.npz')) as data:
            cameras={int(n):p for n,p in zip(data['node_ids'],data['projection_matrices'])}
        samples={}
        for i,event in enumerate(run.frames):
            meta=json.loads((run.path/event['asset_paths']['metadata']).read_text())
            node=int(event['submap_id'])+meta['submap_frame_index']
            if node in cameras:samples[float(times[i])]=rgb_camera(cameras[node],tuple(meta['resolution_hw']))
        self.times=np.array(sorted(samples))
        self.samples=[samples[t] for t in self.times]
        self.slerp=Slerp(self.times,Rotation.from_quat([s['wxyz'][[1,2,3,0]] for s in self.samples])) if len(self.times)>1 else None

    def at(self, seconds):
        if not len(self.times):return None
        t=float(np.clip(seconds,self.times[0],self.times[-1]))
        i=max(0,min(len(self.times)-2,int(np.searchsorted(self.times,t,side='right')-1)))
        if self.slerp is None:return self.samples[0]
        alpha=(t-self.times[i])/(self.times[i+1]-self.times[i])
        a,b=self.samples[i:i+2]
        rotation=self.slerp(t)
        matrix=rotation.as_matrix()
        return {'position':a['position']*(1-alpha)+b['position']*alpha,
                'wxyz':rotation.as_quat()[[3,0,1,2]],'up':-matrix[:,1],
                'forward':matrix[:,2], 'fov':a['fov']*(1-alpha)+b['fov']*alpha}


class PersistentMap:
    def __init__(self, scene):
        self.scene, self.key, self.handles = scene,None,{}
        self.uploads=0

    def update(self, run, step, phase, visible_nodes, point_size, hide_sky, threshold, color_mode):
        key=(str(run.path),step,phase,hide_sky,threshold,color_mode)
        if key!=self.key:
            for h in self.handles.values():h.remove()
            self.handles={};self.key=key
            with np.load(run.path/'snapshots'/str(step)/(phase+'.npz')) as data:
                self.matrices={int(n):h.copy() for n,h in zip(data['node_ids'],data['homographies'])}
        visible=set(visible_nodes)
        for (sid,node),handle in self.handles.items():
            handle.visible=node in visible
            handle.point_size=point_size
        for sid,node,local,colors in run.preview_groups:
            if node not in visible or node not in self.matrices or (sid,node) in self.handles:continue
            scores=run.sky_groups.get((sid,node)) if hide_sky else None
            ids=np.flatnonzero(scores<threshold) if scores is not None else np.arange(len(local))
            if not len(ids):continue
            ids=ids[np.linspace(0,len(ids)-1,min(1000,len(ids)),dtype=int)]
            h=self.matrices[node];p=local[ids]
            q=np.column_stack([p,np.ones(len(p))])@h.T
            with np.errstate(divide='ignore',invalid='ignore'):xyz=q[:,:3]/q[:,3:]
            good=np.isfinite(xyz).all(axis=1)
            rgb=colors[ids][good] if color_mode=='RGB' else np.tile([(53*sid+90)%256,(97*sid+150)%256,(149*sid+200)%256],(good.sum(),1))
            self.handles[sid,node]=self.scene.add_point_cloud(f'/smooth_map/{sid}/{node}',points=xyz[good].astype(np.float32),colors=rgb.astype(np.uint8),point_size=point_size,point_shape='circle')
            self.uploads+=1

    def hide(self):
        for handle in self.handles.values():handle.visible=False
