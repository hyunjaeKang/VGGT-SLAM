"""Single-writer run lifecycle and atomic JSON persistence."""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def write_json_atomic(path, value):
    path = Path(path)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="." + path.name + ".", delete=False) as stream:
            name = stream.name
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def transition(run_dir, state, *, device=None, models=None, error=None):
    """Update manifest atomically. A single worker must own a run at a time."""
    run_dir = Path(run_dir)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    transitions = {"prepared": {"running", "failed"}, "running": {"completed", "failed"}}
    current = manifest["status"]
    if state not in transitions.get(current, set()):
        raise ValueError(f"invalid run transition: {current} -> {state}")
    if state == "running" and (not device or not isinstance(models, dict) or not models):
        raise ValueError("running requires device and model/checkpoint identifiers")
    if state == "failed" and not error:
        raise ValueError("failed requires an error reason")
    now = datetime.now(timezone.utc).isoformat()
    manifest["status"] = state
    manifest["updated_at"] = now
    if state == "running":
        manifest["started_at"] = now
        manifest["environment"]["device"] = device
        manifest["environment"]["models"] = models
    if state in ("completed", "failed"):
        manifest["finished_at"] = now
    if error:
        manifest["error"] = str(error)
    # Manifest is authoritative; status.json is a convenience snapshot.
    write_json_atomic(manifest_path, manifest)
    write_json_atomic(run_dir / "status.json", {"schema_version": 1, "run_id": manifest["run_id"],
                                              "status": state, "updated_at": now, "error": error})
