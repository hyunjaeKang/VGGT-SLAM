"""V2 calibrated GPU point packets with dense foreground and stable background LOD."""
import hashlib
import threading
import struct
import numpy as np


def pack_points(points, colors):
    points=np.asarray(points,dtype='<f4').reshape(-1,3)
    colors=np.asarray(colors,dtype=np.uint8)
    if colors.shape==(3,):colors=np.tile(colors,(len(points),1))
    if colors.shape!=points.shape:raise ValueError('Point/color mismatch')
    return struct.pack('<4sIII',b'VGP2',len(points),16,16+points.nbytes)+points.tobytes()+colors.tobytes()


class DenseGPUScene:
    def __init__(self):
        self.lock=threading.RLock();self.epoch=0;self.key=None;self.data={};self.counts={};self.state={};self.uploads=0

    def update(self,run,step,phase,visible_nodes,frame_index,budget,hide_sky,threshold,color_mode,point_scale=1.,road_points=None,lines=None,road_colors=None):
        key=(str(run.path),step,phase,hide_sky,threshold,color_mode)
        with self.lock:
            if key!=self.key:
                self.key=key;self.epoch+=1;self.data={};self.counts={}
                if hasattr(self,'viser_handles'):
                    for handle in self.viser_handles.values():handle.remove()
                    self.viser_handles={};self.viser_counts={}
                with np.load(run.path/'snapshots'/str(step)/(phase+'.npz')) as snap:
                    self.matrices={int(n):h for n,h in zip(snap['node_ids'],snap['homographies'])}
            groups=[g for g in run.preview_groups if g[1] in set(visible_nodes) and g[1] in self.matrices]
            near={g[1] for g in groups[-3:]}
            active=[]
            for sid,node,local,colors in groups:
                name=f'{sid}_{node}_dense'
                if name not in self.data:
                    scores=run.sky_groups.get((sid,node)) if hide_sky else None
                    ids=np.flatnonzero(scores<threshold) if scores is not None else np.arange(len(local))
                    # Fixed deterministic spatial distribution: LOD changes only
                    # the GPU draw count, never the packet or its point order.
                    if len(ids):ids=ids[np.random.default_rng((sid*1000003+node) % (2**32)).permutation(len(ids))]
                    h=self.matrices[node];p=local[ids]
                    q=np.column_stack([p,np.ones(len(p))])@h.T
                    with np.errstate(divide='ignore',invalid='ignore'):xyz=q[:,:3]/q[:,3:]
                    good=np.isfinite(xyz).all(axis=1)
                    rgb=colors[ids][good] if color_mode=='RGB' else np.tile([(53*sid+90)%256,(97*sid+150)%256,(149*sid+200)%256],(int(good.sum()),1))
                    self.data[name]=pack_points(xyz[good],rgb);self.counts[name]=int(good.sum());self.uploads+=1
                active.append({'id':name,'count':self.counts[name],'kind':'points','near':node in near})
            remaining=int(budget)
            for priority in (True,False):
                subset=[a for a in active if a['near']==priority]
                count=sum(a['count'] for a in subset)
                allocation=min(remaining,count)
                weights=[a['count'] for a in subset]
                for a,n in zip(subset,weights):a['count']=int(allocation*n/max(1,count))
                spare=allocation-sum(a['count'] for a in subset)
                for a,n in zip(subset,weights):
                    if spare and a['count']<n:a['count']+=1;spare-=1
                remaining-=allocation
            total=sum(a['count'] for a in active)
            current={a['id'] for a in active}
            if road_points is not None and len(road_points):
                p=np.asarray(road_points)
                rgb=np.tile([34,197,94],(len(p),1)).astype(np.uint8) if road_colors is None else np.asarray(road_colors,np.uint8)
                if len(rgb)!=len(p):raise ValueError('semantic point/color mismatch')
                if len(p)>150000:
                    ids=np.linspace(0,len(p)-1,150000,dtype=int);p,rgb=p[ids],rgb[ids]
                name='road_'+hashlib.blake2s(p.tobytes()+rgb.tobytes(),digest_size=8).hexdigest()
                if name not in self.data:self.data[name]=pack_points(p,rgb);self.uploads+=1
                active.append({'id':name,'count':len(p),'kind':'points'})
            if lines is not None and len(lines):
                p=np.asarray(lines).reshape(-1,3)
                name='lines_'+hashlib.blake2s(p.tobytes(),digest_size=8).hexdigest()
                if name not in self.data:self.data[name]=pack_points(p,[255,100,70]);self.uploads+=1
                active.append({'id':name,'count':len(p),'kind':'lines'})
            for name in list(self.data):
                if name.startswith(('road_','lines_')) and name not in {a['id'] for a in active}:self.data.pop(name,None)
            self.state={'epoch':self.epoch,'chunks':active,'map_points':total,'point_scale':point_scale,'frame_index':frame_index,'uploads':self.uploads}
            return dict(self.state)

    def packet(self,epoch,name):
        with self.lock:
            return self.data.get(name) if epoch==self.epoch else None

    def snapshot(self):
        with self.lock:return dict(self.state)

    def sync_viser(self,scene,visible,point_size):
        """Use identical dense packets in free orbit; avoid duplicate GPU draws in RGB mode."""
        if not hasattr(self,'viser_handles'):self.viser_handles={};self.viser_counts={}
        with self.lock:
            keep={a['id'] for a in self.state.get('chunks',[]) if a['id'][0].isdigit()}
            for name,handle in list(self.viser_handles.items()):
                if name not in keep:
                    handle.remove();self.viser_handles.pop(name)
                else:
                    handle.visible=visible;handle.point_size=point_size
            if not visible:return
            counts={a['id']:a['count'] for a in self.state['chunks']}
            for name in keep:
                if name in self.viser_handles and self.viser_counts.get(name)==counts[name]:continue
                data=self.data[name];_,n,offset,color_offset=struct.unpack('<4sIII',data[:16])
                points=np.frombuffer(data,dtype='<f4',count=n*3,offset=offset).reshape(n,3)
                colors=np.frombuffer(data,dtype=np.uint8,count=n*3,offset=color_offset).reshape(n,3)
                points,colors=points[:counts[name]],colors[:counts[name]]
                if name in self.viser_handles:
                    self.viser_handles[name].points=points;self.viser_handles[name].colors=colors
                else:self.viser_handles[name]=scene.add_point_cloud('/dense_free/'+name,points=points,colors=colors,point_size=point_size,point_shape='circle')
                self.viser_counts[name]=counts[name]
