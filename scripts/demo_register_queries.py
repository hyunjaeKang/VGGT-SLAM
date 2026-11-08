"""Create a derived cached run referencing source assets and copying query evidence."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--queries", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    manifest = json.loads((source / "manifest.json").read_text())
    events = [json.loads(line) for line in (source / "events.jsonl").read_text().splitlines()]
    # Validate all inputs before reserving the derived run directory.
    queries = []
    for folder in args.queries:
        provenance = json.loads((folder / "provenance.json").read_text())
        if Path(provenance["source_run"]).resolve() != source:
            parser.error("query belongs to a different source run")
        result = folder / provenance["result"]
        queries.append((provenance, result, json.loads(result.read_text())))
    args.output.mkdir(parents=True, exist_ok=False)
    run_id = args.output.name
    # Share large assets by symlink, while keeping manifest/events/query files independent.
    for path in source.iterdir():
        if path.name in {"manifest.json", "events.jsonl", "status.json", "object_queries", "evidence"}:
            continue
        (args.output / path.name).symlink_to(path, target_is_directory=path.is_dir())
    now = datetime.now(timezone.utc).isoformat()
    manifest.update(run_id=run_id, source_mode="derived_cached_object_queries",
                    parent_run=str(source), derived_at=now, status="completed")
    manifest["limitations"] = manifest.get("limitations", []) + [
        "Derived read-only asset references; source run must remain available",
        "Search inference occurred after SLAM; not simultaneous live inference"]
    for event in events:
        event["run_id"] = run_id
    for provenance, result_path, result in queries:
        target = args.output / "object_queries" / result["query_id"]
        shutil.copytree(result_path.parent, target)
        result["snapshot"] = {"step": provenance["snapshot_step"], "phase": provenance["phase"]}
        (target / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        events.append({"schema_version": 1, "seq": len(events), "run_id": run_id,
                       "event_type": "object_query_result", "wall_time": now,
                       "submap_id": result["submap_id"],
                       "asset_paths": {"result": str((target / "result.json").relative_to(args.output))},
                       "payload": {"query_id": result["query_id"], "query": result["query"],
                                   "provenance": provenance}})
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (args.output / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
    (args.output / "status.json").write_text(json.dumps({"status": "completed", "run_id": run_id}) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
