import os
import docker
from docker.errors import NotFound, APIError

from config import GPU_MEMORY_LIMIT, TRAINING_IMAGE, PROCESSED_FOLDER, REDIS_URL

_client = docker.from_env()

# Containers reach Redis via host.docker.internal (Docker Desktop / WSL2)
_CONTAINER_REDIS_URL = REDIS_URL.replace("localhost", "host.docker.internal") \
                                .replace("127.0.0.1", "host.docker.internal")

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def start_training_container(job_id: str, gpu_id: int, job: dict) -> str:
    """
    Launch a training container for the given job.
    Returns container_id.
    """
    dataset_host_path = os.path.join(_BASE_DIR, PROCESSED_FOLDER)
    results_host_path = os.path.join(_BASE_DIR, "results")
    os.makedirs(results_host_path, exist_ok=True)

    environment = {
        "JOB_ID":      job_id,
        "MODEL":       job.get("model",      "yolov8n.pt"),
        "EPOCHS":      job.get("epochs",     "10"),
        "BATCH":       job.get("batch_size", "16"),
        "DATASET_ZIP": f"/workspace/dataset/{job.get('dataset', 'processed_dataset.zip')}",
        "REDIS_URL":   _CONTAINER_REDIS_URL,
    }

    volumes = {
        dataset_host_path: {"bind": "/workspace/dataset", "mode": "ro"},
        results_host_path: {"bind": "/workspace/results",  "mode": "rw"},
    }

    device_requests = [
        docker.types.DeviceRequest(
            device_ids=[str(gpu_id)],
            capabilities=[["gpu"]]
        )
    ]

    container = _client.containers.run(
        TRAINING_IMAGE,
        name=f"training-{job_id[:8]}",
        environment=environment,
        volumes=volumes,
        device_requests=device_requests,
        mem_limit=GPU_MEMORY_LIMIT,   # RAM limit for resource isolation
        extra_hosts={"host.docker.internal": "host-gateway"},  # Linux host resolution
        detach=True,
        remove=False,                 # Keep container so logs are retrievable
    )

    return container.id


def get_container_status(container_id: str) -> str:
    """
    Returns Docker container status string:
    'running' | 'exited' | 'created' | 'not_found'
    """
    try:
        container = _client.containers.get(container_id)
        container.reload()
        return container.status
    except NotFound:
        return "not_found"


def get_container_exit_code(container_id: str) -> int | None:
    try:
        container = _client.containers.get(container_id)
        container.reload()
        return container.attrs["State"]["ExitCode"]
    except NotFound:
        return None


def get_container_logs(container_id: str, tail: int = 100) -> str:
    try:
        container = _client.containers.get(container_id)
        return container.logs(tail=tail).decode("utf-8", errors="replace")
    except NotFound:
        return "Container not found"


def stop_container(container_id: str):
    """Gracefully stop and remove a container."""
    try:
        container = _client.containers.get(container_id)
        container.stop(timeout=10)
        container.remove()
    except NotFound:
        pass
    except APIError as e:
        print(f"[docker_manager] stop error: {e}")


def remove_container(container_id: str):
    """Force remove a container (e.g. after exited)."""
    try:
        container = _client.containers.get(container_id)
        container.remove(force=True)
    except NotFound:
        pass


def cleanup_finished_containers():
    """Remove all exited training containers to free resources."""
    containers = _client.containers.list(
        all=True,
        filters={"name": "training-", "status": "exited"}
    )
    for c in containers:
        try:
            c.remove()
        except APIError:
            pass
