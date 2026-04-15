"""
Run YOLO inference on a single image using a one-shot container
built from the training image (ultralytics is already installed there).
"""
import os
import uuid
import docker
from docker.errors import ContainerError, APIError

from config import TRAINING_IMAGE, HOST_BASE_DIR

_client = docker.from_env()

INFERENCE_RUNS_DIR = os.path.join(HOST_BASE_DIR, "inference_runs")
RESULTS_DIR        = os.path.join(HOST_BASE_DIR, "results")
SCRIPTS_DIR        = os.path.join(HOST_BASE_DIR, "scripts")


def list_trained_models(jobs: list[dict]) -> list[dict]:
    """Return jobs whose best.pt weights exist on disk."""
    out = []
    for job in jobs:
        job_id = job.get("job_id", "")
        weights = os.path.join(RESULTS_DIR, job_id, "weights", "best.pt")
        if os.path.isfile(weights):
            stat = os.stat(weights)
            out.append({
                "job_id":       job_id,
                "model":        job.get("model", ""),
                "epochs":       job.get("epochs", ""),
                "dataset":      job.get("dataset", ""),
                "status":       job.get("status", ""),
                "finished_at":  job.get("finished_at", ""),
                "size_mb":      round(stat.st_size / 1024 / 1024, 2),
            })
    out.sort(key=lambda m: m.get("finished_at", ""), reverse=True)
    return out


def run_inference(job_id: str, image_bytes: bytes, image_filename: str,
                  conf: float = 0.25) -> dict:
    """
    Save the uploaded image, launch a one-shot container that runs predict.py,
    and return the relative path to the annotated image + detection boxes.
    """
    weights_host = os.path.join(RESULTS_DIR, job_id, "weights", "best.pt")
    if not os.path.isfile(weights_host):
        raise FileNotFoundError(f"No trained weights for job {job_id}")

    req_id = uuid.uuid4().hex[:12]
    run_host_dir = os.path.join(INFERENCE_RUNS_DIR, req_id)
    os.makedirs(run_host_dir, exist_ok=True)

    ext = os.path.splitext(image_filename)[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png"):
        ext = ".jpg"
    input_name = f"input{ext}"
    input_host_path = os.path.join(run_host_dir, input_name)
    with open(input_host_path, "wb") as f:
        f.write(image_bytes)

    weights_dir_host = os.path.dirname(weights_host)

    volumes = {
        weights_dir_host: {"bind": "/weights",  "mode": "ro"},
        run_host_dir:     {"bind": "/io",       "mode": "rw"},
        SCRIPTS_DIR:      {"bind": "/scripts",  "mode": "ro"},
    }
    environment = {
        "WEIGHTS_PATH": "/weights/best.pt",
        "INPUT_PATH":   f"/io/{input_name}",
        "OUTPUT_DIR":   "/io",
        "CONF":         str(conf),
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
        import json
        with open(boxes_path) as bf:
            boxes = json.load(bf)

    return {
        "req_id":      req_id,
        "image_url":   f"/inference_runs/{req_id}/annotated.jpg",
        "boxes":       boxes.get("boxes", []),
        "count":       boxes.get("count", 0),
    }
