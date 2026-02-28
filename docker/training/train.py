"""
Training script executed inside the Docker container.
Receives configuration via environment variables, reports status back to Redis.
"""
import os
import sys
import zipfile
import yaml
import redis
from ultralytics import YOLO

# ── Environment variables ────────────────────────────────────────────────────
JOB_ID      = os.environ["JOB_ID"]
MODEL       = os.environ.get("MODEL",       "yolov8n.pt")
EPOCHS      = int(os.environ.get("EPOCHS",  "10"))
BATCH_SIZE  = int(os.environ.get("BATCH",   "16"))
DATASET_ZIP = os.environ.get("DATASET_ZIP", "/workspace/dataset/processed_dataset.zip")
REDIS_URL   = os.environ.get("REDIS_URL",   "redis://localhost:6379")

# ── Redis ────────────────────────────────────────────────────────────────────
r = redis.from_url(REDIS_URL, decode_responses=True)

def log(msg: str):
    print(msg, flush=True)
    # Append to Redis log (keep last 4000 chars)
    existing = r.hget(f"job:{JOB_ID}", "logs") or ""
    r.hset(f"job:{JOB_ID}", "logs", (existing + msg + "\n")[-4000:])

def set_status(status: str):
    r.hset(f"job:{JOB_ID}", "status", status)

# ── Step 1: Extract dataset ──────────────────────────────────────────────────
EXTRACT_DIR = "/workspace/dataset_extracted"
os.makedirs(EXTRACT_DIR, exist_ok=True)

log(f"[JOB {JOB_ID[:8]}] Extracting dataset...")
try:
    with zipfile.ZipFile(DATASET_ZIP, "r") as zf:
        zf.extractall(EXTRACT_DIR)
    log("Dataset extracted.")
except Exception as e:
    log(f"ERROR extracting dataset: {e}")
    set_status("failed")
    sys.exit(1)

# ── Step 2: Prepare data.yaml ────────────────────────────────────────────────
yaml_path = os.path.join(EXTRACT_DIR, "data.yaml")

if not os.path.exists(yaml_path):
    # Auto-detect classes from label files
    class_ids = set()
    for root, _, files in os.walk(EXTRACT_DIR):
        for f in files:
            if f.endswith(".txt"):
                with open(os.path.join(root, f)) as lf:
                    for line in lf:
                        parts = line.strip().split()
                        if parts:
                            class_ids.add(int(parts[0]))

    nc = max(class_ids) + 1 if class_ids else 1
    names = [f"class{i}" for i in range(nc)]

    data_yaml = {
        "path":  EXTRACT_DIR,
        "train": ".",
        "val":   ".",
        "nc":    nc,
        "names": names,
    }
    with open(yaml_path, "w") as f:
        yaml.dump(data_yaml, f)
    log(f"Auto-generated data.yaml: {nc} class(es) detected.")
else:
    log("Found existing data.yaml.")

# ── Step 3: Train ────────────────────────────────────────────────────────────
log(f"Starting training: model={MODEL}, epochs={EPOCHS}, batch={BATCH_SIZE}")

try:
    model = YOLO(MODEL)
    model.train(
        data=yaml_path,
        epochs=EPOCHS,
        batch=BATCH_SIZE,
        project="/workspace/results",
        name=JOB_ID,
        exist_ok=True,
        verbose=True,
    )
    log("Training completed successfully.")
    # NOTE: status is managed by the scheduler via container exit code.
    # Exit 0 → scheduler marks "completed", non-zero → "failed".
except Exception as e:
    log(f"ERROR during training: {e}")
    sys.exit(1)
