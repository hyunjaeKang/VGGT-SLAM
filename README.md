<div align="center">
  <h1>VGGT-SLAM 2.0</h1>

  <p>
    <strong>VGGT-SLAM</strong>
    <a href="https://arxiv.org/abs/2505.12549">
      <img src="https://img.shields.io/badge/arXiv-b33737?logo=arXiv" alt="arXiv" style="vertical-align:middle">
    </a>
    &nbsp;&nbsp;&nbsp;&nbsp;
    <strong>VGGT-SLAM 2.0</strong>
    <a href="https://arxiv.org/abs/2601.19887">
      <img src="https://img.shields.io/badge/arXiv-b33737?logo=arXiv" alt="arXiv" style="vertical-align:middle">
    </a>
  </p>

  <br />

  <img src="assets/vggt_slam_demo.gif" alt="VGGT-SLAM" width="95%"/>

  <p><strong><em>VGGT-SLAM 2.0: Real-time Dense Feed-forward Scene Reconstruction</em></strong></p>

  <p>
    <a href="https://dominic101.github.io/DominicMaggio/"><strong>Dominic Maggio</strong></a> &nbsp;·&nbsp;
    <a href="https://lucacarlone.mit.edu/"><strong>Luca Carlone</strong></a>
  </p>
</div>

---

# This repo contains the code for VGGT-SLAM 2.0 (located here) and VGGT-SLAM (located on the version1.0 branch of this repo).

## 📚 Table of Contents
* [💻 Installation](#installation-of-vGGT-sLAM)
* [🚀 Quick Start](#quick-start)
* [📊 Running Evaluations](#running-evaluations)
* [⚡ Running Online](#Running-Online)
* [📄 News and Updates](#News-and-Updates)
* [📄 Paper Citation](#citation)

---

## Installation of VGGT-SLAM

Clone VGGT-SLAM:

```
git clone https://github.com/MIT-SPARK/VGGT-SLAM
```

```
cd VGGT-SLAM
```

### Create and activate a new conda environment

```
conda create -n vggt-slam python=3.11
```

```
conda activate vggt-slam
```

### Make the setup script executable and run it
This step installs SALAD and our fork of VGGT for the basic mapping demo. Use `./setup.sh --with-open-set` to also install Perception Encoder and SAM 3 for `--run_os`. More details on the license for Perception Encoder
can be found [here](https://github.com/facebookresearch/perception_models/blob/main/LICENSE.PE), for SAM3 can be found [here](https://github.com/facebookresearch/sam3/blob/main/LICENSE), and for VGGT can be found [here](https://github.com/facebookresearch/vggt/blob/main/LICENSE.txt). Note that we only use SAM 3 and Perception Encoder for optional open-set 3D object detection.

```
chmod +x setup.sh
./setup.sh
```

The script uses `python3` from the active environment. Override it with
`PYTHON=/path/to/python ./setup.sh` if necessary. It can be rerun without cloning
existing repositories again. A small, checked patch makes the VGGT fork use the
selected model precision instead of forcing bfloat16 inputs.

### Apple Silicon / local virtual environment

Use Python 3.11; the pinned PyTorch version does not support Python 3.14.
With [uv](https://docs.astral.sh/uv/) installed:

```bash
uv venv --python 3.11 --seed .venv
source .venv/bin/activate
brew install libusb  # Needed by the Open3D 0.20 macOS wheel.
./setup.sh
```

The base mapping pipeline automatically selects CUDA, Apple MPS, then CPU.
Use `--device cpu`, `--device mps`, or `--device cuda` to select explicitly.
The optional SAM3 / Perception Encoder pipeline has separate platform and
model-access requirements and is not covered by the basic Mac setup.
First launch downloads the VGGT (~5 GB), DINOv2, and SALAD checkpoints to the
PyTorch cache, so it needs an internet connection and several GB of free space.

---

## Quick Start

run `python main.py --image_folder /path/to/image/folder --max_loops 1 --vis_map` replacing the image path with your folder of images.
This will create a visualization in viser which shows the incremental construction of the map.

As an example, we provide a folder of test images in `office_loop.zip` which will generate the following map. Using the default parameters will
result in a single loop closure towards the end of the trajectory. Unzip the folder and set its path as the arguments for `--image_folder`, e.g.,

```
unzip office_loop.zip
```

and then run the below command:

```
python3 main.py --image_folder office_loop --max_loops 1 --vis_map --keep_alive
```

Open **http://localhost:8080** to see the reconstruction. `--keep_alive` keeps
the viewer running after processing; press Ctrl+C to stop it. Omit that flag
for batch processing. To save the camera trajectory and dense point cloud:

```bash
python3 main.py --image_folder office_loop --max_loops 1 --vis_map --keep_alive \
  --log_results --log_path logs/office_loop_poses.txt
```

This writes `logs/office_loop_poses.txt` and `logs/office_loop_poses_points.pcd`.
Add `--skip_dense_log` to save only the trajectory, or `--vis_voxel_size 0.005`
to reduce the number of displayed points.

With the local `.venv` prepared, `./scripts/run_office_loop.sh` performs the
unzip and launches this saved-output example in one command. Additional options
can be appended, such as `./scripts/run_office_loop.sh --device cpu`.

### Viewing a saved dense map

If a dense reconstruction is slow to open in the browser, display a sample of
the saved PCD without running inference again:

```bash
.venv/bin/python scripts/view_saved_map.py \
  --point_cloud logs/640_car_detailed_poses_points.pcd \
  --poses logs/640_car_detailed_poses.txt
```

This viewer starts with 300,000 displayed points and a camera trajectory.
Use **Displayed points** to adjust the display budget, or **Fit map** to reset
the camera. The full PCD file is preserved. Use `--port 8081` if another viewer
is already using port 8080; `--poses` is optional.

The saved-map viewer memory-maps the binary XYZ/RGB PCD and loads only the
displayed sample. Dense PCD export also writes frames incrementally, avoiding
an extra full-map copy when processing long driving sequences.

### BEV and contour exports

Create RGB bird's-eye imagery, surface elevation, and estimated ground contours
from a saved road reconstruction:

```bash
.venv/bin/python scripts/export_bev_maps.py \
  --point_cloud logs/640_car_detailed_poses_points.pcd \
  --poses logs/640_car_detailed_poses.txt \
  --output_dir logs/640_car_bev
```

Outputs include `bev_rgb.png`, `surface_elevation.png`, `ground_contours.png`,
`ground_contours.svg`, `overview.png`, contour vertices in `contour_lines.csv`,
and numerical grids with support counts in `rasters.npz`. `metadata.json`
records the local coordinate basis, cell size, height reference, and assumptions.

Camera orientations estimate the up direction. Ground is a heuristic based on
road-colored points and their height relative to the camera trajectory; it is
not a surveyed bare-earth terrain model. Unsupported cells remain unknown.
By default, coordinates and heights use unscaled reconstruction units, without
a geographic reference. `--meters_per_unit` accepts an independently measured
scale; `--cell_size` controls raster resolution in the selected output units.
Scaling alone does not correct orientation errors or reconstruction drift.
For large reconstructions, add `--max_points 2000000` to bound BEV memory use.
This samples across the full PCD; metadata records both the original and
rasterized point counts. Nearly closed routes use their principal horizontal
trajectory axis because their endpoint displacement does not define a stable
map direction.
An optional `--up_vector X Y Z` specifies a known vertical direction in the
reconstruction coordinates, for example after registration to a reference
trajectory. Its provenance must be distinguished from measured gravity.

For long driving sequences, use `--headless --log_results` in `main.py` to
compute without repeatedly redrawing the full map. Open the saved PCD with
`scripts/view_saved_map.py` afterward. Dense points are saved before quaternion
pose conversion, and `*_camera_matrices.npz` preserves frame IDs and projective
camera matrices for recovery. This backup includes overlapping frame duplicates.

Use the `--run_os` flag to enable 3D open-set object detection. This will prompt the user for text queries and plot a 3D bounding box of the detection on the map in viser. The office loop scene does not have very many interesting objects, but some example queries that can be used are "coffee machine", "sink", "printer", "cone", and "refrigerator." For some example scenes with more interesting objects, check out the Clio apartment and cubicle scene which can be downloaded
from [here](https://www.dropbox.com/scl/fo/5bkv8rsa2xvwmvom6bmza/AOc8VW71kuZCgQjcw_REbWA?rlkey=wx1njghufcxconm1znidc1hgw&e=1&st=c809h8h3&dl=0).

<p align="center">
  <img src="assets/office_loop_figure.png" width="300">
</p>


### Collecting Custom Data

To quickly collect a test on a custom dataset, you can record a trajectory with a cell phone and convert the MOV file to a folder of images with:

```
mkdir <desired_location>/img_folder
```

And then, run the command below:

```
ffmpeg -i /path/to/video.MOV -vf "fps=10" <desired_location>/img_folder/frame_%04d.jpg
```
Note while vertical cell phone videos can work, to avoid images being cropped it is recommended to use horizontal videos.

### Adjusting Parameters

See main.py or run `--help` from main.py to view all parameters.

For visualizing larger datasets, displaying all 3D points in Viser can either slow or crash
the visualizer. One way to mitigate this is to sparsify the point cloud that is sent to Viser which can be done with `--vis_voxel_size 0.005`. Increasing the number will decrease the number of displayed points. Note that this does not affect the number of points stored or used internally in VGGT-SLAM.
Also, by default, camera images are not shown in Viser (only frustums). The images can be added with `--vis_imgs`, but this will slow down the visualizer.

---

## Running Evaluations

For the local PandaSet 003 test, run `scripts/evaluate_pandaset.py` with an
exported pose file and the matching `camera/front_camera` folder. It compares
positions after fitted Sim(3) alignment. See [the PandaSet 003 test report](docs/PANDASET003_TEST.md)
for commands, results, and limitations.

For KITTI-360, `scripts/evaluate_kitti360.py` compares exported frame-index poses
with the supplied `cam0_to_world.txt` after fitted Sim(3) alignment:

```bash
.venv/bin/python scripts/evaluate_kitti360.py \
  --estimated_poses logs/kitti360_0000_poses.txt \
  --reference_poses logs/kitti360_0000_reference/cam0_to_world.txt \
  --output_dir logs/kitti360_0000_evaluation
```

Use the rectified camera poses (`cam0_to_world.txt`), rather than the IMU-frame
`poses.txt`. Sparse reference frame IDs are matched exactly; unmatched frames
are excluded. The reported ATE is not the official KITTI segment-drift metric.

To run evaluation on TUM, first install the datasets using the provided download instructions from [MASt3R-SLAM](https://github.com/rmurai0610/MASt3R-SLAM?tab=readme-ov-file#examples).
Install `evo` with `python -m pip install evo` and set
`TUM_DATASET_PATH=/absolute/path/to/MASt3R-SLAM/datasets/tum/` when invoking
`evals/eval_tum.sh`. The script also requires `bc`. This checkout contains the
TUM evaluation script; it does not contain an `eval_7scenes.sh` script.

#### In Tum Dataset

To run on TUM, run `./evals/eval_tum.sh <w>` and then run `python evals/process_logs_tum.py --submap_size <w>` to analyze and print the results, where w is
the submap size, for example:

```
TUM_DATASET_PATH=/absolute/path/to/MASt3R-SLAM/datasets/tum/ ./evals/eval_tum.sh 32
```

```
python evals/process_logs_tum.py --submap_size 32
```

To visualize the maps as they being constructed, inside the bash scripts add `--vis_map`. This will update the viser map each time the submap is updated.

## Running Online
To run online, plug in a RealSense camera and run `python main_realtime.py --vis_map`. Support for open-set object detection can be enabled with `--run_os` and objects can be queried in Viser. Note that it may be desirable to reduce submap size when running the realtime code
just to have more frequent map updates. For example, by adding `--submap_size 8`.

## News and Updates
* May 2025: VGGT-SLAM 1.0 is released
* August 2025: SL(4) optimization is integrated into the official GTSAM repo
* September 2025: VGGT-SLAM 1.0 Accepted to Neurips 2025
* November 2025: VGGT-SLAM 1.0 Featured in MIT News [article](https://news.mit.edu/2025/teaching-robots-to-map-large-environments-1105)
* January 2026: VGGT-SLAM 2.0 is released
* May 2026: VGGT-SLAM 2.0 Accepted to RSS 2026
* May 2026: FOUND-IT is released [link](https://arxiv.org/abs/2605.25371) which builds a 3D scene graph on top of VGGT-SLAM 2.0
* June 2026: Real-time code added along with upgraded features to the visualizer


## Acknowledgement

This work was supported in part by the NSF Graduate Research Fellowship
Program under Grant 2141064, the ARL DCIST program, and the ONR
RAPID program.

## Citation

If our code is helpful, please cite our papers as follows:

```
@article{maggio2025vggt-slam,
  title={{VGGT-SLAM}: Dense RGB SLAM Optimized on the SL (4) Manifold},
  author={Maggio, Dominic and Lim, Hyungtae and Carlone, Luca},
  journal={Advances in Neural Information Processing Systems},
  volume={39},
  year={2025}
}
```

```
@article{maggio2025vggt-slam2,
  title={{VGGT-SLAM 2.0}: Real-time Dense Feed-forward Scene Reconstruction},
  author={Maggio, Dominic and Carlone, Luca},
  journal={Robotics: Science and Systems},
  year={2026}
}
```

