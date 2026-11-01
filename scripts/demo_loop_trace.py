"""Summarize recorded loop constraints and reference-position checks."""
import argparse
import json
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    events = [json.loads(line) for line in (args.run_dir / "events.jsonl").read_text().splitlines()]
    rows = np.loadtxt(args.reference, ndmin=2)
    ref = dict(zip(rows[:, 0].astype(int), rows[:, 1:].reshape(-1, 4, 4)[:, :3, 3]))
    candidates = {e["payload"]["match_id"]: e for e in events if e["event_type"] == "loop_candidate"}
    validations = {e["payload"]["match_id"]: e for e in events if e["event_type"] == "loop_validation"}
    constraints = [e for e in events if e["event_type"] == "loop_constraint_added"]
    optimizations = [e for e in events if e["event_type"] == "optimization_finished"]
    traces = []
    for edge in constraints:
        match_id = edge["payload"]["match_id"]
        candidate, validation = candidates[match_id], validations[match_id]
        payload = candidate["payload"]
        query = int(Path(payload["query_source"]).stem)
        target = int(Path(payload["candidate_source"]).stem)
        optimization = next(e for e in optimizations if e["seq"] > edge["seq"])
        step = optimization["payload"]["step"]
        before = np.load(args.run_dir / "snapshots" / str(step) / "before.npz")
        after = np.load(args.run_dir / "snapshots" / str(step) / "after.npz")
        if not np.array_equal(before["node_ids"], after["node_ids"]):
            raise ValueError("snapshot node sets differ")
        traces.append({"match_id": match_id, "query_frame_id": query, "candidate_frame_id": target,
                       "reference_distance_m": float(np.linalg.norm(ref[query] - ref[target])) if query in ref and target in ref else None,
                       "retrieval_distance": payload["retrieval_distance"],
                       "image_match_ratio": validation["payload"]["image_match_ratio"],
                       "accepted": validation["payload"]["accepted"], "constraint_event_seq": edge["seq"],
                       "optimization": optimization["payload"],
                       "max_homography_element_change": float(np.max(np.abs(after["homographies"] - before["homographies"]))),
                       "query_image": candidate["asset_paths"]["query"], "candidate_image": candidate["asset_paths"]["candidate"]})
    result = {"reference_for_evaluation_only": str(args.reference.resolve()), "traces": traces,
              "limitations": ["reference distance alone does not establish loop correctness", "graph objective is not trajectory accuracy"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
