import json

import numpy as np

from vggt_slam.demo.road import RoadLayer, best_road_query, connectivity_grid, raster_connectivity


def test_connectivity_does_not_bridge_unobserved_gaps_or_diagonal_cells():
    # Extent 7 => one unit per cell with cells=8.
    pts = np.array([[0,0,0],[1,0,0],[3,0,0],[4,0,1],[7,0,7]], float)
    grid = connectivity_grid(pts, cells=8)
    assert len(grid['nodes_yx']) == 5
    assert len(grid['edges']) == 1
    assert grid['component_count'] == 4
    assert not grid['counts'][0, 2]


def test_connectivity_empty_and_nonfinite_inputs():
    grid = connectivity_grid(np.array([[np.nan, 0, 0]]))
    assert len(grid['edges']) == 0 and grid['component_count'] == 0
    image, stats = raster_connectivity(np.empty((0,3)), np.empty((0,3)))
    assert image.shape == (480,480,3) and stats['occupied_cells'] == 0
    assert (image[200,200] == [15,23,42]).all()


def test_road_query_prefers_coverage_and_excludes_other_classes():
    def q(ident, count, prompt):
        return {'query_id':ident,'search':{'inspected_frames':count,'observations':[{'prompt':prompt}]}}
    full = q('full',226,'road')
    assert best_road_query([q('car',999,'car'),full,q('later',1,'road')]) is full
    assert best_road_query([]) is None


def test_road_world_uses_projective_snapshot_and_excludes_future_nodes(tmp_path):
    folder = tmp_path/'snapshots/1'
    folder.mkdir(parents=True)
    before = np.eye(4)
    after = np.eye(4)
    after[0,3] = 2
    after[3,0] = .1
    np.savez(folder/'before.npz', node_ids=[0], homographies=[before])
    np.savez(folder/'after.npz', node_ids=[0,1], homographies=[after,after])
    layer = RoadLayer.__new__(RoadLayer)
    layer.groups = [(0,0,np.array([[1,2,3.]])),(2,1,np.array([[4,5,6.]]))]
    layer._snapshot_key = None
    layer._world_groups = []
    run = type('Run',(),{'path':tmp_path})()
    assert len(layer.world(run,1,'after',0)) == 1
    np.testing.assert_allclose(layer.world(run,1,'after',0)[0],[3/1.1,2/1.1,3/1.1])
    assert len(layer.world(run,1,'after',2)) == 2
    assert len(layer.world(run,1,'after',2,only_frame=0)) == 1
    assert len(layer.world(run,1,'after',0,only_frame=2)) == 0
    assert len(layer.world(run,1,'before',2)) == 1
