"""Camera-relative V5 chase view, independent of arbitrary world scale/up."""
import numpy as np
from scipy.spatial.transform import Rotation


def travel_scale(positions):
    positions=np.asarray(positions,float)
    if positions.ndim!=2 or positions.shape[1]!=3:raise ValueError('Expected camera centres Nx3')
    steps=np.linalg.norm(np.diff(positions,axis=0),axis=1)
    steps=steps[np.isfinite(steps)&(steps>1e-10)]
    return float(np.median(steps)) if len(steps) else .04


def chase_pose(camera,distance,height_ratio=.35):
    if not np.isfinite(distance) or distance<=0:raise ValueError('Positive chase distance required')
    forward=np.asarray(camera['forward'],float);forward=forward/np.linalg.norm(forward)
    up=np.asarray(camera['up'],float);up=up/np.linalg.norm(up)
    position=np.asarray(camera['position'],float)-forward*distance+up*distance*height_ratio
    target=np.asarray(camera['position'],float)+forward*distance*2
    direction=target-position;direction/=np.linalg.norm(direction)
    right=np.cross(direction,up);right/=np.linalg.norm(right)
    view_up=np.cross(right,direction)
    rotation=np.column_stack((right,-view_up,direction))
    return {'position':position,'forward':direction,'up':view_up,'look_at':target,
            'wxyz':Rotation.from_matrix(rotation).as_quat()[[3,0,1,2]],
            'fov':float(np.clip(max(camera['fov'],np.radians(50)),np.radians(50),np.radians(65)))}
