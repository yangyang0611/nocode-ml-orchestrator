import redis
try:
    import pynvml
    pynvml.nvmlInit()
    _NVML_AVAILABLE = True
except Exception:
    _NVML_AVAILABLE = False

from config import REDIS_URL, GPU_COUNT

_redis = redis.from_url(REDIS_URL, decode_responses=True)

# Redis key layout per GPU:
#   gpu:{gpu_id}:status  → "free" | "occupied"
#   gpu:{gpu_id}:job_id  → job_id currently using this GPU
#   gpu:{gpu_id}:owner   → username that submitted that job


def _gpu_status_key(gpu_id: int) -> str:
    return f"gpu:{gpu_id}:status"


def _gpu_job_key(gpu_id: int) -> str:
    return f"gpu:{gpu_id}:job_id"


def _gpu_owner_key(gpu_id: int) -> str:
    return f"gpu:{gpu_id}:owner"


def get_gpu_count() -> int:
    if _NVML_AVAILABLE:
        return pynvml.nvmlDeviceGetCount()
    return GPU_COUNT


def get_gpu_status() -> list[dict]:
    """
    Returns per-GPU status with both physical metrics (from NVML) and
    logical bookkeeping (from Redis: who reserved it, which job).
    """
    count = get_gpu_count()
    result = []

    for i in range(count):
        occupied = _redis.get(_gpu_status_key(i)) == "occupied"
        job_id   = _redis.get(_gpu_job_key(i)) or ""
        owner    = _redis.get(_gpu_owner_key(i)) or ""

        if _NVML_AVAILABLE:
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem  = pynvml.nvmlDeviceGetMemoryInfo(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)

            result.append({
                "gpu_id":       i,
                "name":         name,
                "status":       "occupied" if occupied else "free",
                "job_id":       job_id,
                "owner_user":   owner,
                "utilization":  util.gpu,          # %
                "memory_used":  mem.used // (1024 ** 2),   # MB
                "memory_total": mem.total // (1024 ** 2),  # MB
                "memory_free":  (mem.total - mem.used) // (1024 ** 2),
                "temperature":  temp,              # °C
            })
        else:
            # Mock mode (no NVIDIA driver)
            result.append({
                "gpu_id":       i,
                "name":         "Mock GPU (no NVIDIA)",
                "status":       "occupied" if occupied else "free",
                "job_id":       job_id,
                "owner_user":   owner,
                "utilization":  0,
                "memory_used":  0,
                "memory_total": 8192,
                "memory_free":  8192,
                "temperature":  0,
            })

    return result


def allocate_gpu(job_id: str, owner_user: str = "") -> int | None:
    """
    Reserve the first free GPU for this job (and record its owner).
    Uses WATCH/MULTI for a simple optimistic lock.
    Returns gpu_id, or None if every GPU is busy.
    """
    count = get_gpu_count()

    for i in range(count):
        status_key = _gpu_status_key(i)
        job_key    = _gpu_job_key(i)
        owner_key  = _gpu_owner_key(i)

        with _redis.pipeline() as pipe:
            try:
                pipe.watch(status_key)
                current = pipe.get(status_key)
                if current == "occupied":
                    pipe.reset()
                    continue

                pipe.multi()
                pipe.set(status_key, "occupied")
                pipe.set(job_key, job_id)
                pipe.set(owner_key, owner_user or "")
                pipe.execute()
                return i
            except redis.WatchError:
                continue

    return None


def release_gpu(gpu_id: int):
    """Release GPU and clear job/owner links."""
    _redis.set(_gpu_status_key(gpu_id), "free")
    _redis.delete(_gpu_job_key(gpu_id))
    _redis.delete(_gpu_owner_key(gpu_id))


def is_gpu_free(gpu_id: int) -> bool:
    return _redis.get(_gpu_status_key(gpu_id)) != "occupied"
