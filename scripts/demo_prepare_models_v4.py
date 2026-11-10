from pathlib import Path
import urllib.request,json,hashlib
from huggingface_hub import snapshot_download
root=Path('logs/demo_models/v4');root.mkdir(parents=True,exist_ok=True)
for name in ['yolo11n-seg.pt','yolo26n-seg.pt']:
 p=root/name
 if not p.exists():urllib.request.urlretrieve('https://github.com/ultralytics/assets/releases/download/v8.4.0/'+name,p)
 print(name,p.stat().st_size,flush=True)
snapshot_download('nvidia/segformer-b0-finetuned-cityscapes-1024-1024',local_dir=root/'segformer-b0-cityscapes',allow_patterns=['config.json','preprocessor_config.json','model.safetensors','pytorch_model.bin'])
record={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.pt')}
(root/'model_hashes.json').write_text(json.dumps(record,indent=2)+'\n');print(record)
