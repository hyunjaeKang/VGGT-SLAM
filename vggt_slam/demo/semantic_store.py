"""V4 single-writer observation index and projective local-anchor geometry."""
import hashlib
import json
import sqlite3
import threading
from pathlib import Path

import numpy as np


def frame_uid(run_id, source_id, image_hash, orientation=0):
    return hashlib.sha256(json.dumps([run_id,str(source_id),image_hash,orientation],separators=(',',':')).encode()).hexdigest()


def world_support(local, homography):
    local=np.asarray(local,float).reshape(-1,3)
    q=np.column_stack([local,np.ones(len(local))])@np.asarray(homography).T
    with np.errstate(divide='ignore',invalid='ignore'):xyz=q[:,:3]/q[:,3:]
    return xyz[np.isfinite(xyz).all(axis=1)].astype(np.float32)


def robust_box(points, minimum=8):
    """Quantile support bounds; reject degenerate clouds and never invent depth."""
    points=np.asarray(points,float).reshape(-1,3)
    points=points[np.isfinite(points).all(axis=1)]
    if len(points)<minimum:return {'valid':False,'reason':'insufficient valid depth','point_count':len(points)}
    center=np.median(points,axis=0)
    _,singular,v=np.linalg.svd(points-center,full_matrices=False)
    if np.count_nonzero(singular>max(points.shape)*np.finfo(float).eps*singular[0])<3:
        return {'valid':False,'reason':'degenerate support','point_count':len(points)}
    basis=v.T
    if np.linalg.det(basis)<0:basis[:,-1]*=-1
    projected=(points-center)@basis
    low,high=np.quantile(projected,[.02,.98],axis=0)
    return {'valid':True,'center':(center+basis@((low+high)/2)).tolist(),
            'extent':(high-low).tolist(),'rotation':basis.tolist(),'point_count':len(points),
            'fit':'PCA 2-98% quantile; relative unverified scale'}


class SemanticStore:
    """Exactly one worker writes; viewer/controller use immutable JSON snapshots."""
    def __init__(self, folder):
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock()
        self.db=sqlite3.connect(self.folder/'semantic_state.sqlite',check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS observations (uid TEXT PRIMARY KEY,source_id TEXT,class_name TEXT,payload TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS frames (uid TEXT PRIMARY KEY,payload TEXT)')
        self.stream=(self.folder/'semantic_observations.jsonl').open('a')
    def add(self, uid, source_id, class_name, payload):
        with self.lock:
            row=self.db.execute('INSERT OR IGNORE INTO observations VALUES(?,?,?,?)',(uid,str(source_id),class_name,json.dumps(payload,allow_nan=False)))
            if not row.rowcount:return False
            self.db.commit();self.stream.write(json.dumps({'uid':uid,'source_frame_id':str(source_id),'class_name':class_name,**payload},allow_nan=False)+'\n');self.stream.flush();return True
    def record_frame(self,uid,payload):
        with self.lock:
            self.db.execute('INSERT OR IGNORE INTO frames VALUES(?,?)',(uid,json.dumps(payload,allow_nan=False)));self.db.commit()
    def close(self):self.stream.close();self.db.close()


def visible_detections(detections, frame_index):
    """Dynamic candidates stay on their timestamp; static history can accumulate."""
    return [d for d in detections if d.get('playback_index',frame_index)<=frame_index
            and (d.get('dynamic_state')!='possible' or d.get('playback_index')==frame_index)]
