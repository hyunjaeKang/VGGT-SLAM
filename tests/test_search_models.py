from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from vggt_slam.demo.search_models import detector_inference, worker_environment


def test_isolated_environments_and_unavailable_backend():
    assert '.venv-open-set' in str(worker_environment('/tmp', 'sam3'))
    assert '.venv-v4' in str(worker_environment('/tmp', 'yoloe'))
    assert '.venv-rfdetr' in str(worker_environment('/tmp', 'rfdetr'))


def test_queries_share_inference_but_never_mix_class_masks(tmp_path, monkeypatch):
    import vggt_slam.demo.semantic_models as adapters
    checkpoint=tmp_path/'logs/demo_models/v4/yolo26n-seg.pt'
    checkpoint.parent.mkdir(parents=True);checkpoint.write_bytes(b'local')
    calls=[]
    class Detector:
        model_hash='abc';size=640;device='cpu'
        def __init__(self,*args,**kwargs):pass
        def infer(self,rgb):
            calls.append(rgb)
            return [dict(class_name='car',mask=np.ones((4,5),bool),score=.9),
                    dict(class_name='person',mask=np.zeros((4,5),bool),score=.8)],0.
    monkeypatch.setattr(adapters,'PersistentDetector',Detector)
    infer, identity, _=detector_inference(tmp_path,'yolo26',[{'prompt':'car'},{'prompt':'person'}])
    image=Image.new('RGB',(5,4))
    assert infer(image,'car')[0].all()
    assert not infer(image,'person')[0].any()
    assert infer(image,'truck')[0].shape==(0,4,5)
    assert len(calls)==1
    infer(image.copy(),'car')
    assert len(calls)==2
    assert identity['backend']=='yolo26' and identity['classes']==['car','person']
