import os
import cv2
import numpy as np
from gfpgan import GFPGANer
from PIL import Image

def enhance_image(image_path):
    model_path = os.path.join('GFPGAN', 'experiments', 'pretrained_models', 'GFPGANv1.3.pth')
    gfpganer = GFPGANer(
        model_path=model_path,
        upscale=2,
        arch='clean',
        channel_multiplier=2,
        bg_upsampler=None
    )

    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    _, _, restored_img = gfpganer.enhance(img, has_aligned=False, only_center_face=False)
    restored_img = cv2.cvtColor(restored_img, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(restored_img)
    return pil_image
