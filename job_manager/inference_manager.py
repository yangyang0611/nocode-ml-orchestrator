"""
Run YOLO inference on a single image using a one-shot container
built from the training image (ultralytics is already installed there).
"""
import json
import os
import shutil
import uuid
import docker
from docker.errors import ContainerError, APIError

from config import TRAINING_IMAGE, HOST_BASE_DIR

_client = docker.from_env()

INFERENCE_RUNS_DIR = os.path.join(HOST_BASE_DIR, "inference_runs")
RESULTS_DIR        = os.path.join(HOST_BASE_DIR, "results")
USER_MODELS_DIR    = os.path.join(HOST_BASE_DIR, "user_models")
SCRIPTS_DIR        = os.path.join(HOST_BASE_DIR, "scripts")
YOLOV9_CACHE_DIR   = os.path.join(HOST_BASE_DIR, "yolov9_cache")

os.makedirs(USER_MODELS_DIR, exist_ok=True)
os.makedirs(YOLOV9_CACHE_DIR, exist_ok=True)


# ── Model discovery ──────────────────────────────────────────────────────────

def list_trained_models(jobs: list[dict]) -> list[dict]:
    """Models produced by the training pipeline (results/<job_id>/weights/best.pt)."""
    out = []
    for job in jobs:
        job_id = job.get("job_id", "")
        weights = os.path.join(RESULTS_DIR, job_id, "weights", "best.pt")
        if os.path.isfile(weights):
            stat = os.stat(weights)
            out.append({
                "id":           job_id,
                "source":       "trained",
                "name":         job.get("model", ""),
                "model":        job.get("model", ""),
                "epochs":       job.get("epochs", ""),
                "dataset":      job.get("dataset", ""),
                "status":       job.get("status", ""),
                "finished_at":  job.get("finished_at", ""),
                "size_mb":      round(stat.st_size / 1024 / 1024, 2),
            })
    return out


def list_user_models() -> list[dict]:
    """User-uploaded .pt models under user_models/<id>/model.pt."""
    out = []
    if not os.path.isdir(USER_MODELS_DIR):
        return out
    for mid in os.listdir(USER_MODELS_DIR):
        mdir = os.path.join(USER_MODELS_DIR, mid)
        weights = os.path.join(mdir, "model.pt")
        if not os.path.isfile(weights):
            continue
        meta_path = os.path.join(mdir, "meta.json")
        meta = {}
        if os.path.isfile(meta_path):
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
            except Exception:
                meta = {}
        stat = os.stat(weights)
        out.append({
            "id":           mid,
            "source":       "uploaded",
            "name":         meta.get("name") or meta.get("filename") or mid,
            "filename":     meta.get("filename", ""),
            "uploaded_at":  meta.get("uploaded_at", ""),
            "size_mb":      round(stat.st_size / 1024 / 1024, 2),
        })
    return out


def list_all_models(jobs: list[dict]) -> list[dict]:
    models = list_trained_models(jobs) + list_user_models()
    models.sort(
        key=lambda m: m.get("finished_at") or m.get("uploaded_at") or "",
        reverse=True,
    )
    return models


# ── User model upload / delete ───────────────────────────────────────────────

def save_user_model(file_bytes: bytes, filename: str, display_name: str = "") -> dict:
    if not filename.lower().endswith(".pt"):
        raise ValueError("Only .pt files are accepted.")

    from datetime import datetime, timezone
    mid = uuid.uuid4().hex[:12]
    mdir = os.path.join(USER_MODELS_DIR, mid)
    os.makedirs(mdir, exist_ok=True)
    weights_path = os.path.join(mdir, "model.pt")
    with open(weights_path, "wb") as f:
        f.write(file_bytes)

    meta = {
        "id":          mid,
        "name":        display_name or os.path.splitext(os.path.basename(filename))[0],
        "filename":    filename,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(os.path.join(mdir, "meta.json"), "w") as f:
        json.dump(meta, f)

    stat = os.stat(weights_path)
    return {
        "id":          mid,
        "source":      "uploaded",
        "name":        meta["name"],
        "filename":    meta["filename"],
        "uploaded_at": meta["uploaded_at"],
        "size_mb":     round(stat.st_size / 1024 / 1024, 2),
    }


def delete_user_model(model_id: str) -> bool:
    mdir = os.path.join(USER_MODELS_DIR, model_id)
    # Guard against path traversal
    if os.path.abspath(mdir).startswith(os.path.abspath(USER_MODELS_DIR) + os.sep) \
            and os.path.isdir(mdir):
        shutil.rmtree(mdir, ignore_errors=True)
        return True
    return False


# ── Weights resolver ─────────────────────────────────────────────────────────

def _resolve_weights(model_id: str) -> str:
    """Return absolute path to a .pt file for the given model id, or raise."""
    trained = os.path.join(RESULTS_DIR, model_id, "weights", "best.pt")
    if os.path.isfile(trained):
        return trained
    uploaded = os.path.join(USER_MODELS_DIR, model_id, "model.pt")
    if os.path.isfile(uploaded):
        return uploaded
    raise FileNotFoundError(f"No model found with id {model_id}")


# ── Inference ────────────────────────────────────────────────────────────────

def run_inference(model_id: str, image_bytes: bytes, image_filename: str,
                  conf: float = 0.25) -> dict:
    weights_host = _resolve_weights(model_id)

    req_id = uuid.uuid4().hex[:12]
    run_host_dir = os.path.join(INFERENCE_RUNS_DIR, req_id)
    os.makedirs(run_host_dir, exist_ok=True)

    ext = os.path.splitext(image_filename)[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png"):
        ext = ".jpg"
    input_name = f"input{ext}"
    with open(os.path.join(run_host_dir, input_name), "wb") as f:
        f.write(image_bytes)

    # Mount the weights file's parent dir read-only
    weights_dir_host  = os.path.dirname(weights_host)
    weights_basename  = os.path.basename(weights_host)

    volumes = {
        weights_dir_host:  {"bind": "/weights",        "mode": "ro"},
        run_host_dir:      {"bind": "/io",             "mode": "rw"},
        SCRIPTS_DIR:       {"bind": "/scripts",        "mode": "ro"},
        YOLOV9_CACHE_DIR:  {"bind": "/opt/yolov9_cache","mode": "rw"},
    }
    environment = {
        "WEIGHTS_PATH": f"/weights/{weights_basename}",
        "INPUT_PATH":   f"/io/{input_name}",
        "OUTPUT_DIR":   "/io",
        "CONF":         str(conf),
        "YOLOV9_CACHE": "/opt/yolov9_cache",
    }

    try:
        logs = _client.containers.run(
            TRAINING_IMAGE,
            entrypoint=["python"],
            command=["/scripts/predict.py"],
            environment=environment,
            volumes=volumes,
            remove=True,
            stdout=True, stderr=True,
        )
        logs_text = logs.decode("utf-8", errors="replace") if isinstance(logs, bytes) else str(logs)
    except ContainerError as e:
        raise RuntimeError(
            f"Inference container failed (exit {e.exit_status}): "
            f"{e.stderr.decode('utf-8', errors='replace') if e.stderr else ''}"
        )
    except APIError as e:
        raise RuntimeError(f"Docker error: {e}")

    annotated_host = os.path.join(run_host_dir, "annotated.jpg")
    if not os.path.isfile(annotated_host):
        raise RuntimeError(f"Inference finished but annotated.jpg missing. Logs: {logs_text[-500:]}")

    boxes = {"boxes": [], "count": 0}
    boxes_path = os.path.join(run_host_dir, "boxes.json")
    if os.path.isfile(boxes_path):
        with open(boxes_path) as bf:
            boxes = json.load(bf)

    return {
        "req_id":      req_id,
        "image_url":   f"/inference_runs/{req_id}/annotated.jpg",
        "boxes":       boxes.get("boxes", []),
        "count":       boxes.get("count", 0),
    }
