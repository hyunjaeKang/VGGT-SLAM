"""VGGT-SLAM only, opt-in small model input and bounded CPU threads."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import main_realtime as engine


def main():
    import torch,cv2
    engine.parser.add_argument('--image_size',type=int,choices=[224,322,378,518],default=378)
    engine.parser.add_argument('--cpu_threads',type=int,choices=[1,2,4,8],default=4)
    engine.parser.set_defaults(camera='video_file',headless=True,no_video_window=True,submap_size=8,
                               min_disparity=45,max_loops=1,slam_fast_start=True,preview_points=10_000)
    engine.parser.add_argument("--min_loop_seconds",type=float,default=10.,help="Exclude loop candidates closer than this many source-video seconds; 0 disables")
    args=engine.parser.parse_args()
    import math
    if not math.isfinite(args.min_loop_seconds) or not 0<=args.min_loop_seconds<=600:engine.parser.error("min_loop_seconds must be 0..600")
    if args.run_os:engine.parser.error('V5 is geometry only; use V4 for object search')
    torch.set_num_threads(args.cpu_threads);cv2.setNumThreads(1)
    # Restrict Torch Hub DINO to the already installed repository: avoid branch
    # discovery HTTP requests and intermittent GitHub timeouts at startup.
    original=torch.hub.load
    def local_hub(repo,model,*values,**kwargs):
        if repo=="facebookresearch/dinov2":
            cached=Path(torch.hub.get_dir())/"facebookresearch_dinov2_main"
            if not cached.is_dir():raise FileNotFoundError(f"Prepare cached DINO repository: {cached}")
            return original(str(cached),model,*values,**{**kwargs,"source":"local"})
        return original(repo,model,*values,**kwargs)
    torch.hub.load=local_hub
    engine.main()


if __name__=='__main__':main()
