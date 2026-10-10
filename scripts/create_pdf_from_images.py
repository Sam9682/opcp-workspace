#!/usr/bin/env python3
"""
Convert JPEG images to PDF
"""
import sys

try:
    from PIL import Image
    
    # Open the two JPEG images
    img1 = Image.open('docs/PROCES_VERBAL_ASSEMBLEE_CONSTITUTIVE_(1).jpeg')
    img2 = Image.open('docs/PROCES_VERBAL_ASSEMBLEE_CONSTITUTIVE_(2).jpeg')
    
    # Convert to RGB if needed (PDF requires RGB)
    if img1.mode != 'RGB':
        img1 = img1.convert('RGB')
    if img2.mode != 'RGB':
        img2 = img2.convert('RGB')
    
    # Save as PDF with both images
    img1.save('docs/PROCES_VERBAL_ASSEMBLEE_CONSTITUTIVE_FROM_IMAGES.pdf', 
              save_all=True, 
              append_images=[img2],
              resolution=100.0,
              quality=95)
    
    print("✓ PDF created successfully: docs/PROCES_VERBAL_ASSEMBLEE_CONSTITUTIVE_FROM_IMAGES.pdf")
    
except ImportError:
    print("Error: Pillow (PIL) is not installed.")
    print("Please install it with: sudo apt install python3-pil")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
