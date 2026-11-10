import os
import numpy as np
import torch
import open3d as o3d
from scipy.spatial.transform import Rotation as R
import matplotlib.pyplot as plt
from vggt_slam.slam_utils import decompose_camera, cosine_similarity
from vggt_slam.pcd_io import write_cloud_chunks

class GraphMap:
    def __init__(self):
        self.submaps = dict()
        self.rectifying_H_mats = []
        self.non_lc_submap_ids = []
    
    def get_num_submaps(self):
        return len(self.submaps)

    def add_submap(self, submap):
        submap_id = submap.get_id()
        self.submaps[submap_id] = submap
        if not submap.get_lc_status():
            self.non_lc_submap_ids.append(submap_id)
    
    def get_largest_key(self, ignore_loop_closure_submaps=False):
        """
        Get the largest key of the first node of any submap.
        Return: The largest key, or None if the dictionary is empty.
        """
        if len(self.submaps) == 0:
            return None
        if ignore_loop_closure_submaps:
            non_lc_keys = [key for key, submap in self.submaps.items() if not submap.get_lc_status()]
            return max(non_lc_keys)
        return max(self.submaps.keys())
    
    def get_submap(self, id):
        return self.submaps[id]

    def get_latest_submap(self, ignore_loop_closure_submaps=False):
        return self.get_submap(self.get_largest_key(ignore_loop_closure_submaps))

    def retrieve_best_semantic_frame(self, query_text_vector):
        overall_best_score = -np.inf
        overall_best_submap_id = 0
        overall_best_frame_index = 0
        # search for best image to target image
        sorted_keys = sorted(self.submaps.keys())
        for index, submap_key in enumerate(sorted_keys):
            submap = self.submaps[submap_key]
            if submap.get_lc_status():
                continue
            submap_embeddings = submap.get_all_semantic_vectors()
            if len(submap_embeddings) == 0:
                continue
            scores = []
            for index, embedding in enumerate(submap_embeddings):
                score = float(np.asarray(cosine_similarity(embedding, query_text_vector)).item())
                scores.append(score)
            
            best_score_id = np.argmax(scores)
            best_score = scores[best_score_id]

            if best_score > overall_best_score:
                overall_best_score = best_score
                overall_best_submap_id = submap_key
                overall_best_frame_index = best_score_id

        if not np.isfinite(overall_best_score):
            raise ValueError("No semantic embeddings are available in the map")
        return overall_best_score, overall_best_submap_id, overall_best_frame_index
    
    def retrieve_best_score_frame(self, query_vector, current_submap_id, ignore_last_submap=True, query_path=None):
        min_seconds = getattr(self, "loop_min_seconds", 0.)
        records = getattr(self, "loop_frame_records", {})
        query_time = None
        if min_seconds > 0:
            from pathlib import Path
            query_time = records.get(str(Path(query_path).resolve()), {}).get("timestamp") if query_path else None
            if query_time is None or not np.isfinite(query_time):
                raise ValueError("Temporal loop exclusion requires a finite query timestamp")
        overall_best_score = 1000
        overall_best_submap_id = 0
        overall_best_frame_index = 0
        # search for best image to target image
        sorted_keys = sorted(self.submaps.keys())
        for index, submap_key in enumerate(sorted_keys):
            if submap_key == current_submap_id:
                continue

            if self.non_lc_submap_ids and ignore_last_submap and submap_key == self.non_lc_submap_ids[-1]:
                continue

            else:
                submap = self.submaps[submap_key]
                if submap.get_lc_status():
                    continue
                submap_embeddings = submap.get_all_retrieval_vectors()
                if len(submap_embeddings) == 0:
                    continue
                scores = torch.linalg.vector_norm(submap_embeddings - query_vector, dim=1)
                if min_seconds > 0:
                    eligible = []
                    for i in range(len(scores)):
                        path = str(Path(submap.get_img_names_at_index(i)).resolve())
                        timestamp = records.get(path, {}).get("timestamp")
                        eligible.append(timestamp is not None and np.isfinite(timestamp) and abs(query_time - timestamp) >= min_seconds)
                    scores = scores.masked_fill(~torch.tensor(eligible, dtype=torch.bool, device=scores.device), float('inf'))
                best_score, best_score_id = torch.min(scores, dim=0)
                best_score = best_score.item()
                best_score_id = best_score_id.item()

                if best_score < overall_best_score:
                    overall_best_score = best_score
                    overall_best_submap_id = submap_key
                    overall_best_frame_index = best_score_id

        return overall_best_score, overall_best_submap_id, overall_best_frame_index

    def get_frames_from_loops(self, loops):
        frames = []
        for detected_loop in loops:
            frames.append(self.submaps[detected_loop.detected_submap_id].get_frame_at_index(detected_loop.detected_submap_frame))
        return frames
    
    def get_submaps(self):
        return self.submaps.values()

    def ordered_submaps_by_key(self):
        for k in sorted(self.submaps):
            yield self.submaps[k]
    
    def get_all_homographies(self, graph):
        homographies = []
        for submap in self.ordered_submaps_by_key():
            for pose_num in range(len(submap.poses)):
                id = int(submap.get_id() + pose_num)
                homographies.append(graph.get_homography(id))
        return np.stack(homographies)

    def get_all_cam_matricies(self, graph, give_camera_mat):
        cam_mats = []
        for submap in self.ordered_submaps_by_key():
            if submap.get_lc_status():
                continue
            poses = submap.get_all_poses_world(graph, give_camera_mat=give_camera_mat)
            cam_mats.append(poses)
        return np.vstack(cam_mats)

    def write_poses_to_file(self, file_name, graph, give_camera_mat=False, kitti_format=False):
        all_poses = self.get_all_cam_matricies(give_camera_mat=True, graph=graph)
        with open(file_name, "w") as f:

            if self.rectifying_H_mats:
                assert len(self.rectifying_H_mats) == len(all_poses), "Number of rectifying mats and number of poses do not match"
                print("Using rectifying homographies when writing poses to file.")
            count = 0
            written_frame_ids = set()
            for submap_index, submap in enumerate(self.ordered_submaps_by_key()):
                if submap.get_lc_status():
                    continue
                frame_ids = submap.get_frame_ids()
                print(frame_ids)
                for frame_index, frame_id in enumerate(frame_ids):
                    pose = all_poses[count]
                    count += 1
                    if frame_id in written_frame_ids:
                        continue
                    written_frame_ids.add(frame_id)
                    K, rotation_matrix, t, scale = decompose_camera(pose)
                    x, y, z = t
                    if kitti_format:
                        pose_matrix = np.eye(4)
                        pose_matrix[:3, :3] = rotation_matrix
                        pose_matrix[:3, 3] = t
                        output = pose_matrix.flatten()[:-4]
                        output = np.array([float(frame_id), *output])
                    else:
                        quaternion = R.from_matrix(rotation_matrix).as_quat() # x, y, z, w
                        output = np.array([float(frame_id), x, y, z, *quaternion])
                    f.write(" ".join(f"{v:.8f}" for v in output) + "\n")    

    def write_points_to_file(self, graph, file_name):
        def frame_chunks():
            for submap in self.ordered_submaps_by_key():
                for index, points in enumerate(submap.pointclouds):
                    mask = submap.get_conf_masks_frame(index) > submap.get_conf_threshold()
                    points = points[mask]
                    colors = submap.colors[index][mask]
                    homography = graph.get_homography(submap.get_id() + index)
                    numerator = points @ homography[:3, :3].T + homography[:3, 3]
                    denominator = points @ homography[3, :3] + homography[3, 3]
                    with np.errstate(divide="ignore", invalid="ignore"):
                        yield numerator / denominator[:, None], colors
        count = write_cloud_chunks(file_name, frame_chunks())
        print(f"Saved {count:,} points to {file_name}")
