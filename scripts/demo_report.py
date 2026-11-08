"""Generate a compact Markdown inventory from demo run manifests and evidence."""

import argparse
import json
from pathlib import Path


def _point_count(path):
    try:
        with path.open("rb") as stream:
            for _ in range(100):
                line = stream.readline()
                if not line or len(line) > 4096:
                    break
                if line.startswith(b"POINTS "):
                    return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return None


def collect(runs_root):
    rows = []
    for manifest_path in sorted(Path(runs_root).glob("*/manifest.json")):
        run_dir = manifest_path.parent
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        events = []
        event_path = run_dir / "events.jsonl"
        if event_path.is_file():
            for line in event_path.read_text().splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        metrics = []
        metric_paths = set(run_dir.glob("evaluation*/trajectory_metrics.json"))
        metric_paths.update(run_dir.glob("*/trajectory_metrics.json"))
        for path in sorted(metric_paths):
            try:
                metrics.append(json.loads(path.read_text()))
            except (OSError, json.JSONDecodeError):
                continue
        assets = manifest.get("assets", {})
        point_asset = assets.get("point_cloud")
        point_path = (Path(point_asset["path"]) if isinstance(point_asset, dict)
                      else run_dir / point_asset if point_asset else None)
        video_summary_path = run_dir / "video_summary.json"
        try:
            video_summary = json.loads(video_summary_path.read_text())
        except (OSError, json.JSONDecodeError):
            video_summary = {}
        evidence = sorted(path.relative_to(run_dir).as_posix()
                          for path in (run_dir / "evidence").rglob("*") if path.is_file()) if (run_dir / "evidence").is_dir() else []
        rows.append({"run_id": manifest.get("run_id", run_dir.name),
                     "source_mode": manifest.get("source_mode", "unknown"),
                     "status": manifest.get("status", "unknown"),
                     "frames": sum(event.get("event_type") == "frame_selected" for event in events),
                     "submaps": sum(event.get("event_type") == "submap_created" for event in events),
                     "loop_candidates": sum(event.get("event_type") == "loop_candidate" for event in events),
                     "loop_accepted": sum(event.get("event_type") == "loop_validation"
                                          and bool(event.get("payload", {}).get("accepted")) for event in events),
                     "object_queries": sum(event.get("event_type") == "object_query_result" for event in events),
                     "point_count": _point_count(point_path) if point_path else None,
                     "ate": [metric.get("ate_rmse_m") for metric in metrics],
                     "video": video_summary,
                     "missing_assets": [key for key, value in assets.items()
                                        if isinstance(value, str) and not (run_dir / value).is_file()],
                     "evidence": evidence})
    return rows


def render(rows):
    lines = ["# VGGT-SLAM Demo Results", "",
             "Generated from local run manifests, event logs, metrics, and evidence files. "
             "Metrics keep the alignment and ground-truth limitations recorded by each run.", "",
             "| Run | Input | Status | Frame events | Submaps | Loops accepted | Object queries | PCD points | ATE RMSE |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    details = []
    for row in rows:
        ate = ", ".join("N/A" if value is None else f"{value:.3f} m" for value in row["ate"]) or "N/A"
        points = f"{row['point_count']:,}" if row["point_count"] is not None else "N/A"
        lines.append(f"| `{row['run_id']}` | {row['source_mode']} | {row['status']} | {row['frames']} | "
                     f"{row['submaps']} | {row['loop_accepted']} / {row['loop_candidates']} | "
                     f"{row['object_queries']} | {points} | {ate} |")
        if row["video"]:
            video = row["video"]
            details.extend(["", f"`{row['run_id']}` video: {video.get('decoded_frames', 'N/A')} decoded, "
                          f"{video.get('selected_keyframes', 'N/A')} selected keyframes, "
                          f"{video.get('keyframe_backlog_dropped', 'N/A')} dropped, "
                          f"pacing `{video.get('pacing', 'unknown')}`, submap latency p50/p95 "
                          f"{video.get('submap_latency_seconds_p50', 'N/A')}/"
                          f"{video.get('submap_latency_seconds_p95', 'N/A')} s; ATE requires a timestamp-aligned reference."])
        if row["missing_assets"]:
            details.extend(["", f"Missing assets for `{row['run_id']}`: {', '.join(row['missing_assets'])}."])
        if row["evidence"]:
            links = [f"[`{path}`](../logs/demo_runs/{row['run_id']}/{path})" for path in row["evidence"]]
            details.extend(["", f"Evidence for `{row['run_id']}`: " + ", ".join(links) + "."])
    if not rows:
        lines.extend(["", "No run manifests were found."])
    lines.extend(details)
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=Path("logs/demo_runs"))
    parser.add_argument("--output", type=Path, default=Path("docs/DEMO_RESULTS.md"))
    parser.add_argument("--force", action="store_true", help="replace the output report")
    args = parser.parse_args()
    if args.output.exists() and not args.force:
        parser.error(f"output already exists; pass --force to replace: {args.output}")
    rows = collect(args.runs_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(rows), encoding="utf-8")
    print(f"Wrote {len(rows)} run summaries to {args.output}")


if __name__ == "__main__":
    main()
