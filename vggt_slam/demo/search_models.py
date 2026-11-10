"""V5 search choices and local segmentation adapters (no implicit downloads)."""
from pathlib import Path
import numpy as np

MODEL_OPTIONS = {'SAM3': 'sam3', 'RF-DETR': 'rfdetr',
                 'YOLOE': 'yoloe', 'YOLO26': 'yolo26', 'YOLO11': 'yolo11'}
MODEL_HELP = {
 'sam3': '**SAM3 · 자유 텍스트 분할**\ncar, tree, printer 같은 명칭으로 객체 마스크를 찾습니다. CPU에서는 느릴 수 있습니다.',
 'rfdetr': '**RF-DETR-Seg · 학습 클래스 검출/분할**\nSeg Nano로 자동차·사람 등 COCO 학습 클래스의 박스와 마스크를 찾습니다. car, person, truck 등을 입력하세요. printer, road는 지원하지 않으며 SAM3/YOLOE로 검색하세요. CPU 처리이며 속도는 영상에 따라 달라집니다.',
 'yoloe': '**YOLOE · 자유 텍스트 검출/분할**\n검색할 클래스 이름을 텍스트로 지정합니다. car, tree, printer 등으로 검색할 수 있지만 모든 대상을 찾는다는 보장은 없습니다.',
 'yolo26': '**YOLO26-seg · 학습 클래스 검출/분할**\ncar, person, truck 등 COCO 클래스만 지원합니다. printer, road는 지원하지 않습니다.',
 'yolo11': '**YOLO11-seg · 학습 클래스 검출/분할**\ncar, person, truck 등 COCO 클래스만 지원합니다. YOLO26과 결과·속도를 비교할 수 있습니다.',
}
COMMON_HELP = '\n\nRGB: Mask / Bounding Box · 3D: 깊이가 유효한 영역의 Mask / Box · BEV: 투영된 Mask / Box. Search scope는 검사할 프레임 범위입니다. 전체는 저장된 고유 지도 프레임이며 원본 영상의 모든 프레임을 뜻하지 않습니다.'


def worker_environment(root, backend):
    if backend not in MODEL_HELP:
        raise ValueError('Unknown search model')
    return Path(root) / ({'sam3':'.venv-open-set','rfdetr':'.venv-rfdetr'}.get(backend,'.venv-v4')) / 'bin/python'


def detector_inference(root, backend, queries):
    if backend == 'rfdetr':
        from vggt_slam.demo.rfdetr_search import rfdetr_inference
        return rfdetr_inference(root, queries)
    from vggt_slam.demo.semantic_models import PersistentDetector
    filename = {'yolo26': 'yolo26n-seg.pt', 'yolo11': 'yolo11n-seg.pt', 'yoloe': 'yoloe-26s-seg.pt'}[backend]
    checkpoint = Path(root)/'logs/demo_models/v4'/filename
    if not checkpoint.is_file():
        raise ValueError(f'로컬 모델 파일이 없습니다: {checkpoint}')
    classes = [q['prompt'] for q in queries]
    detector = PersistentDetector(checkpoint, classes, device='cpu')
    if classes == ['*']:
        classes=detector.classes
    cached_image, records = None, []

    def active_classes(image):
        nonlocal cached_image, records
        if image is not cached_image:
            records, _ = detector.infer(np.asarray(image.convert('RGB')))
            cached_image = image
        return {d['class_name'] for d in records if d['mask'] is not None}

    def infer(image, prompt):
        nonlocal cached_image, records
        if image is not cached_image:
            records, _ = detector.infer(np.asarray(image.convert('RGB')))
            cached_image = image
        selected = [d for d in records if d['class_name'] == prompt and d['mask'] is not None]
        masks = np.stack([d['mask'] for d in selected]) if selected else np.empty((0, image.height, image.width), bool)
        return masks, np.asarray([d['score'] for d in selected])

    infer.active_classes=active_classes
    return infer, {'backend': backend, 'sha256': detector.model_hash, 'classes': classes,
                   'confidence': .2, 'image_size': detector.size, 'device': detector.device}, filename
