# TerraScene · Mapping Studio

Interactive interface prototype and a Korean engineering plan for a VGGT-SLAM 2.0 mapping demo.

Open `dist/index.html` directly in a modern desktop browser. The full plan is at `dist/plan.html`. No package installation, external asset, inference server or model download is required. A standalone copy of the interface is also included in the downloadable deliverables.

## What works

- Synthetic replay, local video playback, orbit/zoom of a real 3D coordinate set.
- Occupancy, footprint-inflated costs and connected-component views.
- Actual A-star grid path search with eight-connected movement and no corner cutting.
- Start/goal selection, footprint radius, unknown-space policy and a height slice.
- Sample object filtering/highlighting and JSON/PLY export with synthetic provenance.

## Prototype boundary

All reconstruction geometry, semantic objects, observation masks, keyframes and revisions are synthetic. Local video playback does not reconstruct the video. Three-dimensional occupied voxels represent synthetic surface cells only; a probabilistic free/occupied/unknown volume is planned, not implemented. Circular footprint search does not model car-like steering or dynamics. No timing or GPU memory values are presented as model benchmarks.

The plan distinguishes inspected upstream behavior from original engineering proposals and lists incomplete source inspection. Actual engine integration requires a pinned source audit, exact license/weight compatibility review, metric/gravity calibration, and empirical measurement. No third-party model weights are included.

## Folder and packaging

This prototype lives in `web_app/` (formerly `TerraScene/`). The TerraScene product name and standalone HTML filenames are retained.

Run the following commands from `web_app/`. To generate a downloadable package, run `python package_deliverables.py`; output is written to `web_app/deliverables/`, with a `web_app/` root directory inside the ZIP.

## Verification

```sh
node --check dist/core.js
node --check dist/app.js
node tests/core.test.js
node tests/interface.test.js
python build_plan.py
```

The interface test checks state transitions with a DOM/canvas stub. It does not substitute for visual browser verification. Full browser rendering was not available in the creation environment.

## Abbreviations

VGGT: Visual Geometry Grounded Transformer. SLAM: Simultaneous Localization and Mapping. JSON: JavaScript Object Notation. PLY: Polygon File Format. GPU: Graphics Processing Unit. DOM: Document Object Model. The complete glossary is in the plan and the in-app help.
