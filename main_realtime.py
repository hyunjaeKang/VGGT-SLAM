import os
import time
import threading
import queue
import argparse
from pathlib import Path

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import cv2
import numpy as np
import torch
from torchvision.transforms.functional import to_pil_image

import vggt_slam.slam_utils as utils
from vggt_slam.solver import Solver
from vggt_slam.cameras import BACKENDS, EndOfStream

from vggt.models.vggt import VGGT
from vggt_slam.runtime import select_device, model_dtype, validate_args

# --- Thread Safety Primitives ---
solver_lock = threading.Lock()  # Ensures only one solver thread runs at a time
data_lock = threading.Lock()    # Protects shared SLAM state (solver)

parser = argparse.ArgumentParser(description="VGGT-SLAM RealSense live demo")
parser.add_argument("--keyframe_folder", type=str, default="keyframes", help="Folder to save captured keyframes")
parser.add_argument("--camera", type=str, default="realsense", choices=list(BACKENDS.keys()), help="Camera backend (default: realsense)")
parser.add_argument("--video", type=Path, help="Input video path when --camera video_file")
parser.add_argument("--video_start", type=int, default=0, help="First source video frame to decode")
parser.add_argument("--video_end", type=int, help="Last source video frame to decode, inclusive")
parser.add_argument("--video_pacing", choices=("offline", "realtime"), default="offline")
parser.add_argument("--max_frames", type=int, default=0, help="Stop after this many decoded frames; 0 reads to EOF")
parser.add_argument("--headless", action="store_true", help="Do not start a live viewer; available for video_file")
parser.add_argument("--video_gui", action="store_true", help="Add video controls to the live Viser viewer")
parser.add_argument("--video_start_paused", action="store_true", help="Wait for Step or Resume before processing video frames")
parser.add_argument("--no_video_window", action="store_true", help="Disable OpenCV window; Viser controls remain available")
parser.add_argument("--viewer_port", type=int, default=8080)
parser.add_argument("--device", choices=("auto", "cuda", "mps", "cpu"), default="auto", help="Inference device (auto: CUDA, then Apple MPS, then CPU)")
parser.add_argument("--vis_map", action="store_true", help="Visualize point cloud in viser as it is being built, otherwise only show the final map")
parser.add_argument("--vis_imgs", action="store_true", help="Show camera images in the viser frustums. By default only the frustums are shown (faster visualization)")
parser.add_argument("--vis_voxel_size", type=float, default=None, help="Voxel size for downsampling the point cloud in the viewer (e.g. 0.05 for 5 cm). Default: no downsampling")
parser.add_argument("--vis_flow", action="store_true", help="Visualize Lucas-Kanade optical flow for keyframe selection")
parser.add_argument("--run_os", action="store_true", help="Enable open-set semantic search with Perception Encoder CLIP and SAM3")
parser.add_argument("--submap_size", type=int, default=16, help="Number of new frames per submap, does not include overlapping frames or loop closure frames")
parser.add_argument("--overlapping_window_size", type=int, default=1, help="ONLY DEFAULT OF 1 SUPPORTED RIGHT NOW. Number of overlapping frames, which are used in SL(4) estimation")
parser.add_argument("--max_loops", type=int, default=1, help="ONLY DEFAULT OF 1 SUPPORTED RIGHT NOW or 0 to disable loop closures.")
parser.add_argument("--min_disparity", type=float, default=50, help="Minimum disparity to generate a new keyframe")
parser.add_argument("--conf_threshold", type=float, default=25.0, help="Initial percentage of low-confidence points to filter out")
parser.add_argument("--lc_thres", type=float, default=0.95, help="Threshold for image retrieval. Range: [0, 1.0]. Higher = more loop closures")
parser.add_argument("--log_results", action="store_true", help="save txt file with results")
parser.add_argument("--skip_dense_log", action="store_true", help="by default, logging poses and logs dense point clouds. If this flag is set, dense logging is skipped")
parser.add_argument("--log_path", type=str, default="poses.txt", help="Path to save the log file")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def save_keyframe(img: np.ndarray, folder: str, idx: int) -> str:
    filename = os.path.join(folder, f"frame_{idx:06d}.png")
    cv2.imwrite(filename, img)
    return filename


def restart_camera(camera, stop_event=None, retry_delay: float = 2.0):
    """Stop and re-start the camera, retrying until a device is streaming again.

    Used to recover from a mid-session disconnect (e.g. a RealSense USB drop),
    where ``capture()`` raises. Honors ``stop_event`` so the user can still
    cancel while a camera is unplugged. Returns the working camera object, or
    None if aborted via stop_event.
    """
    try:
        camera.stop()
    except Exception:
        pass  # device may already be gone; ignore teardown errors

    attempt = 0
    while stop_event is None or not stop_event.is_set():
        attempt += 1
        try:
            camera.start()
            print(f"[Camera] Reconnected after {attempt} attempt(s).")
            return camera
        except Exception as e:
            print(f"[Camera] Reconnect attempt {attempt} failed: {e}.")
            print(f"[Camera] Retrying in {retry_delay:.0f}s...")
            time.sleep(retry_delay)
    print("[Camera] Reconnection aborted (session cancelled).")
    return None


def threaded_process_submap(image_names_subset, solver, model, args, clip_model, clip_preprocess, errors=None):
    """Background thread: run VGGT inference + graph optimisation for one submap."""
    try:
        submap_started = time.perf_counter()
        print(f"[SLAM] Processing submap ({len(image_names_subset)} frames)...")
        predictions = solver.run_predictions(
            image_names_subset, model, args.max_loops, clip_model, clip_preprocess
        )
        with data_lock:
            recorder = getattr(solver, "demo_recorder", None) if args.camera == "video_file" else None
            if recorder is not None:
                from vggt_slam.demo.graph_recording import optimize_recorded, record_preview

                frame_ids = [args.video_frame_records[str(Path(name).resolve())]
                             for name in image_names_subset]
                submap_id = solver.current_working_submap.get_id()
                recorder.record_submap(submap_id, frame_ids, predictions,
                                       overlap_count=args.overlapping_window_size if submap_id else 0)
            solver.add_points(predictions)
            if recorder is None:
                solver.graph.optimize()
            else:
                record_preview(solver.current_working_submap, recorder,
                               per_frame=50_000 if args.camera == "video_file" else 1_000)
                optimize_recorded(solver.graph, solver.map, recorder, args.demo_step)
                args.demo_step += 1
            if args.vis_map:
                if len(predictions.get("detected_loops", [])) > 0:
                    solver.update_all_submap_vis()
                else:
                    solver.update_latest_submap_vis()
            if args.camera == "video_file":
                args.submap_metrics.append({"submap_id": int(solver.current_working_submap.get_id()),
                                            "input_frames_including_overlap": len(image_names_subset),
                                            "elapsed_seconds": time.perf_counter() - submap_started})
        print("[SLAM] Submap done.")
    except Exception as e:
        if errors is None:
            raise
        errors.put(e)
    finally:
        if solver_lock.locked():
            solver_lock.release()


def run_semantic_query_loop(args, solver, clip_model, clip_tokenizer, processor):
    """Interactive open-set semantic query loop, run after capture ends."""
    from vggt_slam.demo.object_query import boxes_from_masks, save_query_evidence

    while True:
        query = input("\nEnter text query or q to quit: ").strip()
        if len(query) == 0:
            print("Empty query. Exiting.")
            return
        if query == "q":
            print("Exiting.")
            return

        text_emb = utils.compute_text_embeddings(clip_model, clip_tokenizer, query)
        overall_best_score, overall_best_submap_id, overall_best_frame_index = \
            solver.map.retrieve_best_semantic_frame(text_emb)

        found_submap = solver.map.get_submap(overall_best_submap_id)

        best_img = found_submap.get_frame_at_index(overall_best_frame_index)
        print("Score:", overall_best_score)
        with torch.no_grad():
            best_img = to_pil_image(best_img)
            inference_state = processor.set_image(best_img)
            output = processor.set_text_prompt(state=inference_state, prompt=query)
            masks, boxes, scores = output["masks"], output["boxes"], output["scores"]
            print(f"Found {masks.shape[0]} masks from SAM3 for the prompt '{query}'")
            print("Scores:", scores.cpu().numpy())

        masked_img = utils.overlay_masks(best_img, masks)
        masked_img.show()
        detections = boxes_from_masks(found_submap, overall_best_frame_index, solver.graph,
                                      masks.cpu().numpy(), scores=scores.cpu().numpy())
        for detection in detections:
            if detection["valid"]:
                solver.viewer.visualize_obb(center=np.asarray(detection["center"]),
                                            extent=np.asarray(detection["extent"]),
                                            rotation=np.asarray(detection["rotation"]),
                                            color=(255, 0, 0), line_width=8.0)
        recorder = getattr(solver, "demo_recorder", None)
        save_query_evidence(query, overall_best_score, overall_best_submap_id,
                            overall_best_frame_index, best_img, detections,
                            run_dir=recorder.run_dir if recorder is not None else None,
                            recorder=recorder)


def run_camera_pipeline(args):
    device = select_device(args.device)
    print(f"Using device: {device}")

    # When --run_os is set, SAM3/decord loads its own libxcb which poisons
    # OpenCV's XCB state and makes cv2.waitKey() hang. Skip cv2 display in that
    # case and print periodic status to the console instead.
    use_display = not args.run_os and not args.headless and not args.no_video_window

    solver = Solver(
        init_conf_threshold=args.conf_threshold,
        lc_thres=args.lc_thres,
        vis_voxel_size=args.vis_voxel_size,
        vis_imgs=args.vis_imgs,
        device=device,
        enable_viewer=not args.headless,
        viewer_port=args.viewer_port,
    )
    if args.camera == "video_file":
        solver.demo_recorder = args.demo_recorder
    solver.query_stop_event = threading.Event()

    print("Initializing and loading VGGT model...")

    if args.run_os:
        from sam3.model_builder import build_sam3_image_model
        from sam3.model.sam3_image_processor import Sam3Processor
        import core.vision_encoder.pe as pe
        import core.vision_encoder.transforms as transforms

        sam3_model = build_sam3_image_model(device=str(device))
        processor = Sam3Processor(sam3_model, device=str(device), confidence_threshold=0.50)

        clip_model = pe.CLIP.from_config("PE-Core-L14-336", pretrained=True)  # Downloads from HF
        clip_model = clip_model.to(device).eval()
        clip_tokenizer = transforms.get_text_tokenizer(clip_model.context_length)
        clip_preprocess = transforms.get_image_transform(clip_model.image_size)
    else:
        clip_model, clip_preprocess = None, None
        clip_tokenizer, processor = None, None

    model = VGGT()
    _URL = "https://huggingface.co/facebook/VGGT-1B/resolve/main/model.pt"
    model.load_state_dict(torch.hub.load_state_dict_from_url(_URL, map_location="cpu"))

    model.eval()
    model = model.to(device=device, dtype=model_dtype(device))
    print("All models loaded. Starting SLAM loop.")

    # Register the viser object-query panel so the user can search for objects
    # live (and after capture) without using the terminal.
    if args.run_os:
        solver.viewer.add_object_query_gui(solver, clip_model, clip_tokenizer, processor, data_lock)

    # --- Camera setup ---
    camera = (BACKENDS[args.camera](str(args.video), start_frame=args.video_start,
                                    end_frame=args.video_end, pacing=args.video_pacing)
              if args.camera == "video_file" else BACKENDS[args.camera]())
    print(f"Initializing {args.camera} camera...")
    if args.camera == "video_file" and not getattr(args, "video_run_dir", None):
        args.keyframe_folder = str(Path(args.keyframe_folder) / f"video_run_{time.time_ns()}")
    os.makedirs(args.keyframe_folder, exist_ok=True)
    camera.start()

    # Warm up devices; keep the first decoded video frame for the processing loop.
    print("Waiting for first camera frame...")
    first_frame = None
    pending_frame = None
    while first_frame is None:
        try:
            first_frame = camera.capture()
            if args.camera == "video_file":
                pending_frame = first_frame
        except EndOfStream:
            print("[Video] No frames available in the requested range.")
            break
        except Exception as e:
            if args.camera == "video_file":
                camera.stop()
                raise RuntimeError(f"video input failed: {e}") from e
            print(f"[Camera] Error during warm-up ({e}). Reconnecting...")
            camera = restart_camera(camera)
    if first_frame is None:
        camera.stop()
        raise EndOfStream(f"no video frames available for {args.video}")

    if use_display:
        cv2.imshow("VGGT-SLAM Live", first_frame)
        cv2.waitKey(1)
    print("Camera ready.")

    frame_count = 0
    image_names_subset = []
    target_size = args.submap_size + args.overlapping_window_size
    submap_count = 0
    last_status_frame = 0  # for console status throttle when display is off
    stop_event = threading.Event()
    errors = queue.Queue()
    video_log = None
    video_keyframe_log = None
    video_drop_log = None
    capture_started = time.perf_counter()
    if args.camera == "video_file":
        video_log = (Path(args.keyframe_folder) / "video_frames.jsonl").open("x", encoding="utf-8")
        video_keyframe_log = (Path(args.keyframe_folder) / "video_keyframes.jsonl").open("x", encoding="utf-8")
        video_drop_log = (Path(args.keyframe_folder) / "video_drops.jsonl").open("x", encoding="utf-8")
        args.video_frame_records = {}
        args.demo_step = 1
        args.submap_metrics = []
    decoded_frames = 0
    dropped_frames = 0
    timestamp_type_counts = {}
    paused = args.video_start_paused
    pause_events = 0
    stepped_frames = 0
    step_requested = False
    stop_reason = "unknown"
    controls = None
    if args.video_gui:
        from vggt_slam.demo.video_controls import VideoControls

        controls = VideoControls(solver.viewer.server)
        args.video_controls = controls

    def handle_video_key(key):
        nonlocal paused, pause_events, step_requested, stop_reason
        if key == ord("q"):
            stop_reason = "user_stop"
            if controls is not None:
                controls.update("Stopping", decoded_frames, solver_lock.locked())
            args.demo_recorder.event("video_control", payload={"action": "stop", "decoded_frames": decoded_frames})
            return True
        if key in (ord("p"), ord(" ")):
            paused = not paused
            if not paused:
                camera.resume_pacing()
            pause_events += 1
            args.demo_recorder.event("video_control", payload={"action": "pause" if paused else "resume", "decoded_frames": decoded_frames})
        if paused and key == ord("n"):
            step_requested = True
            args.demo_recorder.event("video_control", payload={"action": "step", "decoded_frames": decoded_frames})
        return False

    try:
        while True:
            if not errors.empty():
                raise RuntimeError("SLAM submap processing failed") from errors.get()
            if stop_event.is_set():
                stop_reason = "stop_event"
                break
            if controls is not None:
                controls.update("Paused" if paused else "Running", decoded_frames, solver_lock.locked())
                if any(handle_video_key(key) for key in controls.drain()):
                    break
            if args.camera == "video_file" and use_display:
                key = cv2.waitKey(1) & 0xFF
                if handle_video_key(key):
                    break
            if args.camera == "video_file":
                if paused and not step_requested:
                    time.sleep(0.05)
                    continue
                if paused and step_requested:
                    stepped_frames += 1
                    step_requested = False

            if pending_frame is not None:
                img, pending_frame = pending_frame, None
            else:
                try:
                    img = camera.capture()
                except EndOfStream:
                    stop_reason = "eof_or_range"
                    print("[Video] End of file/range; flushing pending frames.")
                    break
                except Exception as e:
                    if args.camera == "video_file":
                        raise RuntimeError(f"video input failed: {e}") from e
                    print(f"[Camera] Lost connection ({e}). Attempting to reconnect...")
                    camera = restart_camera(camera, stop_event)
                    if camera is None:  # session cancelled while reconnecting
                        break
                    continue

            if img is None:
                continue

            frame_count += 1
            decoded_frames += 1
            timestamp_type = getattr(camera, "source_timestamp_type", "video_pts_seconds")
            timestamp_type_counts[timestamp_type] = timestamp_type_counts.get(timestamp_type, 0) + 1
            if controls is not None:
                controls.update("Paused" if paused else "Running", decoded_frames, solver_lock.locked(), img)

            selected = solver.flow_tracker.compute_disparity(img, args.min_disparity, args.vis_flow)
            if video_log is not None:
                import json
                video_log.write(json.dumps({"decoded_index": decoded_frames - 1,
                                           "source_frame_id": camera.source_frame_id,
                                           "source_timestamp_seconds": camera.source_timestamp,
                                           "source_timestamp_type": getattr(camera, "source_timestamp_type", "video_pts_seconds"),
                                           "raw_pts_seconds": getattr(camera, "raw_source_timestamp", None),
                                           "timestamp_reason": getattr(camera, "source_timestamp_reason", None),
                                           "keyframe_selected": bool(selected)}) + "\n")
                video_log.flush()

            if selected:
                frame_path = save_keyframe(img, args.keyframe_folder, frame_count)
                image_names_subset.append(frame_path)
                if video_log is not None:
                    import json
                    args.video_frame_records[str(Path(frame_path).resolve())] = {
                        "frame_id": camera.source_frame_id, "source": str(Path(frame_path).resolve()),
                        "timestamp": camera.source_timestamp,
                        "timestamp_type": getattr(camera, "source_timestamp_type", "video_pts_seconds"),
                        "timestamp_reason": getattr(camera, "source_timestamp_reason", None),
                        "raw_pts_seconds": getattr(camera, "raw_source_timestamp", None)}
                    video_keyframe_log.write(json.dumps({"keyframe_path": frame_path,
                                                         "decoded_index": decoded_frames - 1,
                                                         "source_frame_id": camera.source_frame_id,
                                                         "source_timestamp_seconds": camera.source_timestamp,
                                                         "source_timestamp_type": getattr(camera, "source_timestamp_type", "video_pts_seconds")}) + "\n")
                    video_keyframe_log.flush()

            if len(image_names_subset) >= target_size:
                # Offline decoding waits for inference instead of discarding selected frames.
                offline_video = args.camera == "video_file" and args.video_pacing == "offline"
                if solver_lock.acquire(blocking=offline_video):
                    if not errors.empty():
                        solver_lock.release()
                        raise RuntimeError("SLAM submap processing failed") from errors.get()
                    submap_count += 1
                    print(f"[Main] Launching submap {submap_count} (frame {frame_count})...")
                    t = threading.Thread(
                        target=threaded_process_submap,
                        args=(list(image_names_subset), solver, model, args, clip_model, clip_preprocess, errors),
                        daemon=True,
                    )
                    t.start()
                    image_names_subset = image_names_subset[-args.overlapping_window_size:]
                else:
                    # SLAM still busy; cap the backlog so we don't grow unbounded.
                    # Keep the shared frame that anchors this submap to its predecessor.
                    if len(image_names_subset) > target_size:
                        overflow = len(image_names_subset) - target_size
                        dropped_frames += overflow
                        if video_drop_log is not None:
                            import json
                            dropped_names = image_names_subset[1:1 + overflow]
                            for dropped_name in dropped_names:
                                record = args.video_frame_records.get(str(Path(dropped_name).resolve()), {})
                                video_drop_log.write(json.dumps({"keyframe_path": dropped_name,
                                                                 "source_frame_id": record.get("frame_id"),
                                                                 "source_timestamp_seconds": record.get("timestamp"),
                                                                 "source_timestamp_type": record.get("timestamp_type")}) + "\n")
                            video_drop_log.flush()
                        image_names_subset = image_names_subset[:1] + image_names_subset[-(target_size - 1):]

            kf = len(image_names_subset)
            slam_busy = solver_lock.locked()

            if use_display:
                display = img.copy()
                status = f"KFs: {kf}/{target_size}  Submaps: {submap_count}"
                if args.camera == "video_file":
                    status += "  [P: pause  N: step  Q: stop]"
                    if paused:
                        status += "  [PAUSED]"
                if slam_busy:
                    status += "  [SLAM running]"
                cv2.putText(display, status, (8, 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.imshow("VGGT-SLAM Live", display)
                key = cv2.waitKey(1) & 0xFF
                if args.camera == "video_file":
                    if handle_video_key(key):
                        break
                elif key == ord('q'):
                    break
            else:
                if frame_count - last_status_frame >= 30:
                    busy_str = "  [SLAM running]" if slam_busy else ""
                    print(f"[Camera] frame={frame_count}  KFs={kf}/{target_size}"
                          f"  submaps={submap_count}{busy_str}")
                    last_status_frame = frame_count
            if args.camera == "video_file" and args.max_frames and decoded_frames >= args.max_frames:
                stop_reason = "max_frames"
                print("[Video] Reached --max_frames; flushing pending frames.")
                break

    except KeyboardInterrupt:
        stop_reason = "keyboard_interrupt"
        print("\n[Main] Shutting down...")
    finally:
        if args.run_os and args.camera == "video_file":
            solver.query_stop_event.set()
        try:
            if camera is not None:
                camera.stop()
        finally:
            # Even camera release failure must drain writers before recorder closure.
            with solver_lock:
                pass
            if args.run_os:
                with data_lock:
                    pass
            if controls is not None:
                controls.update("Stopping", decoded_frames)
            if video_log is not None:
                video_log.close()
            if video_keyframe_log is not None:
                video_keyframe_log.close()
            if video_drop_log is not None:
                video_drop_log.close()
            if use_display:
                cv2.destroyAllWindows()

    # Wait for any in-flight submap to finish before final visualization/logging.
    with solver_lock:
        pass
    if not errors.empty():
        raise RuntimeError("SLAM submap processing failed") from errors.get()

    # Flush remaining new keyframes when capture ends, including short sessions.
    if image_names_subset and (submap_count == 0 or len(image_names_subset) > args.overlapping_window_size):
        solver_lock.acquire()
        threaded_process_submap(image_names_subset, solver, model, args, clip_model, clip_preprocess, errors)
        if not errors.empty():
            raise RuntimeError("SLAM submap processing failed") from errors.get()

    print("Total number of submaps in map", solver.map.get_num_submaps())
    print("Total number of loop closures in map", solver.graph.get_num_loops())
    if args.camera == "video_file":
        import json
        elapsed = time.perf_counter() - capture_started
        submap_times = [item["elapsed_seconds"] for item in args.submap_metrics]
        summary = {"source_mode": "video_file_incremental", "video": str(Path(args.video).resolve()),
                   "video_sha256": json.loads((args.video_run_dir / "manifest.json").read_text())["config"]["video_sha256"],
                   "pacing": args.video_pacing, "source_fps": camera._fps,
                   "decoded_frames": decoded_frames,
                   "timestamp_type_counts": timestamp_type_counts,
                   "pacing_clock": "per-frame timestamp: observed PTS or explicitly labelled FPS approximation",
                   "selected_keyframes": len(args.video_frame_records),
                   "keyframe_backlog_dropped": dropped_frames,
                   "submaps": len(args.submap_metrics), "submap_processing": args.submap_metrics,
                   "pause_toggle_events": pause_events, "single_step_frames": stepped_frames,
                   "stop_reason": stop_reason,
                   "submap_latency_seconds_p50": float(np.percentile(submap_times, 50)) if submap_times else None,
                   "submap_latency_seconds_p95": float(np.percentile(submap_times, 95)) if submap_times else None,
                   "capture_wall_seconds": elapsed,
                   "decode_pacing_fps": decoded_frames / elapsed if elapsed > 0 else None,
                   "limitations": ["Video optical-flow selection and inference run sequentially in one process",
                                  "GT trajectory evaluation requires a timestamp-aligned reference"]}
        (args.video_run_dir / "video_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(f"Video summary: decoded={decoded_frames}, keyframes={len(args.video_frame_records)}, "
              f"submaps={len(args.submap_metrics)}, keyframe_backlog_dropped={dropped_frames}, pacing={args.video_pacing}")

    if not args.vis_map and not args.headless:
        # just show the map after all submaps have been processed
        solver.update_all_submap_vis()

    if args.log_results and solver.map.get_num_submaps() > 0:
        os.makedirs(os.path.dirname(os.path.abspath(args.log_path)), exist_ok=True)
        solver.map.write_poses_to_file(args.log_path, solver.graph, kitti_format=False)
        if not args.skip_dense_log:
            log_path = Path(args.log_path)
            solver.map.write_points_to_file(solver.graph, str(log_path.with_name(log_path.stem + "_points.pcd")))

    if args.run_os and not args.video_gui and solver.map.get_num_submaps() > 0:
        run_semantic_query_loop(args, solver, clip_model, clip_tokenizer, processor)
    if controls is not None:
        controls.update("Completed", decoded_frames)


def main():
    args = parser.parse_args()
    if args.video_gui and (args.headless or args.camera != "video_file"):
        parser.error("--video_gui requires video_file and a live viewer (no --headless)")
    if args.video_start_paused and not (args.video_gui or (not args.headless and not args.no_video_window and not args.run_os)):
        parser.error("--video_start_paused requires Viser video controls or the OpenCV window")
    if args.camera == "video_file" and args.video is None:
        parser.error("--camera video_file requires --video PATH")
    if args.camera != "video_file" and args.video is not None:
        parser.error("--video requires --camera video_file")
    if args.video_start < 0 or args.max_frames < 0 or (args.video_end is not None and args.video_end < 0):
        parser.error("video frame bounds and --max_frames must be nonnegative")
    if args.headless and args.camera != "video_file":
        parser.error("--headless is supported only with --camera video_file")
    if args.headless and args.run_os:
        parser.error("--headless cannot be combined with --run_os")
    validate_args(parser, args)
    if args.camera != "video_file":
        return run_camera_pipeline(args)

    from vggt_slam.demo.video_run import create_video_run, finish_video_run, start_video_run

    config = {key: str(value) if isinstance(value, Path) else value
              for key, value in vars(args).items()}
    run_dir = create_video_run(args.video, config)
    args.video_run_dir = run_dir
    args.keyframe_folder = str(run_dir / "keyframes")
    args.log_results = True
    args.log_path = str(run_dir / "poses.txt")
    recorder = None
    try:
        from vggt_slam.demo.recording import Recorder

        start_video_run(run_dir, select_device(args.device))
        recorder = Recorder(run_dir)
        args.demo_recorder = recorder
        result = run_camera_pipeline(args)
        recorder.event("run_completed", payload={"source_mode": "video_file_incremental"})
        recorder.close()
        recorder = None
        finish_video_run(run_dir)
        print(f"Video run saved: {run_dir}", flush=True)
        return result
    except BaseException as exc:
        controls = getattr(args, "video_controls", None)
        if controls is not None:
            controls.update("Failed", len(getattr(args, "video_frame_records", {})))
        if recorder is not None:
            try:
                recorder.event("run_failed", payload={"error": str(exc) or type(exc).__name__})
            finally:
                recorder.close()
        finish_video_run(run_dir, error=str(exc) or type(exc).__name__)
        raise


if __name__ == "__main__":
    main()
