"""Persistent V4 model adapters; optional dependencies stay in a separate env."""
import hashlib
import os
import time
from pathlib import Path

import numpy as np
from PIL import Image


class PersistentDetector:
    def __init__(self, checkpoint, classes, device='auto', size=640):
        import torch
        from ultralytics import YOLO,YOLOE
        self.device=('mps' if torch.backends.mps.is_available() else 'cpu') if device=='auto' else device
        self.classes=classes;self.size=size;self.calls=0;self.loads=1
        self.path=Path(checkpoint).resolve();self.model_hash=hashlib.sha256(self.path.read_bytes()).hexdigest()
        start=time.monotonic()
        self.model=YOLOE(str(self.path)) if 'yoloe' in self.path.name else YOLO(str(self.path))
        if 'yoloe' in self.path.name:
            cwd=Path.cwd()
            try:
                os.chdir(self.path.parent);self.model.set_classes(classes)
            finally:os.chdir(cwd)
        names=set(self.model.names.values())
        if classes == ['*']:
            classes=list(self.model.names.values());self.classes=classes
        unknown=set(classes)-names
        if unknown:raise ValueError(f'Classes not in this model: {sorted(unknown)}; select YOLOE or SAM3')
        self.class_ids=[k for k,v in self.model.names.items() if v in classes]
        self.load_seconds=time.monotonic()-start
    def infer(self,rgb,track=False):
        import cv2,torch
        self.calls+=1;start=time.monotonic()
        if self.device=='cpu' and torch.get_num_threads()!=4:torch.set_num_threads(4)
        options=dict(source=rgb[:,:,::-1].copy(),imgsz=self.size,device=self.device,
                     classes=self.class_ids,conf=.20,verbose=False,retina_masks=True)
        if track:result=self.model.track(**options,persist=True,tracker='bytetrack.yaml')[0]
        else:result=self.model.predict(**options)[0]
        if self.device=='mps':torch.mps.synchronize()
        records=[]
        masks=result.masks.data.cpu().numpy() if result.masks is not None else []
        for i,box in enumerate(result.boxes):
            mask=masks[i]>.5 if i<len(masks) else None
            if mask is not None and mask.shape!=rgb.shape[:2]:mask=cv2.resize(mask.astype('uint8'),(rgb.shape[1],rgb.shape[0]),interpolation=cv2.INTER_NEAREST)>0
            records.append({'class_name':result.names[int(box.cls.item())],'score':float(box.conf.item()),
                            'bbox_native':box.xyxy[0].cpu().tolist(),'mask':mask,
                            'track_id_2d':int(box.id.item()) if box.id is not None else None})
        return records,time.monotonic()-start


class PersistentSurfaces:
    def __init__(self,checkpoint,device='cpu',size=384):
        import torch
        from transformers import SegformerForSemanticSegmentation
        self.device=device;self.size=size;self.loads=1;self.calls=0
        self.model=SegformerForSemanticSegmentation.from_pretrained(str(checkpoint),local_files_only=True).eval().to(device)
        self.names={str(v).lower():int(k) for k,v in self.model.config.id2label.items()}
        self.mean=np.array([.485,.456,.406],np.float32);self.std=np.array([.229,.224,.225],np.float32)
    def infer(self,rgb):
        import torch
        self.calls+=1;start=time.monotonic()
        if self.device=='cpu' and torch.get_num_threads()!=4:torch.set_num_threads(4)
        image=np.asarray(Image.fromarray(rgb).resize((self.size,self.size)),np.float32)/255
        tensor=torch.from_numpy(((image-self.mean)/self.std).transpose(2,0,1).copy())[None].to(self.device)
        with torch.inference_mode():
            logits=self.model(tensor).logits
            labels=torch.nn.functional.interpolate(logits,size=rgb.shape[:2],mode='bilinear',align_corners=False).argmax(1)[0].cpu().numpy()
        if self.device=='mps':torch.mps.synchronize()
        return {name:labels==self.names[name] for name in ('road','sky') if name in self.names},time.monotonic()-start


class PersistentSAM3:
    def __init__(self,classes):
        from huggingface_hub import hf_hub_download
        from sam3.model_builder import build_sam3_image_model
        from sam3.model.sam3_image_processor import Sam3Processor
        checkpoint=hf_hub_download('facebook/sam3','sam3.pt',local_files_only=True)
        self.processor=Sam3Processor(build_sam3_image_model(device='cpu',checkpoint_path=checkpoint,load_from_HF=False),device='cpu')
        self.model_hash=hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest()
        self.classes=classes;self.loads=1;self.calls=0;self.device='cpu';self.load_seconds=0
    def infer(self,rgb,track=False):
        import torch
        self.calls+=1;start=time.monotonic();records=[]
        with torch.inference_mode():
            state=self.processor.set_image(Image.fromarray(rgb))
            for name in self.classes:
                output=self.processor.set_text_prompt(state=state,prompt=name)
                for mask,score in zip(output['masks'].cpu().numpy(),output['scores'].cpu().numpy()):
                    mask=mask.squeeze().astype(bool);y,x=np.nonzero(mask)
                    records.append({'class_name':name,'score':float(score),'mask':mask,'track_id_2d':None,
                                    'bbox_native':[int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)] if len(x) else [0,0,0,0]})
        return records,time.monotonic()-start
