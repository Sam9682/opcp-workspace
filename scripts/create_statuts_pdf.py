#!/usr/bin/env python3
"""
Convert STATUTS JPEG images to PDF
"""
from PIL import Image

# Open the four JPEG images
img1 = Image.open('docs/STATUTS_PSMC_OPCP_(1).jpeg')
img2 = Image.open('docs/STATUTS_PSMC_OPCP_(2).jpeg')
img3 = Image.open('docs/STATUTS_PSMC_OPCP_(3).jpeg')
img4 = Image.open('docs/STATUTS_PSMC_OPCP_(4).jpeg')

# Convert to RGB if needed (PDF requires RGB)
images = [img1, img2, img3, img4]
rgb_images = []
for img in images:
    if img.mode != 'RGB':
        rgb_images.append(img.convert('RGB'))
    else:
        rgb_images.append(img)

# Save as PDF with all images
rgb_images[0].save('docs/STATUTS_PSMC_OPCP_FROM_IMAGES.pdf', 
          save_all=True, 
          append_images=rgb_images[1:],
          resolution=100.0,
          quality=95)

print("✓ PDF created successfully: docs/STATUTS_PSMC_OPCP_FROM_IMAGES.pdf")
