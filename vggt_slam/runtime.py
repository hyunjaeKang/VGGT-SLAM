"""Shared device selection and argument checks for both entry points."""

import torch


def select_device(requested="auto"):
    if requested == "auto":
        if torch.cuda.is_available():
            requested = "cuda"
        elif torch.backends.mps.is_available():
            requested = "mps"
        else:
            requested = "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but is unavailable")
    if requested == "mps" and not torch.backends.mps.is_available():
        raise ValueError("MPS was requested but is unavailable")
    return torch.device(requested)


def model_dtype(device):
    if device.type == "cuda":
        return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    return torch.float32


def validate_args(parser, args):
    if args.submap_size < 1:
        parser.error("--submap_size must be positive")
    if args.overlapping_window_size != 1:
        parser.error("only --overlapping_window_size 1 is supported")
    if args.max_loops not in (0, 1):
        parser.error("--max_loops must be 0 or 1")
    if not 0 <= args.conf_threshold < 100:
        parser.error("--conf_threshold must be in [0, 100)")
    if args.min_disparity < 0:
        parser.error("--min_disparity must be non-negative")
    if args.vis_voxel_size is not None and args.vis_voxel_size <= 0:
        parser.error("--vis_voxel_size must be positive")
