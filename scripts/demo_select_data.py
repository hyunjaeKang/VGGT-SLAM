"""Select consecutive driving frames with the existing optical-flow tracker."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from vggt_slam.frame_overlap import FrameTracker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-dir", type=Path, required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--disparity", type=float, required=True, help="threshold in original image pixels")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reference", type=Path, help="reference pose file, for post-selection diagnostics only")
    args = parser.parse_args()
    if args.start < 0 or args.end <= args.start or args.disparity < 0:
        parser.error("invalid range or disparity")
    paths = [args.image_dir / f"{i:010d}.png" for i in range(args.start, args.end + 1)]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        parser.error(f"missing {len(missing)} source frames; first: {missing[0]}")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    cv2.setNumThreads(2)
    tracker = FrameTracker()
    selected = []
    for index, path in enumerate(paths, args.start):
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"cannot decode {path}")
        if tracker.compute_disparity(image, args.disparity):
            selected.append(index)
        if (index - args.start) % 200 == 0:
            print(f"processed {index - args.start + 1}/{len(paths)}, selected {len(selected)}", flush=True)
    if selected[-1] != args.end:
        selected.append(args.end)
        forced_end = True
    else:
        forced_end = False
    ids_path = args.output_dir / "frame_ids.json"
    ids_path.write_text(json.dumps(selected, indent=2) + "\n")
    display_indices = sorted(set(np.linspace(0, len(selected) - 1, min(30, len(selected)), dtype=int).tolist()))
    thumbs = [selected[i] for i in display_indices]
    cell_w, cell_h = 320, 115
    sheet = Image.new("RGB", (cell_w * 3, cell_h * ((len(thumbs) + 2) // 3)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(thumbs):
        with Image.open(args.image_dir / f"{frame:010d}.png") as im:
            im.thumbnail((cell_w, cell_h - 20))
            x, y = (index % 3) * cell_w, (index // 3) * cell_h
            sheet.paste(im, (x, y + 20))
            draw.text((x + 4, y + 2), str(frame), fill="black")
    sheet.save(args.output_dir / "contact_sheet.jpg", quality=90)
    result = {"source": str(args.image_dir.resolve()), "inclusive_range": [args.start, args.end],
              "input_frames": len(paths), "selected_frames": len(selected), "threshold_original_pixels": args.disparity,
              "selected_ids_sha256": hashlib.sha256(ids_path.read_bytes()).hexdigest(),
              "forced_last_frame": forced_end, "contact_sheet_frame_ids": thumbs,
              "selection_method": "existing FrameTracker optical flow in original frame order"}
    if args.reference:
        data = np.loadtxt(args.reference, ndmin=2)
        reference_ids = data[:, 0].astype(int)
        poses = data[:, 1:].reshape(-1, 4, 4)[:, :3, 3]
        window = (reference_ids >= args.start) & (reference_ids <= args.end)
        ids, pos = reference_ids[window], poses[window]
        if len(pos) and ids[0] == args.start:
            result["reference_diagnostics_only"] = {"reference_path": str(args.reference.resolve()),
                "matched_reference_frames": len(ids), "path_length_m": float(np.linalg.norm(np.diff(pos, axis=0), axis=1).sum()),
                "max_displacement_from_start_m": float(np.linalg.norm(pos - pos[0], axis=1).max()),
                "endpoint_distance_m": float(np.linalg.norm(pos[-1] - pos[0])),
                "last_reference_frame": int(ids[-1])}
    (args.output_dir / "selection_report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
