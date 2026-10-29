"""Reusable customer avatars and shop-owner portraits."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps


def read_photo(base,path):
    if not path:return None
    location=Path(path)
    if not location.is_absolute():location=Path(base)/location
    try:
        if not location.resolve().is_relative_to(Path(base).resolve()):return None
        with Image.open(location) as image:return ImageOps.exif_transpose(image).convert('RGB')
    except (OSError,ValueError):return None


def avatar(base,path,size=96,active=False):
    photo=read_photo(base,path)
    result=Image.new('RGBA',(size,size),(0,0,0,0))
    draw=ImageDraw.Draw(result)
    draw.ellipse((1,1,size-2,size-2),fill='#F1F3F5',outline='#243E55' if active else '#DAE0E6',width=max(2,size//32))
    inset=max(4,size//16);inner=size-inset*2
    if photo is not None:
        cropped=ImageOps.fit(photo,(inner,inner),method=Image.Resampling.LANCZOS,centering=(.5,.35))
        mask=Image.new('L',(inner,inner));ImageDraw.Draw(mask).ellipse((0,0,inner-1,inner-1),fill=255)
        result.paste(cropped,(inset,inset),mask)
    else:
        draw.ellipse((size*.36,size*.24,size*.64,size*.52),fill='#526C80')
        draw.ellipse((size*.23,size*.57,size*.77,size*.9),fill='#526C80')
    return result


def owner_portrait(base,path,size=(280,340)):
    photo=read_photo(base,path)
    if photo is not None:
        # Keep the whole owner photo visible, including the head.
        result=Image.new('RGB',size,'#E9EEF3')
        photo=ImageOps.contain(photo,size,method=Image.Resampling.LANCZOS)
        result.paste(photo,((size[0]-photo.width)//2,(size[1]-photo.height)//2))
        return result
    result=Image.new('RGB',size,'#E9EEF3');draw=ImageDraw.Draw(result);w,h=size
    draw.ellipse((w*.33,h*.2,w*.67,h*.48),fill='#AAB8C5')
    draw.rounded_rectangle((w*.18,h*.55,w*.82,h*.86),radius=35,fill='#AAB8C5')
    return result
