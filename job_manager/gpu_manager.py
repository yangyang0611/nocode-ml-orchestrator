import redis
try:
    import pynvml
    pynvml.nvmlInit()
    _NVML_AVAILABLE = True
except Exception:
    _NVML_AVAILABLE = False

from config import REDIS_URL, GPU_COUNT

_redis = redis.from_url(REDIS_URL, decode_responses=True)

# Redis key: gpu:{gpu_id}:status  → "free" | "occupied"
# Redis key: gpu:{gpu_id}:job_id  → job_id currently using this GPU


def _gpu_status_key(gpu_id: int) -> str:
    return f"gpu:{gpu_id}:status"


def _gpu_job_key(gpu_id: int) -> str:
    return f"gpu:{gpu_id}:job_id"


def get_gpu_count() -> int:
    if _NVML_AVAILABLE:
        return pynvml.nvmlDeviceGetCount()
    return GPU_COUNT


def get_gpu_status() -> list[dict]:
    """
    回傳每張 GPU 的即時狀態。
    """
    count = get_gpu_count()
    result = []

    for i in range(count):
        occupied = _redis.get(_gpu_status_key(i)) == "occupied"
        job_id = _redis.get(_gpu_job_key(i)) or ""

        if _NVML_AVAILABLE:
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)

            result.append({
                "gpu_id":       i,
                "name":         name,
                "status":       "occupied" if occupied else "free",
                "job_id":       job_id,
                "utilization":  util.gpu,          # %
                "memory_used":  mem.used // (1024 ** 2),   # MB
                "memory_total": mem.total // (1024 ** 2),  # MB
                "temperature":  temp,              # °C
            })
        else:
            # Mock mode
            result.append({
                "gpu_id":       i,
                "name":         "Mock GPU (no NVIDIA)",
                "status":       "occupied" if occupied else "free",
                "job_id":       job_id,
                "utilization":  0,
                "memory_used":  0,
                "memory_total": 8192,
                "temperature":  0,
            })

    return result


def allocate_gpu(job_id: str) -> int | None:
    """
    找到空閒 GPU，標記為 occupied，回傳 gpu_id。
    若無可用 GPU 回傳 None。
    使用 Redis WATCH 做簡單 optimistic locking 防止 race condition。
    """
    count = get_gpu_count()

    for i in range(count):
        status_key = _gpu_status_key(i)
        job_key = _gpu_job_key(i)

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
                pipe.execute()
                return i
            except redis.WatchError:
                # 另一個 process 搶先一步，試下一張
                continue

    return None


def release_gpu(gpu_id: int):
    """釋放 GPU，清除 job 關聯。"""
    _redis.set(_gpu_status_key(gpu_id), "free")
    _redis.delete(_gpu_job_key(gpu_id))


def is_gpu_free(gpu_id: int) -> bool:
    return _redis.get(_gpu_status_key(gpu_id)) != "occupied"
