"""
One-shot YOLO inference. Run inside the ml-training container.

Env vars:
  WEIGHTS_PATH  - path to .pt (mounted read-only)
  INPUT_PATH    - path to input image
  OUTPUT_DIR    - directory to write annotated image + boxes.json
  CONF          - confidence threshold (default 0.25)
  YOLOV9_CACHE  - directory to clone WongKinYiu/yolov9 into (default /opt/yolov9_cache)
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

WEIGHTS = os.environ["WEIGHTS_PATH"]
INPUT   = os.environ["INPUT_PATH"]
OUT_DIR = os.environ["OUTPUT_DIR"]
CONF    = float(os.environ.get("CONF", "0.25"))
YOLOV9_CACHE = os.environ.get("YOLOV9_CACHE", "/opt/yolov9_cache")

os.makedirs(OUT_DIR, exist_ok=True)


def write_boxes(boxes_out):
    with open(Path(OUT_DIR) / "boxes.json", "w") as f:
        json.dump({"boxes": boxes_out, "count": len(boxes_out)}, f)


# ── Path A: ultralytics ──────────────────────────────────────────────────────
def try_ultralytics() -> bool:
    from ultralytics import YOLO
    model = YOLO(WEIGHTS)
    results = model.predict(
        source=INPUT, conf=CONF,
        save=True, project=OUT_DIR, name="run", exist_ok=True, verbose=False,
    )

    run_dir = Path(OUT_DIR) / "run"
    saved = next((p for p in run_dir.iterdir()
                  if p.suffix.lower() in (".jpg", ".jpeg", ".png")), None)
    if saved is None:
        raise RuntimeError("ultralytics produced no annotated image")
    shutil.copy(str(saved), str(Path(OUT_DIR) / "annotated.jpg"))

    names = getattr(model, "names", {})
    boxes_out = []
    for r in results:
        if r.boxes is None:
            continue
        xyxy = r.boxes.xyxy.cpu().tolist()
        conf = r.boxes.conf.cpu().tolist()
        cls  = r.boxes.cls.cpu().tolist()
        for (x1, y1, x2, y2), c, k in zip(xyxy, conf, cls):
            k = int(k)
            boxes_out.append({
                "x1": round(x1, 2), "y1": round(y1, 2),
                "x2": round(x2, 2), "y2": round(y2, 2),
                "conf": round(float(c), 4),
                "cls":  k,
                "label": names.get(k, str(k)) if isinstance(names, dict) else str(k),
            })
    write_boxes(boxes_out)
    print(f"[ultralytics] Wrote {len(boxes_out)} detections")
    return True


# ── Path B: WongKinYiu/yolov9 fallback ───────────────────────────────────────
def ensure_wongkinyiu_repo() -> str:
    """Clone WongKinYiu/yolov9 into cache if missing. Return repo path."""
    repo = Path(YOLOV9_CACHE) / "yolov9"
    if not (repo / "detect.py").is_file():
        repo.parent.mkdir(parents=True, exist_ok=True)
        print(f"[fallback] cloning WongKinYiu/yolov9 into {repo}...", flush=True)
        subprocess.run(
            ["git", "clone", "--depth", "1",
             "https://github.com/WongKinYiu/yolov9.git", str(repo)],
            check=True,
        )
    return str(repo)


def ensure_deps():
    """WongKinYiu/yolov9 detect.py deps not always present; install on demand."""
    for mod, pkg in [
        ("seaborn", "seaborn"),
        ("thop",    "thop"),
        ("pandas",  "pandas"),
    ]:
        try:
            __import__(mod)
        except ImportError:
            print(f"[fallback] pip installing {pkg}...", flush=True)
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", pkg],
                check=False,
            )


def try_wongkinyiu() -> bool:
    repo_dir = ensure_wongkinyiu_repo()
    ensure_deps()

    run_name = "wkyrun"
    # Clean any previous fallback run dir so detect.py names outputs predictably
    run_dir = Path(OUT_DIR) / run_name
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)

    cmd = [
        sys.executable, "detect.py",
        "--weights", WEIGHTS,
        "--source",  INPUT,
        "--project", OUT_DIR,
        "--name",    run_name,
        "--exist-ok",
        "--save-txt", "--save-conf",
        "--conf-thres", str(CONF),
        "--device", "0" if os.environ.get("CUDA_VISIBLE_DEVICES") else "cpu",
    ]
    env = {**os.environ, "PYTHONPATH": repo_dir + ":" + os.environ.get("PYTHONPATH", "")}
    print(f"[fallback] running detect.py from {repo_dir}", flush=True)
    res = subprocess.run(cmd, cwd=repo_dir, env=env)
    if res.returncode != 0:
        raise RuntimeError(f"WongKinYiu detect.py failed (exit {res.returncode})")

    saved = next((p for p in run_dir.iterdir()
                  if p.suffix.lower() in (".jpg", ".jpeg", ".png")), None)
    if saved is None:
        raise RuntimeError("WongKinYiu detect.py produced no annotated image")
    shutil.copy(str(saved), str(Path(OUT_DIR) / "annotated.jpg"))

    # Pull class names out of the checkpoint (needs the repo on sys.path)
    sys.path.insert(0, repo_dir)
    names = {}
    try:
        import torch
        ckpt = torch.load(WEIGHTS, map_location="cpu", weights_only=False)
        model_obj = ckpt.get("ema") or ckpt.get("model") or ckpt
        raw_names = getattr(model_obj, "names", None)
        if isinstance(raw_names, dict):
            names = {int(k): v for k, v in raw_names.items()}
        elif isinstance(raw_names, (list, tuple)):
            names = {i: n for i, n in enumerate(raw_names)}
    except Exception as e:
        print(f"[fallback] could not read class names from ckpt: {e}")

    # Parse detect.py labels: run_dir/labels/<stem>.txt, YOLO normalised xywh + conf
    from PIL import Image
    with Image.open(saved) as im:
        W, H = im.size

    labels_dir = run_dir / "labels"
    stem = Path(saved).stem
    label_file = labels_dir / f"{stem}.txt"
    boxes_out = []
    if label_file.is_file():
        for line in label_file.read_text().splitlines():
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            k = int(float(parts[0]))
            xc, yc, bw, bh = map(float, parts[1:5])
            conf = float(parts[5]) if len(parts) >= 6 else 0.0
            x1 = (xc - bw / 2) * W
            y1 = (yc - bh / 2) * H
            x2 = (xc + bw / 2) * W
            y2 = (yc + bh / 2) * H
            boxes_out.append({
                "x1": round(x1, 2), "y1": round(y1, 2),
                "x2": round(x2, 2), "y2": round(y2, 2),
                "conf": round(conf, 4),
                "cls":  k,
                "label": names.get(k, str(k)),
            })
    write_boxes(boxes_out)
    print(f"[wongkinyiu] Wrote {len(boxes_out)} detections")
    return True


# ── Orchestration ────────────────────────────────────────────────────────────
def main():
    try:
        try_ultralytics()
        return 0
    except Exception as e:
        msg = str(e)
        is_format_err = (
            "No module named 'models'" in msg
            or "NOT forwards compatible" in msg
            or "originally trained with" in msg
        )
        if not is_format_err:
            print(f"ERROR ultralytics: {e}", file=sys.stderr)
            return 1
        print(f"[predict] ultralytics cannot load this checkpoint, "
              f"falling back to WongKinYiu/yolov9: {msg[:200]}", flush=True)

    try:
        try_wongkinyiu()
        return 0
    except Exception as e:
        print(f"ERROR WongKinYiu fallback: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
