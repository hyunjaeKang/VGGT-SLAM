"""V5 opt-in crop geometry; default versions keep the upstream 518px loader."""
from pathlib import Path
import torch
from PIL import Image
from torchvision.transforms.functional import to_tensor


def load_images(paths, width=378):
    if not paths or width < 14 or width % 14:
        raise ValueError('Require images and a width divisible by 14')
    images=[]
    for path in paths:
        with Image.open(path) as source:
            if source.mode=='RGBA':
                source=Image.alpha_composite(Image.new('RGBA',source.size,(255,255,255,255)),source)
            source=source.convert('RGB')
            height=max(14,round(source.height*width/source.width/14)*14)
            image=to_tensor(source.resize((width,height),Image.Resampling.BICUBIC))
        if height>width:
            top=(height-width)//2;image=image[:,top:top+width,:]
        images.append(image)
    height=max(image.shape[1] for image in images)
    return torch.stack([torch.nn.functional.pad(image,(0,0,(height-image.shape[1])//2,(height-image.shape[1]+1)//2),value=1.) for image in images])


def load_local_weights(model):
    """No network metadata check; mmap avoids a second resident checkpoint copy."""
    path=Path(torch.hub.get_dir())/'checkpoints/model.pt'
    if not path.is_file():raise FileNotFoundError(f'VGGT checkpoint missing: {path}; prepare it using the existing installation')
    weights=torch.load(path,map_location='cpu',weights_only=True,mmap=True)
    model.load_state_dict(weights,assign=True)
