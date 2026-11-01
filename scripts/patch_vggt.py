"""Make the SPARK fork honor the model's selected inference precision."""

from pathlib import Path


def patch(path):
    source = path.read_text()
    old = "images = images.to(torch.bfloat16)"
    new = "images = images.to(next(self.parameters()).dtype)"
    if new in source:
        return
    if source.count(old) != 1:
        raise RuntimeError(f"VGGT source changed; inspect the input dtype in {path}")
    path.write_text(source.replace(old, new))


if __name__ == "__main__":
    patch(Path(__file__).resolve().parents[1] / "third_party/vggt/vggt/models/vggt.py")
