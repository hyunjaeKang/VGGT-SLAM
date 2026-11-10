"""Local RF-DETR-Seg Nano search adapter, isolated from SLAM dependencies."""
import hashlib
from importlib.metadata import version
from pathlib import Path
import numpy as np


def rfdetr_inference(root, queries):
    from rfdetr import RFDETRSegNano
    from rfdetr.assets.coco_classes import COCO_CLASSES
    classes = [q['prompt'] for q in queries]
    names = dict(COCO_CLASSES) if isinstance(COCO_CLASSES, dict) else dict(enumerate(COCO_CLASSES))
    supported = {str(name).casefold() for name in names.values()} - {'n/a', '__background__'}
    if classes == ['*']:
        classes=sorted(supported)
    unknown = set(classes) - supported
    if unknown:
        raise ValueError(f"RF-DETR-Seg가 지원하지 않는 클래스: {', '.join(sorted(unknown))}. SAM3 또는 YOLOE를 사용하세요.")
    checkpoint = Path(root)/'logs/demo_models/rfdetr/rf-detr-seg-nano.pt'
    if not checkpoint.is_file():
        raise ValueError('RF-DETR 가중치가 없습니다. docs/RFDETR_SEARCH.md의 준비 명령을 실행하세요.')
    model = RFDETRSegNano(pretrain_weights=str(checkpoint), device='cpu')
    cached_image, detections = None, None

    def active_classes(image):
        nonlocal cached_image, detections
        if image is not cached_image:
            detections=model.predict(image,threshold=.3);cached_image=image
        return {str(names.get(int(i), '')).casefold() for i in detections.class_id}

    def infer(image, prompt):
        nonlocal cached_image, detections
        if image is not cached_image:
            detections = model.predict(image, threshold=.3)
            cached_image = image
        ids = np.asarray(detections.class_id)
        selected = np.asarray([str(names.get(int(i), '')).casefold() == prompt for i in ids], dtype=bool)
        if not selected.any():
            return np.empty((0, image.height, image.width), bool), np.empty(0)
        if detections.mask is None:
            raise ValueError('RF-DETR-Seg returned detections without masks')
        masks = np.asarray(detections.mask, bool)[selected]
        if masks.shape[1:] != (image.height, image.width):
            raise ValueError(f'RF-DETR mask dimensions do not match RGB: {masks.shape}')
        return masks, np.asarray(detections.confidence)[selected]

    infer.active_classes=active_classes
    identity = {'backend':'rfdetr','variant':'RFDETRSegNano','version':version('rfdetr'),
                'sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                'confidence':.3,'classes':classes,'device':'cpu'}
    return infer, identity, 'RF-DETR-Seg Nano'
