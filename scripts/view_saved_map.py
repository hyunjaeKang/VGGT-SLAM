"""Display a saved dense reconstruction with a bounded browser point budget."""

import argparse
from pathlib import Path
import threading
import time

import numpy as np
import viser
from vggt_slam.pcd_io import read_cloud, unpack_rgb


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--point_cloud", type=Path, required=True)
    parser.add_argument("--poses", type=Path)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--max_points", type=int, default=300_000)
    args = parser.parse_args()
    if not 50_000 <= args.max_points <= 2_000_000:
        parser.error("--max_points must be between 50000 and 2000000")
    if not args.point_cloud.is_file():
        parser.error(f"Point cloud not found: {args.point_cloud}")

    cloud = read_cloud(args.point_cloud)
    points = cloud["xyz"]
    print(f"Loaded {len(points):,} points; full-resolution file is preserved.", flush=True)

    server = viser.ViserServer(host="127.0.0.1", port=args.port)
    budget = server.gui.add_slider("Displayed points", min=50_000, max=2_000_000,
                                   step=50_000, initial_value=args.max_points)
    status = server.gui.add_markdown("")
    update_lock = threading.Lock()
    cloud_handle = None

    # Spread samples across all frames rather than displaying just the start.
    preview_ids = np.linspace(0, len(points) - 1, min(50_000, len(points)), dtype=np.int64)
    preview = points[preview_ids]
    low, high = np.quantile(preview, [0.02, 0.98], axis=0)
    center = (low + high) / 2
    radius = max(float(np.linalg.norm(high - low)), 0.1)

    def update_cloud(_=None):
        nonlocal cloud_handle
        with update_lock:
            count = min(int(budget.value), len(points))
            indices = np.linspace(0, len(points) - 1, count, dtype=np.int64)
            selected_points = points[indices].astype(np.float32)
            selected_colors = unpack_rgb(cloud["rgb"][indices])
            valid = np.isfinite(selected_points).all(axis=1)
            if cloud_handle is not None:
                cloud_handle.remove()
            cloud_handle = server.scene.add_point_cloud(
                "/map", points=selected_points[valid], colors=selected_colors[valid],
                point_size=radius / 2000, point_shape="square",
            )
            status.content = f"Showing **{valid.sum():,} / {len(points):,}** points. Full detail is saved in the PCD file."
            print(f"Displaying {valid.sum():,} points", flush=True)

    update_cloud()
    budget.on_update(update_cloud)

    if args.poses is not None:
        poses = np.loadtxt(args.poses, ndmin=2)
        positions = poses[:, 1:4].astype(np.float32)
        if len(positions) > 1:
            server.scene.add_line_segments(
                "/trajectory", points=np.stack([positions[:-1], positions[1:]], axis=1),
                colors=(255, 100, 40), line_width=2,
            )

    def fit_view(client):
        client.camera.up_direction = (0, -1, 0)
        client.camera.position = center + radius * np.array([0.35, -0.5, -0.65])
        client.camera.look_at = center

    server.on_client_connect(fit_view)
    fit_button = server.gui.add_button("Fit map")

    @fit_button.on_click
    def fit_all(_):
        for client in server.get_clients().values():
            fit_view(client)

    print(f"Viewer ready at http://localhost:{server.get_port()}", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
