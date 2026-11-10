import sys
import types
import numpy as np
import pytest
from PIL import Image
from vggt_slam.demo.rfdetr_search import rfdetr_inference


def test_coco_ids_mask_alignment_and_shared_image_inference(tmp_path, monkeypatch):
    calls=[]
    class Model:
        def __init__(self,**kwargs):calls.append(kwargs)
        def predict(self,image,threshold):
            calls.append(threshold)
            return types.SimpleNamespace(class_id=np.array([3,1]),confidence=np.array([.9,.8]),
                mask=np.array([np.ones((4,5),bool),np.zeros((4,5),bool)]))
    monkeypatch.setitem(sys.modules,'rfdetr',types.SimpleNamespace(RFDETRSegNano=Model))
    monkeypatch.setitem(sys.modules,'rfdetr.assets.coco_classes',types.SimpleNamespace(COCO_CLASSES={1:'person',3:'car'}))
    monkeypatch.setattr('vggt_slam.demo.rfdetr_search.version',lambda _: 'test')
    checkpoint=tmp_path/'logs/demo_models/rfdetr/rf-detr-seg-nano.pt'
    checkpoint.parent.mkdir(parents=True);checkpoint.write_bytes(b'weights')
    infer, identity, _=rfdetr_inference(tmp_path,[{'prompt':'car'},{'prompt':'person'}])
    image=Image.new('RGB',(5,4))
    assert infer(image,'car')[0].all()
    assert not infer(image,'person')[0].any()
    assert len(calls)==2
    assert identity['backend']=='rfdetr'
    with pytest.raises(ValueError,match='SAM3'):
        rfdetr_inference(tmp_path,[{'prompt':'printer'}])
    assert len(calls)==2  # unsupported query fails before model load
