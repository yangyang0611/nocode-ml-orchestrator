"""
Generate a tiny synthetic YOLO dataset for demo purposes.
Creates 20 images (640x640) with random bounding boxes and packages as zip.
Output: processed/processed_dataset.zip
"""
import os
import random
import zipfile
import numpy as np
from PIL import Image, ImageDraw

OUTPUT_DIR  = "processed/demo_raw"
OUTPUT_ZIP  = "processed/processed_dataset.zip"
NUM_IMAGES  = 20
IMG_SIZE    = 640
NUM_CLASSES = 3

os.makedirs(OUTPUT_DIR, exist_ok=True)

for i in range(NUM_IMAGES):
    # Random background colour
    bg = tuple(random.randint(80, 200) for _ in range(3))
    img = Image.new("RGB", (IMG_SIZE, IMG_SIZE), color=bg)
    draw = ImageDraw.Draw(img)

    labels = []
    num_boxes = random.randint(1, 4)
    for _ in range(num_boxes):
        cls = random.randint(0, NUM_CLASSES - 1)
        cx  = random.uniform(0.15, 0.85)
        cy  = random.uniform(0.15, 0.85)
        w   = random.uniform(0.10, 0.35)
        h   = random.uniform(0.10, 0.35)

        # Draw rectangle on image
        x1 = int((cx - w / 2) * IMG_SIZE)
        y1 = int((cy - h / 2) * IMG_SIZE)
        x2 = int((cx + w / 2) * IMG_SIZE)
        y2 = int((cy + h / 2) * IMG_SIZE)
        colour = [(220, 50, 50), (50, 200, 50), (50, 50, 220)][cls]
        draw.rectangle([x1, y1, x2, y2], outline=colour, width=3)

        labels.append(f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

    img_path   = os.path.join(OUTPUT_DIR, f"img_{i:03d}.jpg")
    label_path = os.path.join(OUTPUT_DIR, f"img_{i:03d}.txt")

    img.save(img_path, quality=85)
    with open(label_path, "w") as f:
        f.write("\n".join(labels))

# data.yaml for YOLO training
yaml_content = f"""\
path: /workspace/dataset_extracted
train: .
val: .
nc: {NUM_CLASSES}
names: [cat, dog, bird]
"""
with open(os.path.join(OUTPUT_DIR, "data.yaml"), "w") as f:
    f.write(yaml_content)

# Package as zip
with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    for fname in os.listdir(OUTPUT_DIR):
        zf.write(os.path.join(OUTPUT_DIR, fname), fname)

size_kb = os.path.getsize(OUTPUT_ZIP) // 1024
print(f"✅ Demo dataset created: {OUTPUT_ZIP} ({size_kb} KB)")
print(f"   {NUM_IMAGES} images, {NUM_CLASSES} classes (cat/dog/bird)")
