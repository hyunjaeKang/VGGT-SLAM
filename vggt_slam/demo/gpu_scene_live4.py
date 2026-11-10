"""V4 invalidates immutable GPU packets when new semantic sky scores arrive."""
from vggt_slam.demo.gpu_scene import DenseGPUScene


class LiveGPUScene(DenseGPUScene):
    def __init__(self):super().__init__();self.sky_revision=None
    def update(self,run,step,phase,visible_nodes,frame_index,budget,hide_sky,threshold,color_mode,**kwargs):
        revision=(str(run.path),getattr(run,'sky_revision',0))
        if hide_sky and revision!=self.sky_revision:self.key=None
        self.sky_revision=revision
        return super().update(run,step,phase,visible_nodes,frame_index,budget,hide_sky,threshold,color_mode,**kwargs)
