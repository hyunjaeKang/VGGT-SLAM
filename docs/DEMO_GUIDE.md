# VGGT-SLAM Demo Guide

This repository supports offline image runs, saved-run inspection, and incremental video-file input. A video-file run executes SLAM while decoding the file; it is separate from opening a previously cached result. RealSense remains available in the original live entry point, but the demo evidence here uses video files.

For the updated map UI, sky filtering, synchronized BEV and cached text search, see [Map Studio](MAP_STUDIO.md).

## Environment

Use the repository `.venv` and its cached VGGT checkpoint. Check optional packages and devices with:

```bash
.venv/bin/python demo.py doctor
```

The current environment has OpenCV and Viser. The VGGT checkpoint is cached locally. SAM3/Perception Encoder and `evo` are optional; text object search and the `evo_ape` TUM evaluation need those dependencies and their model assets. Do not treat a missing optional model as a successful search or evaluation.

## Incremental video input

```bash
.venv/bin/python -u main_realtime.py \
  --camera video_file \
  --video /path/to/drive.mp4 \
  --video_pacing offline \
  --device mps \
  --submap_size 16 \
  --max_loops 1 \
  --headless
```

`--video_start` and inclusive `--video_end` select source frame indices. `--max_frames 0` reads to EOF; a positive value caps decoded frames. `offline` decodes as fast as processing permits. `realtime` follows per-frame PTS; unavailable or non-increasing PTS uses an explicitly labelled FPS approximation when a finite positive FPS exists. Without `--headless`, the video window accepts **P** or **Space** to pause/resume, **N** to process one frame while paused, and **Q** to stop and flush pending keyframes. Closing the run writes poses, a colored PCD, frame/depth/confidence assets, graph snapshots, and a video summary under a unique `logs/demo_runs/video_<id>/` directory. Existing keyframes and runs are not reused.

The manifest records the input path, SHA-256, frame range, pacing, device and model checkpoint. `keyframes/video_frames.jsonl` records decoded frame IDs, PTS timestamps and selection decisions; `video_drops.jsonl` records keyframes dropped when inference falls behind. `video_summary.json` reports decoded/keyframe/submap counts and submap latency percentiles.

Open a completed run without loading VGGT or SAM3:

```bash
.venv/bin/python demo.py view --run logs/demo_runs/video_<id> --port 8090
```

The Viser run list is populated from run directories with a `manifest.json`; restart the viewer to discover runs created after it starts. The browser shows cached RGB, relative depth, confidence, trajectory, camera frustum, graph edges, loop evidence and any saved trajectory metrics. Reconstruction scale is unverified unless a separately documented evaluation fits it to ground truth.

Use **Point size (점 크기 배율)** to adjust displayed point size from **0.1× to 10×** (default 1×). This changes only appearance and persists when changing frames or runs during the viewer session. **Displayed point limit** controls the number of points separately.

Cached playback opens paused at the final frame. **Play / Pause** starts or toggles playback; starting at the end restarts from the first frame. **Pause playback** explicitly pauses at the current frame. The status below these buttons shows **재생 중**, **정지**, or **재생 완료**. Playback targets two frames per second and waits for rendering; this is saved-result playback, not model inference speed.

## Offline image run

Prepare an explicit selection with a JSON config containing `run_id`, `image_dir`, and optional `start`, `end`, `frame_ids_file`, and timestamp sidecar settings:

```bash
.venv/bin/python demo.py prepare --config configs/demo/pandaset003_cached.json
.venv/bin/python -u main.py --headless --device mps \
  --demo_run logs/demo_runs/<run_id> --submap_size 16 --max_loops 1
.venv/bin/python demo.py view --run logs/demo_runs/<run_id>
```

Use a new run ID for each inference. `cached_playback` configs register existing PCD and pose files for browsing without copying those files or running a model.

## Text object search

The online path uses Perception Encoder CLIP to rank captured frames and SAM3 to produce masks, followed by a 3D box from reconstructed points. Keep the display enabled for the object query panel or post-capture prompt:

```bash
.venv/bin/python main_realtime.py --run_os --camera video_file \
  --video /path/to/indoor.mp4 --video_pacing offline --device mps
```

This requires the SAM3 and PE packages, compatible checkpoints, and a supported device. Search is not available in headless mode. Each search saves the selected RGB frame, masks, retrieval score and confidence-filtered 3D boxes under `object_queries/`; the viewer's **Clear boxes** button removes the live boxes. Saved runs reopen their query result and boxes in the cached viewer. The default `.venv` does not include SAM3 or `evo`. The experimental `.venv-open-set` has SAM3/PE installed, and a patched SAM3 CPU image query has completed; PE retrieval plus SLAM 3D box integration remains unvalidated.

For a reproducible single-image diagnostic, first apply the narrowly scoped import/cache patch, then run:

```bash
.venv-open-set/bin/python scripts/patch_sam3.py
.venv-open-set/bin/python scripts/demo_sam3_smoke.py \
  --image /path/to/image.png --query car --device cpu \
  --output logs/demo_environment/<new-experiment-id>
```

The smoke command uses only the locally cached SAM3 checkpoint and writes a success or Python failure `result.json`; native crashes can bypass this writer, so preserve process exit status and stdout as well. It tests SAM3 segmentation alone, without PE retrieval or SLAM/3D boxes. The patch defers CUDA EDT import, permits CPU position/decoder caches, uses FP32 linear/activation on CPU, and avoids CUDA pinned memory on CPU. A real CPU `car` query completed in 10.9 seconds with 19 masks (`logs/demo_environment/sam3_cpu_smoke_20261105_06`). MPS and full search integration remain unverified. Use a new output directory for every attempt.

## Evaluation and report

PandaSet and KITTI-360 evaluation helpers are in `scripts/evaluate_pandaset.py` and `scripts/evaluate_kitti360.py`. They fit a Sim(3) transform on matched poses; report match counts and do not interpret fitted ATE as absolute localization. TUM evaluation uses `evals/eval_tum.sh` and requires `evo` plus a timestamp-aligned TUM ground truth.

Generate a local run inventory after experiments:

```bash
.venv/bin/python scripts/demo_report.py --runs-root logs/demo_runs --output docs/DEMO_RESULTS.md --force
```

Run outputs and large point clouds are ignored by Git. Keep evidence in the run directory and commit only source, docs, and small fixtures.

### Recorded-run object query experiment

`scripts/demo_pe_retrieve.py --run <recorded-run> --query car --output <new-retrieval-folder>` runs actual PE retrieval in `.venv-open-set`. Use the selected RGB path from `result.json` as `demo_sam3_smoke.py --image`; keep the same query. Then use the base `.venv` to run:

```bash
.venv/bin/python scripts/demo_cached_object_boxes.py \
  --retrieval <retrieval-folder> --segmentation <sam3-output-folder> \
  --output <new-3d-box-folder>
```

This reuses recorded depth/confidence and the final projective snapshot without rerunning VGGT or modifying the source run. Separate evidence folders are not automatically registered in the cached viewer. A `car` experiment produced 17 confidence-filtered 3D boxes from 19 SAM3 masks; visual box quality and other query categories remain unverified.

### Browse real object query evidence

The derived run `logs/demo_runs/object_queries_20261105_01` references the original video map and contains real `car`, `tree`, and `elephant` query results. Start it with:

```bash
.venv/bin/python demo.py view --run logs/demo_runs/object_queries_20261105_01 --port 8092
```

In **Saved object query**, select `query_1793848788240336000` for car (17 valid boxes), `query_1793852578053438000` for tree (3), or `query_1793852602152499000` for elephant (0). Use optimization step **2**, view **after**, and **Clear object boxes** to remove the overlay. Select the query again to reopen it. These boxes are bound to their recorded snapshot; other optimization views hide them. Counts demonstrate the data path, not object localization accuracy. The source run must remain in place because the derived run shares its large assets through symlinks.

### Video pacing and integrity checks

`offline` waits for the current inference worker before advancing a full keyframe batch; it preserves selected keyframes. `realtime` caps the pending keyframe batch and records discarded keyframes in `video_drops.jsonl`. Source FPS, decode/capture throughput, and inference latency measure different things. `--headless` disables both OpenCV display and the live viewer.

Validate a completed video run and export its estimate using actual recorded PTS:

```bash
.venv/bin/python scripts/demo_validate_video.py --run logs/demo_runs/<video-id> \
  --output logs/demo_runs/<video-id>/evidence/<new-validation-id>
```

The validator checks processed/dropped frame partition, pose-to-keyframe IDs, normalized quaternions, and strictly increasing timestamps. `estimated_pts.tum` replaces keyframe filename IDs with observed video PTS seconds; if any frame uses an FPS approximation it writes `estimated_approximate.tum` and marks the provenance instead. It is a TUM-format estimate, not a ground-truth evaluation; ATE remains unavailable without a corresponding reference.

### Single-sequence TUM evaluation

Use `.venv-eval` for `evo`; keep the SLAM environment unchanged. `scripts/demo_prepare_tum.py` selects RGB rows uniformly from an official archive, assigns numeric local frame IDs, and preserves the original RGB timestamps in a sidecar. It extracts ground truth separately for evaluation and never passes depth/GT to inference.

```bash
.venv/bin/python scripts/demo_prepare_tum.py --archive /path/to/freiburg1_xyz.tgz \
  --output logs/demo_selections/<new-selection> --run-id <new-run> --count 33
.venv/bin/python main.py --headless --device mps --demo_run logs/demo_runs/<new-run> \
  --submap_size 8 --max_loops 0 --use_all_selected_frames
.venv-eval/bin/python scripts/demo_evaluate_tum.py --run logs/demo_runs/<new-run> \
  --groundtruth logs/demo_selections/<new-selection>/groundtruth.txt \
  --output logs/demo_runs/<new-run>/evaluation
```

The evaluator replaces frame IDs with original RGB seconds, associates timestamps within 20ms, and runs `evo_ape tum <GT> <EST> -as`. It saves the command/stdout, evo ZIP, timestamp association differences, metric JSON, and an APE graph. The local `s10_tum_xyz33_20261105_01` experiment associated all 33 selected RGB frames and achieved **0.02369m position ATE RMSE after fitted Sim(3)**. This is one selected subset, not a full-sequence benchmark or absolute localization result. The official dataset source and citation are recorded in `logs/demo_datasets/tum/download_source.json`.

Open this result with `demo.py view --run logs/demo_runs/s10_tum_xyz33_20261105_01 --port 8093`. Its evaluation appears in the cached viewer alongside the map.

### Live Viser video controls

```bash
.venv/bin/python main_realtime.py --camera video_file --video /path/to/clip.mp4 \
  --video_pacing realtime --video_gui --video_start_paused --no_video_window \
  --viewer_port 8094 --vis_map --device mps --submap_size 4
```

Open `http://localhost:8094`. **Step video** processes one decoded frame while paused; **Pause / Resume video** toggles capture; **Stop video** stops capture, waits for an active submap worker, flushes pending keyframes, and saves the run. Pausing capture allows an already running worker to finish. Resume rebases the pacing clock so paused wall time does not cause a catch-up burst. `--no_video_window` disables OpenCV display while preserving the live Viser map and controls. `--video_gui` requires `video_file` and cannot be used with `--headless`. After the command exits, use the cached viewer to reopen its saved run.

The real Chrome/MPS control experiment is `video_20261105T053815_749770000`: six single-step frames, two pause/resume toggles, Stop at nine decoded frames, two saved submaps. Its GUI screenshots and action results are under `evidence/gui_controls_01/`. The capture wall time includes waiting while paused and is not an inference performance measurement.

For explicitly labelled failure experiments, `scripts/demo_video_failure_probe.py --video <small-fixture> --mode decoder|worker --output <new-probe-folder>` injects an error into a loaded pipeline. These runs intentionally end as `failed`; partial recorded RGB/depth/snapshots may remain, but successful pose/PCD export is not promised after failure. Do not interpret these probes as naturally occurring decoder/model failures.

### VFR and missing video timing

Valid increasing PTS drives pacing, including VFR files. A nominal average FPS does not override PTS. Timestamp handling is recorded per decoded frame, selected keyframe, and RGB/depth metadata:

| Timing input | Recorded timestamp |
|---|---|
| Finite, nonnegative, increasing PTS | `video_pts_seconds` |
| Missing/repeated/backward PTS with usable FPS | `video_frame_index_over_fps_seconds` |
| Frame-index approximation would move backward | `video_fps_extrapolated_seconds`, advanced from the last timestamp |
| Neither PTS nor FPS usable | `unavailable` in offline mode; realtime fails explicitly |

FPS-derived values are estimates, not observed PTS. Raw PTS (when finite), fallback reason, and timestamp type remain in sidecars/metadata; summary JSON counts each timestamp type. An unavailable timestamp prevents TUM export. Realtime delays above the camera's default 10-second pacing timeout fail explicitly rather than waiting indefinitely. Extremely long VFR gaps have not been validated.

The synthetic VFR fixture `logs/demo_fixtures/pandaset_vfr9_20261105` contains intervals from 40 to 320ms. OpenCV timestamps matched ffprobe exactly in both pacing modes; actual MPS run `video_20261106T001912_118994000` preserved those PTS through RGB/depth recording and TUM export. Invalid FPS/PTS cases were tested using a simulated decoder, separately from the real encoded VFR experiment.

### Live PE/SAM3 search in the same SLAM session

The verified local CPU entry point uses `.venv-open-set` for torch 2.13/torchvision/SAM3/PE and reuses the base `.venv` SLAM dependencies read-only. It loads the modern tensor stack first and records actual module paths in `open_set_runtime.json`. It requires matching Python major/minor versions; this local environment composition is not a standalone distribution.

```bash
HF_HUB_OFFLINE=1 .venv-open-set/bin/python scripts/demo_live_open_set.py \
  --run_os --camera video_file \
  --video logs/demo_fixtures/pandaset33_1fps_20261105/clip.mp4 \
  --video_gui --video_start_paused --no_video_window --viewer_port 8096 \
  --vis_map --submap_size 4 --max_loops 0 --min_disparity 0
```

Open `http://localhost:8096`, Step until a submap has finished, then enter text in **Object Query → Query** and press **Search**. **Clear boxes** removes the overlay. Capture can resume while a query runs. **Stop video** rejects new queries, waits for an in-flight query/worker to finish writing, flushes pending keyframes, and saves the run; the video GUI path does not open the terminal query loop afterward. The example defaults to offline pacing and CPU; it is not real-time throughput evidence, and MPS/CUDA open-set combinations have not been verified here.

The actual `video_20261106T011557_281290000` session captured 13 frames/three submaps and produced car=17, tree=3, elephant=0 valid boxes, with live Search/Clear and Stop during the last query. View its saved results at `http://localhost:8095` while the cached viewer is running. Choosing a saved query synchronizes the recorded optimization snapshot and frame; Clear hides the boxes. Old query files without a snapshot use the preceding recorded `optimization_finished` event in memory, preserving the files. Absolute object dimensions/positions have no independent GT validation.

### Acceptance and object quality review

See [DEMO_ACCEPTANCE_REVIEW.md](DEMO_ACCEPTANCE_REVIEW.md) for the final code/evidence comparison and object review. The 20 existing valid car/tree masks reproduced exactly and their reconstructed support points lie inside their saved boxes. This checks consistency, not independent object accuracy. Car detections #1 and #5 have strong extreme-point sensitivity and remain flagged for geometry review. Contact sheets, 3D diagnostic plots, and per-detection values are under the live run's `evidence/quality_review_01/`.

Future object queries reject rank-deficient support and retain excluded masks/reasons. No percentile trimming was silently applied to the original boxes. Use `scripts/demo_audit_object_quality.py --run <run> --replay <car-tree-SAM3-replay-root> --output <new-audit-folder>` to repeat the recorded-depth audit without rerunning VGGT.
