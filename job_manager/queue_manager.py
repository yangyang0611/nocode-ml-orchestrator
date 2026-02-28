import uuid
from datetime import datetime, timezone
import redis
from config import REDIS_URL

_redis = redis.from_url(REDIS_URL, decode_responses=True)

# Priority queues：數字越小優先級越高
PRIORITY_QUEUES = {
    "high":   "queue:high",
    "medium": "queue:medium",
    "low":    "queue:low",
}
PRIORITY_ORDER = ["high", "medium", "low"]

JOB_KEY = "job:{job_id}"


def _job_key(job_id: str) -> str:
    return f"job:{job_id}"


def submit_job(job_config: dict, priority: str = "medium") -> str:
    """
    把 training job 放進 priority queue。
    回傳 job_id。
    """
    if priority not in PRIORITY_QUEUES:
        priority = "medium"

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    metadata = {
        "job_id":       job_id,
        "status":       "pending",
        "priority":     priority,
        "submitted_at": now,
        "started_at":   "",
        "finished_at":  "",
        "gpu_id":       "",
        "container_id": "",
        "logs":         "",
        **job_config,   # model, epochs, batch_size, dataset, user ...
    }

    # 儲存 job metadata
    _redis.hset(_job_key(job_id), mapping=metadata)

    # 推入對應 priority queue（FIFO：rpush + blpop）
    _redis.rpush(PRIORITY_QUEUES[priority], job_id)

    return job_id


def dequeue_next_job() -> dict | None:
    """
    從最高 priority queue 取出一個 pending job。
    若所有 queue 都空則回傳 None。
    """
    for priority in PRIORITY_ORDER:
        job_id = _redis.lpop(PRIORITY_QUEUES[priority])
        if job_id:
            job = get_job(job_id)
            # 確保還是 pending（未被 cancel）
            if job and job.get("status") == "pending":
                return job
    return None


def get_job(job_id: str) -> dict | None:
    data = _redis.hgetall(_job_key(job_id))
    return data if data else None


def list_jobs() -> list[dict]:
    """回傳所有 job，依提交時間降冪排列。"""
    keys = _redis.keys("job:*")
    jobs = []
    for key in keys:
        data = _redis.hgetall(key)
        if data:
            jobs.append(data)
    jobs.sort(key=lambda j: j.get("submitted_at", ""), reverse=True)
    return jobs


def update_job(job_id: str, fields: dict):
    """更新 job 的部分欄位。"""
    _redis.hset(_job_key(job_id), mapping=fields)


def cancel_job(job_id: str) -> bool:
    """
    取消 job。
    - pending：直接標記 cancelled（scheduler 取出時會跳過）
    - running：需由 scheduler 停止 container（這裡只標記）
    """
    job = get_job(job_id)
    if not job:
        return False
    if job["status"] in ("completed", "failed", "cancelled"):
        return False
    update_job(job_id, {"status": "cancelled"})
    return True


def get_queue_status() -> dict:
    """回傳各 priority queue 的等待數量。"""
    return {
        priority: _redis.llen(queue_key)
        for priority, queue_key in PRIORITY_QUEUES.items()
    }
