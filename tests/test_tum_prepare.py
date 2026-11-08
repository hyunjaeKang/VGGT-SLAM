import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

from PIL import Image


def test_tum_sample_preserves_rgb_times_without_using_groundtruth(tmp_path):
    archive = tmp_path / "sample.tgz"
    prefix = "rgbd_dataset_test/"
    with tarfile.open(archive, "w:gz") as tar:
        def add(name, data):
            member = tarfile.TarInfo(prefix + name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))

        add("rgb.txt", b"# RGB\n1300000000.1 rgb/a.png\n1300000000.2 rgb/b.png\n1300000000.3 rgb/c.png\n")
        add("groundtruth.txt", b"# Never pass this to inference\n")
        for name in ("a", "b", "c"):
            image = io.BytesIO(); Image.new("RGB", (4, 4)).save(image, format="PNG")
            add(f"rgb/{name}.png", image.getvalue())
    output, runs = tmp_path / "sample", tmp_path / "runs"
    subprocess.run([sys.executable, "scripts/demo_prepare_tum.py", "--archive", str(archive),
                    "--output", str(output), "--run-id", "test_tum", "--count", "3",
                    "--runs-root", str(runs)], check=True)
    selection = json.loads((runs / "test_tum/selection.json").read_text())
    assert [frame["frame_id"] for frame in selection["frames"]] == [0, 1, 2]
    assert [frame["timestamp"] for frame in selection["frames"]] == [1300000000.1, 1300000000.2, 1300000000.3]
    assert all(Path(frame["source"]).parent == output / "images" for frame in selection["frames"])
    assert len(list((output / "images").iterdir())) == 3
