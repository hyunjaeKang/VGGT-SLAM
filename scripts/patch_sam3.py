"""Apply diagnosed SAM3 import/cache fixes for CPU image inference."""

from pathlib import Path


def patch(path):
    source = path.read_text()
    eager = "from sam3.model.edt import edt_triton\n"
    anchor = "    fn_mask_dt = edt_triton(padded_fn_masks)"
    lazy = "    from sam3.model.edt import edt_triton\n\n" + anchor
    if lazy in source and not source.startswith(eager) and "\n" + eager not in source:
        return
    if source.count(eager) != 1 or source.count(anchor) != 1:
        raise RuntimeError(f"SAM3 source changed; inspect EDT imports in {path}")
    path.write_text(source.replace(eager, "", 1).replace(anchor, lazy, 1))


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "third_party/sam3/sam3/model"
    patch(root / "sam3_tracker_utils.py")
    path = root / "position_encoding.py"
    source = path.read_text()
    old = 'tensors = torch.zeros((1, 1) + size, device="cuda")'
    new = 'tensors = torch.zeros((1, 1) + size, device="cuda" if torch.cuda.is_available() else "cpu")'
    if new not in source:
        if source.count(old) != 1:
            raise RuntimeError(f"SAM3 source changed; inspect position cache in {path}")
        path.write_text(source.replace(old, new))
    path = root.parent / "perflib/fused.py"
    source = path.read_text()
    anchor = "    self = linear.bias.detach()"
    fallback = '''    if mat1.device.type == "cpu":
        output = linear(mat1)
        if activation in [torch.nn.functional.relu, torch.nn.ReLU]:
            return torch.nn.functional.relu(output)
        if activation in [torch.nn.functional.gelu, torch.nn.GELU]:
            return torch.nn.functional.gelu(output)
        raise ValueError(f"Unexpected activation {activation}")
'''
    if fallback not in source:
        if source.count(anchor) != 1:
            raise RuntimeError(f"SAM3 source changed; inspect fused activation in {path}")
        path.write_text(source.replace(anchor, fallback + anchor))
    path = root / "decoder.py"
    source = path.read_text()
    old = 'feat_size, feat_size, device="cuda"'
    new = 'feat_size, feat_size, device="cuda" if torch.cuda.is_available() else "cpu"'
    if new not in source:
        if source.count(old) != 1:
            raise RuntimeError(f"SAM3 source changed; inspect decoder cache in {path}")
        path.write_text(source.replace(old, new))
    path = root / "geometry_encoders.py"
    source = path.read_text()
    old = 'scale = scale.pin_memory().to(device=boxes_xyxy.device, non_blocking=True)'
    new = '''scale = (scale.pin_memory().to(device=boxes_xyxy.device, non_blocking=True)
                     if boxes_xyxy.device.type == "cuda" else scale.to(boxes_xyxy.device))'''
    if new not in source:
        if source.count(old) != 1:
            raise RuntimeError(f"SAM3 source changed; inspect box scale in {path}")
        path.write_text(source.replace(old, new))
