"""Same checkpoint and frames, synchronized MPS model timings by true input width."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse,json,time,os
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK","1")
import numpy as np
import torch
from vggt.models.vggt import VGGT
from vggt_slam.demo.slam_preprocess import load_images,load_local_weights


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    torch.set_num_threads(4);device='mps' if torch.backends.mps.is_available() else 'cpu'
    selection=json.loads(Path('logs/demo_runs/s03_kitti_loop_on_20261031_01/selection.json').read_text())['frames']
    paths=[r['source'] for r in selection[:4]]
    started=time.perf_counter();model=VGGT();load_local_weights(model);model=model.eval().to(device)
    result={'device':device,'cpu_threads':4,'model_load_seconds':time.perf_counter()-started,'source_paths':paths,'runs':[],'scope':'Model only, 4 same frames. No independent trajectory GT evaluation.'}
    def sync():
        if device=='mps':torch.mps.synchronize()
    for width in [518,378,322,224]:
        images=load_images(paths,width).to(device);times=[]
        for _ in range(3):
            sync();t=time.perf_counter()
            with torch.inference_mode():out=model(images)
            sync();times.append(time.perf_counter()-t)
        depth=out['depth'].float().cpu().numpy()
        row={'width':width,'shape':list(images.shape),'patch_tokens_per_frame':int(images.shape[-1]*images.shape[-2]/196),'seconds':times,'warm_median_seconds':float(np.median(times[1:])),'depth_finite_fraction':float(np.isfinite(depth).mean()),'positive_depth_fraction':float((depth>0).mean())}
        result['runs'].append(row);print(json.dumps(row),flush=True)
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
        del out,images
        if device=='mps':torch.mps.empty_cache()


if __name__=='__main__':main()
