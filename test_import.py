from torchvision.transforms.functional import rgb_to_grayscale # type: ignore
from basicsr.data.degradations import rgb_to_grayscale as basicsr_rgb_to_grayscale # type: ignore

print("Import successful")
print(rgb_to_grayscale)
print(basicsr_rgb_to_grayscale)