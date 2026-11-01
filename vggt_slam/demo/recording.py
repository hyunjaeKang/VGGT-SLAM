"""Record CPU inference outputs for later inspection, without retaining tensors."""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from vggt_slam.demo.status import write_json_atomic
from vggt_slam.demo.image_mapping import crop_mappings


class Recorder:
    def __init__(self, run_dir):
        self.run_dir = Path(run_dir)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        self.run_id = manifest["run_id"]
        self.events = self.run_dir / "events.jsonl"
        # A fresh recorder must not overwrite or append to another session.
        self._stream = self.events.open("x", encoding="utf-8")
        self._seq = 0

    def close(self):
        self._stream.close()

    def event(self, event_type, *, source_frame_id=None, submap_id=None, asset_paths=None, payload=None):
        event = {"schema_version": 1, "seq": self._seq, "run_id": self.run_id,
                 "event_type": event_type, "wall_time": datetime.now(timezone.utc).isoformat(),
                 "source_frame_id": source_frame_id, "submap_id": submap_id,
                 "asset_paths": asset_paths or {}, "payload": payload or {}}
        self._stream.write(json.dumps(event, allow_nan=False) + "\n")
        self._stream.flush()
        self._seq += 1

    def loop_candidate(self, match_id, query_path, candidate_path, submap_id, payload):
        folder = self.run_dir / "loops" / match_id
        folder.mkdir(parents=True, exist_ok=False)
        for source, name in ((query_path, "query.png"), (candidate_path, "candidate.png")):
            with Image.open(source) as image:
                image.convert("RGB").save(folder / name)
        rel = folder.relative_to(self.run_dir)
        self.event("loop_candidate", submap_id=submap_id,
                   asset_paths={"query": str(rel / "query.png"), "candidate": str(rel / "candidate.png")},
                   payload={**payload, "match_id": match_id, "query_source": str(query_path),
                            "candidate_source": str(candidate_path)})

    def record_submap(self, submap_id, frame_ids, predictions, overlap_count=0):
        images = np.asarray(predictions["images"])
        depth = np.asarray(predictions["depth"])
        confidence = np.asarray(predictions["depth_conf"])
        intrinsics = np.asarray(predictions["intrinsic"])
        count = len(frame_ids)
        if (images.ndim != 4 or images.shape[:2] != (count, 3) or depth.ndim != 4
                or depth.shape[0] != count or depth.shape[-1] != 1
                or confidence.shape != depth.shape[:3] or images.shape[2:] != depth.shape[1:3]
                or intrinsics.shape != (count, 3, 3)):
            raise ValueError("inconsistent frame, depth, confidence or intrinsic shapes")
        ids = [item["frame_id"] if isinstance(item, dict) else item for item in frame_ids]
        if len(set(map(str, ids))) != count or not 0 <= overlap_count <= count:
            raise ValueError("invalid frame IDs or overlap count")
        paths = [item.get("source") if isinstance(item, dict) else None for item in frame_ids]
        mappings = crop_mappings(paths, images.shape[2:]) if all(paths) else [None] * count
        submap = self.run_dir / "submaps" / str(int(submap_id))
        submap.mkdir(parents=True, exist_ok=False)
        self.event("submap_created", submap_id=int(submap_id), payload={"frame_count": count})
        for i, frame_id in enumerate(frame_ids):
            source = frame_id if isinstance(frame_id, dict) else {"frame_id": frame_id}
            frame_id = source["frame_id"]
            frame_dir = submap / "frames" / str(i)
            frame_dir.mkdir(parents=True)
            rgb = np.clip(images[i].transpose(1, 2, 0) * 255, 0, 255).astype(np.uint8)
            Image.fromarray(rgb).save(frame_dir / "rgb.png")
            values = depth[i, ..., 0].astype(np.float32)
            conf = confidence[i].astype(np.float32)
            valid = np.isfinite(values) & np.isfinite(conf) & (values > 0)
            np.savez_compressed(frame_dir / "depth.npz", depth=values, confidence=conf,
                                valid=valid, intrinsic=intrinsics[i].astype(np.float32))
            finite = values[valid]
            bounds = [float(finite.min()), float(finite.max())] if finite.size else None
            for name, array, mask in (("depth", values, valid), ("confidence", conf, np.isfinite(conf))):
                finite_values = array[mask]
                preview = np.zeros(array.shape, dtype=np.uint8)
                if finite_values.size:
                    low, high = float(finite_values.min()), float(finite_values.max())
                    if high > low:
                        preview[mask] = np.clip((array[mask] - low) / (high - low) * 255, 0, 255).astype(np.uint8)
                Image.fromarray(preview).save(frame_dir / f"{name}.png")
            rel = frame_dir.relative_to(self.run_dir)
            meta = {"source_frame_id": str(frame_id), "submap_id": int(submap_id),
                    "submap_frame_index": i, "overlap": i < overlap_count,
                    "rgb_depth_mapping": "same preprocessed pixel grid", "depth_units": "relative, unverified",
                    "depth_visualization_range": bounds, "resolution_hw": list(values.shape),
                    "source_path": source.get("source"), "source_timestamp": source.get("timestamp"),
                    "source_timestamp_type": source.get("timestamp_type", "unavailable"),
                    "source_to_preprocessed_mapping": mappings[i]}
            write_json_atomic(frame_dir / "metadata.json", meta)
            self.event("frame_selected", source_frame_id=str(frame_id), submap_id=int(submap_id),
                       asset_paths={"rgb": str(rel / "rgb.png"), "depth": str(rel / "depth.npz"),
                                    "depth_preview": str(rel / "depth.png"),
                                    "confidence_preview": str(rel / "confidence.png"),
                                    "metadata": str(rel / "metadata.json")}, payload={"overlap": i < overlap_count})
