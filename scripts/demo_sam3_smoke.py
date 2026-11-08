"""Run real SAM3 image inference using a cached checkpoint, without SLAM."""

import argparse
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image
import torch
from huggingface_hub import hf_hub_download
from sam3.model_builder import build_sam3_image_model
from sam3.model.sam3_image_processor import Sam3Processor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--device", choices=["cpu", "mps", "cuda"], default="cpu")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error(f"image does not exist: {args.image}")
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    result = {"image": str(args.image.resolve()), "query": args.query,
              "device": args.device, "torch": torch.__version__, "status": "running",
              "autocast": "bfloat16" if args.device == "cuda" else "disabled"}
    try:
        checkpoint = hf_hub_download("facebook/sam3", "sam3.pt", local_files_only=True)
        print("Loading cached SAM3 checkpoint", flush=True)
        model = build_sam3_image_model(device=args.device, checkpoint_path=checkpoint, load_from_HF=False)
        processor = Sam3Processor(model, device=args.device)
        image = Image.open(args.image).convert("RGB")
        image.save(args.output / "frame.png")
        print("Running image encoder and text prompt", flush=True)
        with torch.inference_mode(), torch.autocast(device_type=args.device, dtype=torch.bfloat16,
                                                   enabled=args.device == "cuda"):
            state = processor.set_image(image)
            output = processor.set_text_prompt(state=state, prompt=args.query)
        masks = output["masks"].detach().cpu().numpy()
        for index, mask in enumerate(masks):
            Image.fromarray(np.squeeze(mask).astype(np.uint8) * 255).save(args.output / f"mask_{index:02d}.png")
        result.update(status="completed", scores=output["scores"].detach().cpu().tolist(),
                      boxes=output["boxes"].detach().cpu().tolist(), mask_count=len(masks),
                      checkpoint=checkpoint)
    except Exception as exc:
        result.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        result["seconds"] = time.monotonic() - started
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
