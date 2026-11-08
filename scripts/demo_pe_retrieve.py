"""Rank a recorded run's RGB frames with the actual PE model on CPU."""

import argparse
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
import torch
from core.vision_encoder import pe, transforms


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    events = [json.loads(line) for line in (args.run / "events.jsonl").read_text().splitlines()]
    frames = [event for event in events if event["event_type"] == "frame_selected"]
    if not frames:
        parser.error("run contains no recorded frames")
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    model = pe.CLIP.from_config("PE-Core-L14-336", pretrained=True).eval().cpu()
    preprocess = transforms.get_image_transform(model.image_size)
    tokenizer = transforms.get_text_tokenizer(model.context_length)
    embeddings = []
    with torch.inference_mode():
        text = model.encode_text(tokenizer([args.query]), normalize=True)
        for frame in frames:
            with Image.open(args.run / frame["asset_paths"]["rgb"]) as image:
                embeddings.append(model.encode_image(preprocess(image).unsqueeze(0), normalize=True))
        images = torch.cat(embeddings)
        scores = (images @ text.T).squeeze(1).cpu().numpy()
    np.savez_compressed(args.output / "embeddings.npz", images=images.cpu().numpy(), text=text.cpu().numpy())
    best = int(scores.argmax())
    result = {"model": "PE-Core-L14-336", "device": "cpu", "query": args.query,
              "source_run": str(args.run.resolve()), "score_type": "cosine similarity; not probability",
              "scores": scores.tolist(), "best_index": best, "best_frame": frames[best],
              "seconds": time.monotonic() - started}
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
