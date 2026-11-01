"""Memory-bounded binary XYZ/RGB PCD input and output."""

from pathlib import Path
import tempfile

import numpy as np


def read_cloud(path):
    """Memory-map the binary XYZ/RGB layout exported by this project/Open3D."""
    path = Path(path)
    with path.open("rb") as stream:
        header = {}
        while True:
            raw = stream.readline()
            if not raw:
                raise ValueError("Missing PCD DATA header")
            line = raw.decode("ascii").strip()
            if line and not line.startswith("#"):
                key, *values = line.split()
                header[key] = values
                if key == "DATA":
                    offset = stream.tell()
                    break
    if (header.get("DATA") != ["binary"]
            or header.get("FIELDS") != ["x", "y", "z", "rgb"]
            or header.get("SIZE") != ["4"] * 4
            or header.get("TYPE") not in (["F", "F", "F", "U"], ["F"] * 4)
            or header.get("COUNT") != ["1"] * 4):
        raise ValueError("Expected an uncompressed binary XYZ/RGB PCD with four 4-byte fields")
    count = int(header["POINTS"][0])
    if count < 1 or path.stat().st_size != offset + count * 16:
        raise ValueError("Invalid PCD point count or payload size")
    return np.memmap(path, dtype=[("xyz", "<f4", (3,)), ("rgb", "<u4")],
                     mode="r", offset=offset, shape=(count,))


def unpack_rgb(packed):
    return np.stack([(packed >> 16) & 255, (packed >> 8) & 255, packed & 255], axis=-1).astype(np.uint8)


def write_cloud_chunks(path, chunks):
    """Atomically write chunks of Nx3 points and matching uint8 RGB colors."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    def header(count):
        return ("# .PCD v0.7\nVERSION 0.7\nFIELDS x y z rgb\nSIZE 4 4 4 4\n"
                "TYPE F F F U\nCOUNT 1 1 1 1\n"
                f"WIDTH {count:20d}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\n"
                f"POINTS {count:20d}\nDATA binary\n").encode("ascii")

    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w+b", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(header(0))
            count = 0
            for points, colors in chunks:
                points = np.asarray(points, dtype=np.float32)
                colors = np.asarray(colors, dtype=np.uint8)
                if points.ndim != 2 or points.shape[1] != 3 or colors.shape != points.shape:
                    raise ValueError("Expected matching Nx3 point and RGB arrays")
                valid = np.isfinite(points).all(axis=1)
                points, colors = points[valid], colors[valid]
                packed = np.empty(len(points), dtype=[("xyz", "<f4", (3,)), ("rgb", "<u4")])
                packed["xyz"] = points
                rgb = colors.astype(np.uint32)
                packed["rgb"] = (rgb[:, 0] << 16) | (rgb[:, 1] << 8) | rgb[:, 2]
                stream.write(packed.tobytes())
                count += len(points)
            stream.seek(0)
            stream.write(header(count))
        temporary.replace(path)
        return count
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
