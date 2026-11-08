"""Select a small TUM RGB-only sample; keep timestamp provenance and GT separate."""

import argparse
import hashlib
import json
from pathlib import Path
import tarfile

import numpy as np

from vggt_slam.demo.prepare import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--count", type=int, default=33)
    parser.add_argument("--runs-root", type=Path, default=Path("logs/demo_runs"))
    args = parser.parse_args()
    if args.count < 3:
        parser.error("count must be at least 3")
    args.output.mkdir(parents=True, exist_ok=False)
    images = args.output / "images"
    images.mkdir()
    with tarfile.open(args.archive) as archive:
        listing = next(member for member in archive.getmembers() if member.name.endswith("/rgb.txt"))
        prefix = listing.name.rsplit("/", 1)[0]
        rows = [line.split() for line in archive.extractfile(listing).read().decode().splitlines()
                if line.strip() and not line.startswith("#")]
        if len(rows) < args.count:
            parser.error("not enough RGB frames")
        selected = np.linspace(0, len(rows) - 1, args.count, dtype=int)
        provenance = []
        for index, source_index in enumerate(selected):
            timestamp, name = rows[source_index]
            member = archive.getmember(prefix + "/" + name)
            if not member.isfile():
                raise ValueError("RGB member must be a regular file")
            (images / f"{index:06d}.png").write_bytes(archive.extractfile(member).read())
            provenance.append({"frame_id": index, "rgb_list_index": int(source_index),
                               "archive_member": member.name, "timestamp_text": timestamp,
                               "timestamp_seconds": float(timestamp)})
        # GT is extracted for evaluation only; neither it nor depth is passed to SLAM.
        (args.output / "groundtruth.txt").write_bytes(archive.extractfile(prefix + "/groundtruth.txt").read())
    timestamps = [item["timestamp_seconds"] for item in provenance]
    if np.any(np.diff(timestamps) <= 0):
        raise ValueError("RGB timestamps must increase")
    timestamp_path = args.output / "timestamps.json"
    timestamp_path.write_text(json.dumps(timestamps) + "\n")
    with args.archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    (args.output / "source.json").write_text(json.dumps({"archive": str(args.archive.resolve()),
        "archive_sha256": digest, "sequence": prefix, "selection": "uniform by RGB row index; no GT selection",
        "frames": provenance}, indent=2) + "\n")
    config = {"run_id": args.run_id, "image_dir": str(images.resolve()),
              "timestamp_file": str(timestamp_path.resolve()), "timestamp_type": "unix_seconds"}
    (args.output / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    print(prepare(config, args.runs_root))


if __name__ == "__main__":
    main()
