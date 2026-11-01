import os
from pathlib import Path
import time
import argparse
import hashlib
import json

# PyTorch 2.3 lacks a few MPS image operators; use CPU for those operators.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import numpy as np
import torch
from torchvision.transforms.functional import to_pil_image
from tqdm.auto import tqdm
import cv2
import matplotlib.pyplot as plt

import vggt_slam.slam_utils as utils
from vggt_slam.solver import Solver
from vggt_slam.submap import Submap

from vggt.models.vggt import VGGT
from vggt_slam.runtime import select_device, model_dtype, validate_args

parser = argparse.ArgumentParser(description="VGGT-SLAM demo")
parser.add_argument("--headless", action="store_true", help="Compute and save results without starting or updating a viewer")
parser.add_argument("--keep_alive", action="store_true", help="Keep the Viser viewer available after reconstruction until Ctrl+C")
parser.add_argument("--image_folder", type=str, default="examples/kitchen/images/", help="Path to folder containing images")
parser.add_argument("--device", choices=("auto", "cuda", "mps", "cpu"), default="auto", help="Inference device (auto: CUDA, then Apple MPS, then CPU)")
parser.add_argument("--vis_map", action="store_true", help="Visualize point cloud in viser as it is being build, otherwise only show the final map")
parser.add_argument("--vis_imgs", action="store_true", help="Show camera images in the viser frustums. By default only the frustums are shown (faster visualization)")
parser.add_argument("--vis_voxel_size", type=float, default=None, help="Voxel size for downsampling the point cloud in the viewer (e.g. 0.05 for 5 cm). Default: no downsampling")
parser.add_argument("--run_os", action="store_true", help="Enable open-set semantic search with Perception Encoder CLIP and SAM3")
parser.add_argument("--vis_flow", action="store_true", help="Visualize Lucas-Kanade optical flow for keyframe selection")
parser.add_argument("--log_results", action="store_true", help="save txt file with results")
parser.add_argument("--skip_dense_log", action="store_true", help="by default, logging poses and logs dense point clouds. If this flag is set, dense logging is skipped")
parser.add_argument("--log_path", type=str, default="poses.txt", help="Path to save the log file")
parser.add_argument("--submap_size", type=int, default=16, help="Number of new frames per submap, does not include overlapping frames or loop closure frames")
parser.add_argument("--overlapping_window_size", type=int, default=1, help="ONLY DEFAULT OF 1 SUPPORTED RIGHT NOW. Number of overlapping frames, which are used in SL(4) estimation")
parser.add_argument("--max_loops", type=int, default=1, help="ONLY DEFAULT OF 1 SUPPORTED RIGHT NOW or 0 to disable loop closures.")
parser.add_argument("--min_disparity", type=float, default=50, help="Minimum disparity to generate a new keyframe")
parser.add_argument("--conf_threshold", type=float, default=25.0, help="Initial percentage of low-confidence points to filter out")
parser.add_argument("--lc_thres", type=float, default=0.95, help="Threshold for image retrieval. Range: [0, 1.0]. Higher = more loop closures")
parser.add_argument("--demo_run", type=Path, default=None, help="Record into an unused prepared offline demo run (requires --headless)")
parser.add_argument("--use_all_selected_frames", action="store_true", help="Use each prepared frame without a second optical-flow selection; requires --demo_run")


def main():
    """
    Main function that wraps the entire pipeline of VGGT-SLAM.
    """
    args = parser.parse_args()
    if args.use_all_selected_frames and args.demo_run is None:
        parser.error("--use_all_selected_frames requires --demo_run")
    if args.demo_run is None:
        return run_pipeline(args)

    from vggt_slam.demo.recording import Recorder
    from vggt_slam.demo.status import transition, write_json_atomic

    run_dir = args.demo_run.resolve(strict=True)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["source_mode"] != "offline_compute" or manifest["status"] != "prepared":
        parser.error("--demo_run requires a prepared offline_compute run")
    if not args.headless or args.run_os or args.keep_alive:
        parser.error("--demo_run requires --headless without --run_os or --keep_alive")
    if (run_dir / "events.jsonl").exists():
        parser.error("demo run already contains events; create a new run")
    args.log_results = True
    args.log_path = str(run_dir / "poses.txt")
    manifest["execution_args"] = {key: str(value) if isinstance(value, Path) else value
                                  for key, value in vars(args).items()}
    write_json_atomic(manifest_path, manifest)
    recorder = None
    started = False
    try:
        device = select_device(args.device)
        transition(run_dir, "running", device=str(device), models={
            "vggt": {"checkpoint_url": "https://huggingface.co/facebook/VGGT-1B/resolve/main/model.pt"},
            "salad": {"checkpoint_url": "https://github.com/serizba/salad/releases/download/v1.0.0/dino_salad.ckpt"},
        })
        started = True
        recorder = Recorder(run_dir)
        run_pipeline(args, recorder)
        recorder.event("run_completed")
        manifest = json.loads(manifest_path.read_text())
        for key, name in (("events", "events.jsonl"), ("stdout", "stdout.log"), ("poses", "poses.txt"),
                          ("point_cloud", "poses_points.pcd"), ("camera_matrices", "poses_camera_matrices.npz")):
            if (run_dir / name).is_file():
                manifest["assets"][key] = name
        write_json_atomic(manifest_path, manifest)
        transition(run_dir, "completed")
    except BaseException as exc:
        if started:
            if recorder is not None:
                recorder.event("run_failed", payload={"error": str(exc) or type(exc).__name__})
        transition(run_dir, "failed", error=str(exc) or type(exc).__name__)
        raise
    finally:
        if recorder is not None:
            recorder.close()


def run_pipeline(args, recorder=None):
    validate_args(parser, args)
    if args.headless and (args.vis_map or args.keep_alive or args.run_os or args.vis_imgs or args.vis_flow):
        parser.error("--headless cannot be combined with visualization or --run_os flags")

    # Validate input before loading models or downloading checkpoints.
    selected_frames = {}
    if recorder is not None:
        selection = json.loads((recorder.run_dir / "selection.json").read_text())
        manifest = json.loads((recorder.run_dir / "manifest.json").read_text())
        digest = hashlib.sha256(json.dumps(selection, sort_keys=True).encode()).hexdigest()
        if digest != manifest["selection_sha256"]:
            raise ValueError("selection checksum mismatch")
        image_names = [frame["source"] for frame in selection["frames"]]
        selected_frames = {frame["source"]: frame for frame in selection["frames"]}
        if len(selected_frames) != len(image_names) or any(not Path(name).is_file() for name in image_names):
            raise ValueError("selection contains duplicate or missing image paths")
        args.log_results = True
        args.log_path = str(recorder.run_dir / "poses.txt")
    else:
        image_dir = Path(args.image_folder)
        if not image_dir.is_dir():
            parser.error(f"Image folder does not exist: {image_dir}")
        image_names = utils.sort_images_by_number([
            str(path) for path in image_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
            and "depth" not in path.stem.lower()
        ])
    if not image_names:
        parser.error(f"No supported RGB images found in {image_dir}")
    use_optical_flow_downsample = not args.use_all_selected_frames
    device = select_device(args.device)
    print(f"Using device: {device}")

    solver = Solver(
        init_conf_threshold=args.conf_threshold,
        lc_thres=args.lc_thres,
        vis_voxel_size=args.vis_voxel_size,
        vis_imgs=args.vis_imgs,
        device=device,
        enable_viewer=not args.headless
    )
    if recorder is not None:
        solver.demo_recorder = recorder

    print("Initializing and loading VGGT model...")


    if args.run_os:
        from sam3.model_builder import build_sam3_image_model
        from sam3.model.sam3_image_processor import Sam3Processor
        import core.vision_encoder.pe as pe
        import core.vision_encoder.transforms as transforms

        sam3_model = build_sam3_image_model()
        processor = Sam3Processor(sam3_model, confidence_threshold=0.50)

        clip_model = pe.CLIP.from_config("PE-Core-L14-336", pretrained=True)  # Downloads from HF
        clip_model = clip_model.to(device)
        clip_tokenizer = transforms.get_text_tokenizer(clip_model.context_length)
        clip_preprocess = transforms.get_image_transform(clip_model.image_size)
    else:
        clip_model, clip_preprocess = None, None
        clip_tokenizer = None

    model = VGGT()
    _URL = "https://huggingface.co/facebook/VGGT-1B/resolve/main/model.pt"
    model.load_state_dict(torch.hub.load_state_dict_from_url(_URL, map_location="cpu"))

    model.eval()
    model = model.to(device=device, dtype=model_dtype(device))

    source_label = f"prepared selection in {recorder.run_dir}" if recorder else args.image_folder
    print(f"Found {len(image_names)} images in {source_label}")

    image_names_subset = []
    count = 0
    image_count = 0
    total_time_start = time.time()
    keyframe_time = utils.Accumulator()
    backend_time = utils.Accumulator()
    for image_name in tqdm(image_names):
        if use_optical_flow_downsample:
            with keyframe_time:
                img = cv2.imread(image_name)
                if img is None:
                    raise ValueError(f"Cannot read image: {image_name}")
                enough_disparity = solver.flow_tracker.compute_disparity(img, args.min_disparity, args.vis_flow)
                if enough_disparity:
                    image_names_subset.append(image_name)
                    image_count += 1
        else:
            image_names_subset.append(image_name)
            image_count += 1

        # Run submap processing if enough images are collected or if it's the last group of images.
        if (len(image_names_subset) == args.submap_size + args.overlapping_window_size
                or (image_name == image_names[-1]
                    and (count == 0 or len(image_names_subset) > args.overlapping_window_size))):
            count += 1
            print(image_names_subset)
            t1 = time.time()
            predictions = solver.run_predictions(image_names_subset, model, args.max_loops, clip_model, clip_preprocess)
            print("Solver total time", time.time()-t1)
            print(count, "submaps processed")

            solver.add_points(predictions)
            if recorder is not None:
                recorder.record_submap(solver.current_working_submap.get_id(),
                                       [selected_frames[name] for name in image_names_subset], predictions,
                                       overlap_count=args.overlapping_window_size if count > 1 else 0)
                from vggt_slam.demo.graph_recording import record_preview
                record_preview(solver.current_working_submap, recorder)

            with backend_time:
                if recorder is None:
                    solver.graph.optimize()
                else:
                    from vggt_slam.demo.graph_recording import optimize_recorded
                    optimize_recorded(solver.graph, solver.map, recorder, count)

            loop_closure_detected = len(predictions["detected_loops"]) > 0
            if args.vis_map and not args.headless:
                if loop_closure_detected:
                    solver.update_all_submap_vis()
                else:
                    solver.update_latest_submap_vis()
            
            # Reset for next submap.
            image_names_subset = image_names_subset[-args.overlapping_window_size:]

    total_time = time.time() - total_time_start
    average_fps = total_time / image_count
    print(image_count, "frames processed")
    print("Total time:", total_time)
    print(f"Total time for VGGT calls: {solver.vggt_timer.total_time:.4f}s")
    print("Average VGGT time per frame:", solver.vggt_timer.total_time / image_count)
    print("Average loop closure time per frame:", solver.loop_closure_timer.total_time / image_count)
    print("Average keyframe selection time per frame:", keyframe_time.total_time / image_count)
    print("Average backend time per frame:", backend_time.total_time / image_count)
    print("Average semantic time per frame:", solver.clip_timer.total_time / image_count)
    print("Average total time per frame:", total_time / image_count)
    print("Average FPS:", 1 / average_fps)
        
    print("Total number of submaps in map", solver.map.get_num_submaps())
    print("Total number of loop closures in map", solver.graph.get_num_loops())


    if not args.vis_map and not args.headless:
        solver.update_all_submap_vis()

    if args.log_results:
        Path(args.log_path).parent.mkdir(parents=True, exist_ok=True)
        if not args.skip_dense_log:
            # Log the full point cloud as one file
            log_path = Path(args.log_path)
            solver.map.write_points_to_file(solver.graph, str(log_path.with_name(log_path.stem + "_points.pcd")))
        # Preserve projective cameras before converting them to quaternions.
        frame_ids = [frame_id for submap in solver.map.ordered_submaps_by_key()
                     if not submap.get_lc_status() for frame_id in submap.get_frame_ids()]
        log_path = Path(args.log_path)
        np.savez_compressed(log_path.with_name(log_path.stem + "_camera_matrices.npz"),
                            frame_ids=np.asarray(frame_ids),
                            projection_matrices=solver.map.get_all_cam_matricies(solver.graph, give_camera_mat=True))
        solver.map.write_poses_to_file(args.log_path, solver.graph, kitti_format=False)
        print(f"Results saved to {args.log_path}")


    if args.run_os:
        # Register the viser object-query panel so the user can search for
        # objects in the viewer in addition to the terminal prompt below.
        import threading
        data_lock = threading.Lock()
        solver.viewer.add_object_query_gui(solver, clip_model, clip_tokenizer, processor, data_lock)

        while True:
            # Prompt user for text input
            query = input("\nEnter text query or q to quit: ").strip()
            if len(query) == 0:
                print("Empty query. Exiting.")
                return
            
            if query == "q":
                print("Exiting.")
                return
            
            text_emb = utils.compute_text_embeddings(clip_model, clip_tokenizer, query)
            overall_best_score, overall_best_submap_id, overall_best_frame_index = solver.map.retrieve_best_semantic_frame(text_emb)

            found_submap = solver.map.get_submap(overall_best_submap_id)

            # Display image
            best_img = found_submap.get_frame_at_index(overall_best_frame_index)
            print("Score:", overall_best_score)
            with torch.no_grad():
                # convert torch image to PIL
                best_img = to_pil_image(best_img)
                inference_state = processor.set_image(best_img)
                output = processor.set_text_prompt(state=inference_state, prompt=query)
                masks, boxes, scores = output["masks"], output["boxes"], output["scores"]
                print(f"Found {masks.shape[0]} masks from SAM3 for the prompt '{query}'")
                print("Scores:", scores.cpu().numpy())


            masked_img = utils.overlay_masks(best_img, masks)
            masked_img.show()

            for i in range(masks.shape[0]):
                mask = masks[i].cpu().numpy()
                obb_center, obb_extent, obb_rotation = utils.compute_obb_from_points(found_submap.get_points_in_mask(overall_best_frame_index, mask, solver.graph))
                solver.viewer.visualize_obb(
                    center=obb_center,
                    extent=obb_extent,
                    rotation=obb_rotation,
                    color=(255, 0, 0),
                    line_width=8.0,
                )

    if args.keep_alive:
        print("Viewer ready at http://localhost:8080 — press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
