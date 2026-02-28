# NoCode ML Training Orchestrator

A no-code ML training orchestration platform built on Flask. Upload and preprocess YOLO datasets, submit training jobs via priority queue, and monitor GPU resources and job status in real time — all without writing code.

---

## Features

### Image Preprocessing
Upload a folder of images with YOLO-format labels and apply a configurable pipeline of preprocessing steps.

| Operation | Options |
|-----------|---------|
| Resize | Custom width × height |
| Rotate | 90 / 180 / 270 degrees |
| Mirror | Horizontal flip |
| Add Noise | Gaussian, Brightness, Saturation |

Steps can be reordered via drag-and-drop. The processed dataset is downloaded as a zip file.

### Training Job Submission
Select a dataset, choose a YOLOv8 model (n / s / m), configure epochs and batch size, and assign a priority. Jobs enter a Redis-backed priority queue and are dispatched as GPU resources become available.

### Real-time Dashboard
Polling-based dashboard (3-second refresh) showing:
- GPU utilization, memory usage, and temperature
- Per-priority queue depths (High / Medium / Low)
- Job status table with live log viewer and cancel controls

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Web UI (Flask + JS)                   │
│  /           Image Preprocessing  (index.html)          │
│  /train      Training Job Submit  (train.html)          │
│  /dashboard  Job Dashboard        (dashboard.html)      │
└────────────────────┬────────────────────────────────────┘
                     │ REST API
┌────────────────────▼────────────────────────────────────┐
│                  Flask API Server (app.py)               │
│  /api/jobs        POST/GET/DELETE — job management      │
│  /api/resources   GET — GPU utilization & memory        │
│  /api/queue       GET — per-priority queue depth        │
└──────┬───────────────────────────┬──────────────────────┘
       │                           │
┌──────▼──────┐         ┌──────────▼──────────────────────┐
│   Redis     │         │   Job Scheduler (daemon thread)  │
│  · Priority │◄────────│   · Polls queue every 5s        │
│    Queues   │         │   · Allocates GPU per job        │
│  · Job      │         │   · Monitors container status   │
│    Metadata │         └──────────┬──────────────────────┘
└─────────────┘                    │ docker-py SDK
                         ┌──────────▼──────────────────────┐
                         │   Docker Engine                  │
                         │   · YOLOv8 training containers  │
                         │   · GPU device assignment       │
                         │   · Memory & shm isolation      │
                         └─────────────────────────────────┘
```

---

## Prerequisites

- Python 3.10+
- Docker
- NVIDIA GPU + Driver (CPU fallback supported)
- [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) for GPU access inside containers

```bash
# Install nvidia-container-toolkit (Ubuntu/Debian)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker
```

---

## Quick Start

### Option A — Local

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start Redis
docker run -d -p 6379:6379 --name redis --restart unless-stopped redis:alpine

# 3. Build training image
docker build -t ml-training:latest ./docker/training/

# 4. Start Flask
python app.py
```

### Option B — Docker Compose

```bash
# Build training image first (required)
docker build -t ml-training:latest ./docker/training/

# Start full stack (Redis + Flask)
HOST_BASE_DIR=$(pwd) docker compose -f docker/docker-compose.yml up --build
```

Open in browser:

| URL | Page |
|-----|------|
| `http://localhost:5000` | Image Preprocessing |
| `http://localhost:5000/train` | Submit Training Job |
| `http://localhost:5000/dashboard` | Monitor Jobs & GPU |

---

## Project Structure

```
preprocessing_gui/
├── app.py                      # Flask app — preprocessing + job API + scheduler init
├── config.py                   # Centralized settings
├── requirements.txt
│
├── job_manager/
│   ├── queue_manager.py        # Redis priority queue (submit / dequeue / cancel)
│   ├── gpu_manager.py          # GPU allocation with optimistic locking
│   ├── docker_manager.py       # Container lifecycle management
│   └── scheduler.py            # Background thread — dispatch & monitor jobs
│
├── docker/
│   ├── training/
│   │   ├── Dockerfile          # YOLOv8 training image (ultralytics base)
│   │   └── train.py            # Training script run inside container
│   └── docker-compose.yml      # Full stack: Redis + Flask
│
├── templates/
│   ├── index.html              # Preprocessing UI
│   ├── train.html              # Job submission form
│   └── dashboard.html          # Real-time monitoring dashboard
│
├── static/
│   ├── index.js / index.css    # Preprocessing page scripts
│   ├── train.js                # Job submission logic
│   └── dashboard.js            # Dashboard polling & rendering
│
└── scripts/
    └── make_demo_dataset.py    # Generate synthetic YOLO dataset for demo
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/jobs` | Submit a training job |
| `GET` | `/api/jobs` | List all jobs |
| `GET` | `/api/jobs/<id>` | Get job status |
| `DELETE` | `/api/jobs/<id>` | Cancel a job |
| `GET` | `/api/jobs/<id>/logs` | Get container logs |
| `GET` | `/api/resources` | GPU utilization & memory |
| `GET` | `/api/queue` | Per-priority queue depths |

**Submit job example:**
```bash
curl -X POST http://localhost:5000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"model":"yolov8n.pt","epochs":10,"dataset":"processed_dataset.zip","priority":"high"}'
```

---

## Tech Stack

| Component | Choice |
|-----------|--------|
| Web Framework | Flask 3 |
| Task Queue | Redis + rq |
| Container Management | docker-py SDK |
| GPU Monitoring | nvidia-ml-py (pynvml API) |
| ML Training | YOLOv8 — Ultralytics |
| Frontend | Bootstrap 4 + Vanilla JS |
