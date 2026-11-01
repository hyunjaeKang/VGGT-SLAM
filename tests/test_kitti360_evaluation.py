import numpy as np
import pytest

from scripts.evaluate_kitti360 import load_reference, match_frames


def test_kitti360_sparse_frame_ids_are_matched_without_interpolation(tmp_path):
    matrices = np.tile(np.eye(4), (3, 1, 1))
    matrices[:, :3, 3] = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    path = tmp_path / "cam0_to_world.txt"
    np.savetxt(path, np.column_stack([[1, 4, 9], matrices.reshape(3, 16)]))
    ids, loaded = load_reference(path)
    estimated = np.zeros((5, 8))
    estimated[:, 0] = [0, 1, 3, 4, 9]
    estimated[:, 7] = 1
    matched, positions = match_frames(estimated, ids, loaded)
    np.testing.assert_array_equal(matched[:, 0], [1, 4, 9])
    np.testing.assert_allclose(positions, matrices[:, :3, 3])


def test_kitti360_reference_rejects_imu_pose_format(tmp_path):
    path = tmp_path / "poses.txt"
    np.savetxt(path, np.zeros((3, 13)))
    with pytest.raises(ValueError, match="4x4"):
        load_reference(path)
