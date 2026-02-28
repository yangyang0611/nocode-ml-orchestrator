"""
Background scheduler: polls the priority queue every N seconds,
dispatches jobs to Docker containers, and monitors running jobs.
"""
import threading
from datetime import datetime, timezone, timedelta

from config import SCHEDULER_INTERVAL_SECONDS, JOB_TIMEOUT_MINUTES
from job_manager.queue_manager import (
    dequeue_next_job, update_job, get_job, list_jobs,
    PRIORITY_QUEUES, _redis,
)
from job_manager.gpu_manager import allocate_gpu, release_gpu
from job_manager.docker_manager import (
    start_training_container,
    get_container_status, get_container_exit_code, get_container_logs,
    stop_container, remove_container, cleanup_finished_containers,
)

_scheduler_thread: threading.Thread | None = None
_stop_event = threading.Event()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _release_job_resources(job: dict):
    """Stop container and release GPU for a job that is ending."""
    container_id = job.get("container_id", "")
    gpu_id_str   = job.get("gpu_id", "")

    if container_id:
        c_status = get_container_status(container_id)
        if c_status == "running":
            stop_container(container_id)   # stop + remove
        elif c_status == "exited":
            remove_container(container_id)

    if gpu_id_str != "":
        release_gpu(int(gpu_id_str))


# ── Main loop stages ──────────────────────────────────────────────────────────

def _check_running_jobs():
    """
    For every job currently in 'running' or 'cancelled' state:
    - cancelled + has container  → stop container, release GPU
    - running + timed out        → stop container, mark failed
    - running + container exited → read exit code, mark completed/failed
    - running + container gone   → mark failed
    """
    for job in list_jobs():
        job_id = job["job_id"]

        # Always re-fetch to get the latest status
        job = get_job(job_id)
        if not job:
            continue

        status       = job.get("status", "")
        container_id = job.get("container_id", "")
        gpu_id_str   = job.get("gpu_id", "")

        # ── cancelled while running (has a container) ────────────────────────
        if status == "cancelled" and container_id:
            print(f"[Scheduler] Cancelling running job {job_id[:8]}")
            _release_job_resources(job)
            update_job(job_id, {"finished_at": _now(), "container_id": "", "gpu_id": ""})
            continue

        if status != "running" or not container_id:
            continue

        # ── timeout check ────────────────────────────────────────────────────
        started_at = job.get("started_at", "")
        if started_at:
            try:
                elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(started_at)
                if elapsed > timedelta(minutes=JOB_TIMEOUT_MINUTES):
                    print(f"[Scheduler] Job {job_id[:8]} timed out after {JOB_TIMEOUT_MINUTES}m")
                    _release_job_resources(job)
                    update_job(job_id, {
                        "status":      "failed",
                        "finished_at": _now(),
                        "gpu_id":      "",
                        "container_id": "",
                        "logs":        (job.get("logs", "") +
                                        f"\nJob timed out after {JOB_TIMEOUT_MINUTES} minutes.")[-4000:],
                    })
                    continue
            except ValueError:
                pass

        # ── container status check ───────────────────────────────────────────
        c_status = get_container_status(container_id)

        if c_status == "exited":
            exit_code    = get_container_exit_code(container_id)
            logs         = get_container_logs(container_id)
            final_status = "completed" if exit_code == 0 else "failed"

            if gpu_id_str != "":
                release_gpu(int(gpu_id_str))
            remove_container(container_id)

            update_job(job_id, {
                "status":       final_status,
                "finished_at":  _now(),
                "gpu_id":       "",
                "container_id": "",
                "logs":         logs,
            })
            print(f"[Scheduler] Job {job_id[:8]} → {final_status} (exit_code={exit_code})")

        elif c_status == "not_found":
            if gpu_id_str != "":
                release_gpu(int(gpu_id_str))
            update_job(job_id, {
                "status":       "failed",
                "finished_at":  _now(),
                "gpu_id":       "",
                "container_id": "",
                "logs":         "Container disappeared unexpectedly.",
            })
            print(f"[Scheduler] Job {job_id[:8]} → failed (container vanished)")


def _try_dispatch_next_job():
    """
    Dequeue the highest-priority pending job and launch it on an available GPU.
    If no GPU is free, push the job back to the front of its queue.
    """
    job = dequeue_next_job()
    if not job:
        return

    job_id   = job["job_id"]
    priority = job.get("priority", "medium")

    gpu_id = allocate_gpu(job_id)

    if gpu_id is None:
        # No GPU free — put job back at the front of its queue
        _redis.lpush(PRIORITY_QUEUES[priority], job_id)
        return

    try:
        container_id = start_training_container(job_id, gpu_id, job)
        update_job(job_id, {
            "status":       "running",
            "gpu_id":       str(gpu_id),
            "container_id": container_id,
            "started_at":   _now(),
        })
        print(f"[Scheduler] Dispatched job {job_id[:8]} → GPU {gpu_id}, "
              f"container {container_id[:12]}")

    except Exception as e:
        print(f"[Scheduler] Failed to start container for {job_id[:8]}: {e}")
        release_gpu(gpu_id)
        update_job(job_id, {
            "status":       "failed",
            "finished_at":  _now(),
            "gpu_id":       "",
            "logs":         f"Failed to start container: {e}",
        })


# ── Scheduler thread ──────────────────────────────────────────────────────────

def _scheduler_loop():
    print("[Scheduler] Started.")
    while not _stop_event.is_set():
        try:
            _check_running_jobs()
            _try_dispatch_next_job()
            cleanup_finished_containers()
        except Exception as e:
            print(f"[Scheduler] Unexpected error: {e}")

        _stop_event.wait(SCHEDULER_INTERVAL_SECONDS)
    print("[Scheduler] Stopped.")


def start_scheduler():
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _stop_event.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        daemon=True,
        name="JobScheduler",
    )
    _scheduler_thread.start()


def stop_scheduler():
    _stop_event.set()
    if _scheduler_thread:
        _scheduler_thread.join(timeout=10)
