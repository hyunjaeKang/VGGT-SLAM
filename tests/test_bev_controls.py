import numpy as np
from vggt_slam.demo.bev import raster_bev


def test_zoom_changes_span_and_reset_is_exact():
    points = np.array([[0,0,0], [1,0,1], [2,0,2]], float)
    colors = np.full((3,3), 100, np.uint8)
    path = points.copy()
    first, a = raster_bev(points, colors, path)
    _, b = raster_bev(points, colors, path, zoom=2)
    reset, c = raster_bev(points, colors, path, zoom=1)
    assert b['span'] == a['span']/2
    assert c == a
    np.testing.assert_array_equal(first, reset)


def test_trajectory_visibility_does_not_move_map_bounds():
    points = np.array([[0,0,0],[2,0,2]],float)
    colors = np.full((2,3),100,np.uint8)
    path = np.array([[0,0,2],[2,0,0]],float)
    on, a = raster_bev(points,colors,path)
    off, b = raster_bev(points,colors,path,show_trajectory=False)
    assert a['span']==b['span'] and not b['trajectory_visible']
    assert np.any(on!=off)


def test_connectivity_is_optional_overlay_on_same_coordinate_frame():
    points = np.array([[0,0,0],[2,0,2]],float)
    colors = np.full((2,3),100,np.uint8)
    road = np.array([[0,0,0],[.015,0,0],[.03,0,0],[2,0,2]],float)
    base,a = raster_bev(points,colors,[],show_trajectory=False)
    overlay,b = raster_bev(points,colors,[],road_points=road,show_trajectory=False)
    assert a['span']==b['span']
    assert a['connectivity'] is None
    assert b['connectivity']['edges']>0
    assert np.any(base!=overlay)


def test_pan_moves_all_semantic_layers_without_changing_span():
    points=np.array([[0.,0,0],[1,0,1],[2,0,2]])
    colors=np.full((3,3),100,np.uint8)
    box=np.array([[[.2,0,.2],[.8,0,.2]]])
    first,a=raster_bev(points,colors,[],mask_points=points,boxes=[box])
    moved,b=raster_bev(points,colors,[],pan=(.1,.1),mask_points=points,boxes=[box])
    assert a['span']==b['span'] and b['pan']==[.1,.1]
    assert b['box_count']==1 and b['mask_cells']>0
    assert np.any(first!=moved)
