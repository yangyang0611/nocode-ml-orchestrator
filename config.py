import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# GPU settings
GPU_COUNT = 1          # RTX 4060 x1
GPU_MEMORY_LIMIT = "6g"  # 留 2GB 給系統，6GB 給 container

# Job settings
JOB_TIMEOUT_MINUTES = 120
SCHEDULER_INTERVAL_SECONDS = 5

# Docker training image
TRAINING_IMAGE = "ml-training:latest"

# File paths
PROCESSED_FOLDER = "processed"

# Host base directory for Docker volume mounts.
# When Flask runs inside a container, this must be set to the HOST's
# absolute repo path so sibling training containers can mount volumes correctly.
# When running locally, defaults to the repo root automatically.
HOST_BASE_DIR = os.getenv(
    "HOST_BASE_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__)))
)
