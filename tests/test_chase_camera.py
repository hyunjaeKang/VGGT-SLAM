import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from vggt_slam.demo.chase_camera import chase_pose,travel_scale


def camera():return {'position':np.array([1.,2.,3.]),'forward':np.array([0.,0.,1.]),'up':np.array([0.,-1.,0.]),'fov':.3}


def test_chase_is_behind_above_and_looks_ahead():
    source=camera();view=chase_pose(source,2.)
    assert np.dot(view['position']-source['position'],source['forward'])<0
    assert np.dot(view['position']-source['position'],source['up'])>0
    np.testing.assert_allclose(view['look_at'],source['position']+source['forward']*4)
    rotation=Rotation.from_quat(view['wxyz'][[1,2,3,0]]).as_matrix()
    np.testing.assert_allclose(rotation[:,2],view['forward'],atol=1e-12)
    np.testing.assert_allclose(-rotation[:,1],view['up'],atol=1e-12)


def test_chase_preserves_camera_relative_up_under_arbitrary_world_rotation():
    source=camera();view=chase_pose(source,2.)
    rotation=Rotation.from_euler('xyz',[130,50,-30],degrees=True).as_matrix()
    rotated={**source,**{key:rotation@source[key] for key in ['position','forward','up']}}
    result=chase_pose(rotated,2.)
    for key in ['position','forward','up','look_at']:np.testing.assert_allclose(result[key],rotation@view[key],atol=1e-12)


def test_chase_scale_is_relative_and_robust_to_a_large_jump():
    positions=np.column_stack([np.arange(20)*.02,np.zeros((20,2))]);positions[10]*=100000
    distance=travel_scale(positions)
    assert distance==pytest.approx(.02)
    assert travel_scale(positions*3)==pytest.approx(distance*3)
    source=camera();scaled={**source,'position':source['position']*3}
    np.testing.assert_allclose(chase_pose(scaled,6)['position'],chase_pose(source,2)['position']*3)


@pytest.mark.parametrize('distance',[0,-1,float('nan')])
def test_chase_rejects_invalid_distance(distance):
    with pytest.raises(ValueError):chase_pose(camera(),distance)
