"""
One-shot YOLO inference. Run inside the ml-training container.
Env vars:
  WEIGHTS_PATH  - path to best.pt (mounted read-only)
  INPUT_PATH    - path to input image
  OUTPUT_DIR    - directory to write annotated image + boxes.json
"""
import json
import os
import shutil
import sys
from pathlib import Path

from ultralytics import YOLO

WEIGHTS = os.environ["WEIGHTS_PATH"]
INPUT   = os.environ["INPUT_PATH"]
OUT_DIR = os.environ["OUTPUT_DIR"]
CONF    = float(os.environ.get("CONF", "0.25"))

os.makedirs(OUT_DIR, exist_ok=True)

model = YOLO(WEIGHTS)
results = model.predict(
    source=INPUT,
    conf=CONF,
    save=True,
    project=OUT_DIR,
    name="run",
    exist_ok=True,
    verbose=False,
)

run_dir = Path(OUT_DIR) / "run"
saved = None
for p in run_dir.iterdir():
    if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
        saved = p
        break

if saved is None:
    print("ERROR: no annotated image produced", file=sys.stderr)
    sys.exit(1)

final_img = Path(OUT_DIR) / "annotated.jpg"
shutil.copy(str(saved), str(final_img))

boxes_out = []
names = getattr(model, "names", {})
for r in results:
    if r.boxes is None:
        continue
    xyxy = r.boxes.xyxy.cpu().tolist()
    conf = r.boxes.conf.cpu().tolist()
    cls  = r.boxes.cls.cpu().tolist()
    for (x1, y1, x2, y2), c, k in zip(xyxy, conf, cls):
        k = int(k)
        boxes_out.append({
            "x1": round(x1, 2), "y1": round(y1, 2),
            "x2": round(x2, 2), "y2": round(y2, 2),
            "conf": round(float(c), 4),
            "cls": k,
            "label": names.get(k, str(k)) if isinstance(names, dict) else str(k),
        })

with open(Path(OUT_DIR) / "boxes.json", "w") as f:
    json.dump({"boxes": boxes_out, "count": len(boxes_out)}, f)

print(f"Wrote {final_img} with {len(boxes_out)} detections")
