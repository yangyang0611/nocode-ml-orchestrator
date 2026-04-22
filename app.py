import cv2
import os
import zipfile
import numpy as np
from PIL import Image, ImageEnhance
import shutil
from flask import Flask, request, jsonify, send_from_directory, send_file, render_template, make_response
from flask_cors import CORS
import random
import time

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads/'
PROCESSED_FOLDER = 'processed/'
PROCESSED_FILES_FOLDER = os.path.join(PROCESSED_FOLDER, 'processed_files')
UNZIPPED_FOLDER = os.path.join(PROCESSED_FOLDER, 'unzipped')

def ensure_dir_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)

ensure_dir_exists(PROCESSED_FILES_FOLDER)
ensure_dir_exists(UPLOAD_FOLDER)
ensure_dir_exists(PROCESSED_FOLDER)
ensure_dir_exists(UNZIPPED_FOLDER)

def clear_folder(folder_path):
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')

def resize_image(image_path, label_path, output_image_path, output_label_path, target_size=(960, 960)):
    # Load image
    image = cv2.imread(image_path)
    original_height, original_width = image.shape[:2]

    # Resize image
    resized_image = cv2.resize(image, target_size)
    cv2.imwrite(output_image_path, resized_image)

    # Read YOLO label
    with open(label_path, 'r') as file:
        lines = file.readlines()

    resized_labels = []
    for line in lines:
        parts = line.strip().split()
        class_id = parts[0]
        x_center, y_center, width, height = map(float, parts[1:])

        # Convert YOLO format to pixel values
        x_center_pixel = x_center * original_width
        y_center_pixel = y_center * original_height
        width_pixel = width * original_width
        height_pixel = height * original_height

        # Calculate new bounding box in pixel values
        new_x_center_pixel = x_center_pixel * target_size[0] / original_width
        new_y_center_pixel = y_center_pixel * target_size[1] / original_height
        new_width_pixel = width_pixel * target_size[0] / original_width
        new_height_pixel = height_pixel * target_size[1] / original_height

        # Convert back to YOLO format
        new_x_center = new_x_center_pixel / target_size[0]
        new_y_center = new_y_center_pixel / target_size[1]
        new_width = new_width_pixel / target_size[0]
        new_height = new_height_pixel / target_size[1]

        resized_labels.append(f"{class_id} {new_x_center} {new_y_center} {new_width} {new_height}\n")

    # Write resized labels to file
    with open(output_label_path, 'w') as file:
        file.writelines(resized_labels)
    print(f"Resized image saved to {output_image_path}")

def mirror_image_and_labels(image_path, label_path, output_image_path, output_label_path):
    img = Image.open(image_path)
    mirrored_img = img.transpose(Image.FLIP_LEFT_RIGHT)
    mirrored_img.save(output_image_path)
    img.close()

    with open(label_path, 'r') as f:
        lines = f.readlines()

    width, height = img.size

    new_lines = []
    for line in lines:
        parts = line.strip().split()
        class_id = parts[0]
        x_center = float(parts[1])
        y_center = float(parts[2])
        width_bbox = float(parts[3])
        height_bbox = float(parts[4])

        new_x_center = 1 - x_center
        new_line = f"{class_id} {new_x_center} {y_center} {width_bbox} {height_bbox}\n"
        new_lines.append(new_line)

    with open(output_label_path, 'w') as f:
        f.writelines(new_lines)

def add_gaussian_noise(image, mean=0, std=0.1, seed=None):
    if seed is not None:
        np.random.seed(seed)
    np_image = np.array(image)
    gaussian = np.random.normal(mean, std, np_image.shape)
    noisy_image = np.clip(np_image + gaussian * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(noisy_image)

def random_brightness(image, factor1=1.0, factor2=1.0, seed=None):
    if seed is not None:
        np.random.seed(seed)
    enhancer = ImageEnhance.Brightness(image)
    factor1 = random.uniform(factor1, factor2)
    return enhancer.enhance(factor1)

def random_saturation(image, factor1=1.0, factor2=1.0, seed=None):
    if seed is not None:
        np.random.seed(seed)
    enhancer = ImageEnhance.Color(image)
    factor1 = random.uniform(factor1, factor2)
    return enhancer.enhance(factor1)

def rotate_image_and_labels(image_path, label_path, output_image_path, output_label_path, angle):
    if angle not in [90, 180, 270]:
        raise ValueError("Rotation angle must be 90, 180, or 270 degrees")
    
    img = Image.open(image_path)
    # Clockwise rotation: PIL rotates CCW for positive angles, so negate.
    rotated_img = img.rotate(-angle, expand=True)
    rotated_img.save(output_image_path)
    img.close()
    print(f"Rotated image saved to {output_image_path}")

    with open(label_path, 'r') as f:
        lines = f.readlines()

    width, height = img.size

    new_lines = []
    for line in lines:
        parts = line.strip().split()
        class_id = parts[0]
        x_center = float(parts[1])
        y_center = float(parts[2])
        width_bbox = float(parts[3])
        height_bbox = float(parts[4])

        if angle == 90:
            # Clockwise 90°
            new_x_center = 1 - y_center
            new_y_center = x_center
            new_width_bbox = height_bbox
            new_height_bbox = width_bbox
        elif angle == 180:
            new_x_center = 1 - x_center
            new_y_center = 1 - y_center
            new_width_bbox = width_bbox
            new_height_bbox = height_bbox
        elif angle == 270:
            # Clockwise 270°
            new_x_center = y_center
            new_y_center = 1 - x_center
            new_width_bbox = height_bbox
            new_height_bbox = width_bbox

        new_line = f"{class_id} {new_x_center} {new_y_center} {new_width_bbox} {new_height_bbox}\n"
        new_lines.append(new_line)

    with open(output_label_path, 'w') as f:
        f.writelines(new_lines)
    print(f"Rotated labels saved to {output_label_path}")

def unzip_file(zip_src, dst_dir):
    with zipfile.ZipFile(zip_src, 'r') as zip_ref:
        zip_ref.extractall(dst_dir)

def zip_folder(folder_path, output_path):
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                if not file.startswith('temp'):
                    zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), folder_path))

@app.route('/')
def index():
    response = make_response(render_template('index.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response


@app.route('/train')
def train():
    return render_template('train.html')


@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@app.route('/inference')
def inference_page():
    return render_template('inference.html')


INFERENCE_RUNS_FOLDER = 'inference_runs/'
ensure_dir_exists(INFERENCE_RUNS_FOLDER)


@app.route('/inference_runs/<req_id>/<path:filename>')
def inference_run_file(req_id, filename):
    safe_dir = os.path.abspath(os.path.join(INFERENCE_RUNS_FOLDER, req_id))
    if not safe_dir.startswith(os.path.abspath(INFERENCE_RUNS_FOLDER)):
        return jsonify({"error": "invalid path"}), 400
    return send_from_directory(safe_dir, filename)

def clear_upload_folder():
    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')
            
IMAGE_EXTS = ('.png', '.jpg', '.jpeg')


def validate_yolo_zip(zip_path):
    """Inspect zip contents. Returns (ok, message, report).
    Hard-fails only when the zip is invalid or contains no images.
    Otherwise always ok=True and lets the caller surface warnings."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = [n for n in zf.namelist() if not n.endswith('/')]
    except zipfile.BadZipFile:
        return False, "Uploaded file is not a valid .zip archive.", {}

    image_map = {os.path.splitext(os.path.basename(n))[0]: os.path.basename(n)
                 for n in names if n.lower().endswith(IMAGE_EXTS)}
    label_map = {os.path.splitext(os.path.basename(n))[0]: os.path.basename(n)
                 for n in names if n.lower().endswith('.txt')}

    if not image_map:
        return False, "Zip contains no images (.png/.jpg/.jpeg).", {"images": 0}

    image_stems = set(image_map)
    label_stems = set(label_map)
    matched_stems      = image_stems & label_stems
    unmatched_images   = sorted(image_map[s] for s in image_stems - label_stems)
    orphan_labels      = sorted(label_map[s] for s in label_stems - image_stems)

    report = {
        "images":           len(image_map),
        "labels":           len(label_map),
        "matched":          len(matched_stems),
        "unmatched_images": unmatched_images,
        "orphan_labels":    orphan_labels,
    }
    return True, "ok", report


@app.route('/upload', methods=['POST'])
def upload():
    clear_upload_folder()

    files = request.files.getlist('files')
    if not files:
        return jsonify({"error": "No file uploaded"}), 400
    if len(files) > 1:
        return jsonify({"error": "Please upload a single .zip file."}), 400

    f = files[0]
    if not f.filename.lower().endswith('.zip'):
        return jsonify({"error": "Only .zip files are accepted."}), 400

    dataset_filename = "uploaded_dataset.zip"
    dataset_path = os.path.join(PROCESSED_FOLDER, dataset_filename)
    f.save(dataset_path)

    ok, msg, report = validate_yolo_zip(dataset_path)
    if not ok:
        try:
            os.remove(dataset_path)
        except OSError:
            pass
        return jsonify({"error": msg, "stats": report}), 400

    return jsonify({
        "message": f"Uploaded: {report['matched']}/{report['images']} image–label pairs.",
        "datasetFilename": dataset_filename,
        "report": report,
    }), 200

@app.route('/upload', methods=['DELETE'])
def remove_upload():
    clear_upload_folder()
    removed = []
    for fname in ("uploaded_dataset.zip",):
        fpath = os.path.join(PROCESSED_FOLDER, fname)
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
                removed.append(fname)
            except OSError as e:
                return jsonify({"error": f"Failed to remove {fname}: {e}"}), 500
    return jsonify({"message": "Upload removed", "removed": removed}), 200


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    response = make_response(send_from_directory(UPLOAD_FOLDER, filename))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.route('/process', methods=['POST'])
def process():
    data = request.json
    options = data.get('options', {})
    dataset_filename = data.get('datasetFilename', '')

    print(f"Received options: {options}")
    print(f"Received dataset filename: {dataset_filename}")
    
    if not dataset_filename:
        return jsonify({"error": "No dataset filename provided"}), 400

    dataset_path = os.path.join(PROCESSED_FOLDER, dataset_filename)
    unzip_dir = UNZIPPED_FOLDER
    
    ensure_dir_exists(unzip_dir)
    ensure_dir_exists(PROCESSED_FILES_FOLDER)

    # Clear the unzipped and processed_files directory
    clear_folder(unzip_dir)
    clear_folder(PROCESSED_FILES_FOLDER)

    unzip_file(dataset_path, unzip_dir)
    print(f"Unzipped dataset to {unzip_dir}")

    # Build basename -> label path index so images and labels can live in
    # separate directories (e.g. images/ and labels/).
    label_index = {}
    for r, _, fs in os.walk(unzip_dir):
        for fn in fs:
            if fn.lower().endswith('.txt'):
                label_index[os.path.splitext(fn)[0]] = os.path.join(r, fn)

    for root, dirs, files in os.walk(unzip_dir):
        for file in files:
            if file.lower().endswith(IMAGE_EXTS):
                original_img_path = os.path.join(root, file)
                stem = os.path.splitext(file)[0]
                original_label_path = label_index.get(stem)
                if not original_label_path or not os.path.exists(original_label_path):
                    print(f"Skipping {original_img_path}: no matching .txt label")
                    continue
                final_img_path = os.path.join(PROCESSED_FILES_FOLDER, file)
                final_label_path = os.path.join(PROCESSED_FILES_FOLDER, os.path.splitext(file)[0] + '.txt')

                # Create a temporary path for intermediate processing steps
                temp_img_path = os.path.join(PROCESSED_FILES_FOLDER, f"temp_{file}")
                temp_label_path = os.path.join(PROCESSED_FILES_FOLDER, f"temp_{os.path.splitext(file)[0]}.txt")

                current_img_path = original_img_path
                current_label_path = original_label_path

                if options.get('sequence'):
                    sequence = options['sequence']
                    for step in sequence:
                        if step['step'] == 'Rotate':
                            angle = int(step['params'].get('angle', 90))
                            print(f"Rotating image by {angle} degrees")
                            if angle not in [90, 180, 270]:
                                return jsonify({"error": "Invalid rotation angle. Must be 90, 180, or 270 degrees."}), 400
                            rotate_image_and_labels(current_img_path, current_label_path, temp_img_path, temp_label_path, angle)
                            current_img_path, current_label_path = temp_img_path, temp_label_path

                        elif step['step'] == 'Mirror':
                            print(f"Adding Mirror")
                            mirror_image_and_labels(current_img_path, current_label_path, temp_img_path, temp_label_path)
                            current_img_path, current_label_path = temp_img_path, temp_label_path

                        elif step['step'] == 'Add Noise':
                            img = Image.open(current_img_path)
                            noise_type = step['params'].get('type', 'Gaussian')
                            print(f"Adding noise: {noise_type}")
                            if noise_type == 'Gaussian':
                                mean = float(step['params'].get('mean', 0))
                                std = float(step['params'].get('std', 0.1))
                                print(f"Gaussian noise params: mean={mean}, std={std}")
                                img = add_gaussian_noise(img, mean, std, seed=42)
                            elif noise_type == 'Brightness':
                                factor1 = float(step['params'].get('factor1', 1.0))
                                factor2 = float(step['params'].get('factor2', 1.0))
                                print(f"Brightness factors: factor1={factor1}, factor2={factor2}")
                                img = random_brightness(img, factor1, factor2, seed=42)
                            elif noise_type == 'Saturation':
                                factor1 = float(step['params'].get('factor1', 1.0))
                                factor2 = float(step['params'].get('factor2', 1.0))
                                print(f"Saturation factors: factor1={factor1}, factor2={factor2}")
                                img = random_saturation(img, factor1, factor2, seed=42)
                            img.save(temp_img_path)
                            img.close()
                            current_img_path = temp_img_path

                        elif step['step'] == 'Resize':
                            img = Image.open(current_img_path)
                            width = int(step['params'].get('width', 960))
                            height = int(step['params'].get('height', 960))
                            print(f"Resizing image to {width}x{height}")
                            resize_image(current_img_path, current_label_path, temp_img_path, temp_label_path, (width, height))
                            current_img_path, current_label_path = temp_img_path, temp_label_path

                # After all processing steps, save the final result with the original filename
                shutil.copy(current_img_path, final_img_path)
                if os.path.exists(current_label_path):
                    shutil.copy(current_label_path, final_label_path)
                    print(f"Final image saved to {final_img_path}")

                # Clean up temporary files immediately after use
                if os.path.exists(temp_img_path):
                    try:
                        os.remove(temp_img_path)
                    except PermissionError:
                        print(f"Could not delete temporary file {temp_img_path} because it is being used by another process.")
                if os.path.exists(temp_label_path):
                    try:
                        os.remove(temp_label_path)
                    except PermissionError:
                        print(f"Could not delete temporary file {temp_label_path} because it is being used by another process.")

    # Ensure no temp files are in the processed files folder
    for root, dirs, files in os.walk(PROCESSED_FILES_FOLDER):
        for file in files:
            if file.startswith('temp'):
                try:
                    os.remove(os.path.join(root, file))
                except PermissionError:
                    print(f"Could not delete temporary file {file} because it is being used by another process.")

    processed_dataset_filename = "processed_dataset.zip"
    processed_dataset_path = os.path.join(PROCESSED_FOLDER, processed_dataset_filename)
    zip_folder(PROCESSED_FILES_FOLDER, processed_dataset_path)
    print(f"Zipped processed dataset to {processed_dataset_path}")

    return jsonify({"message": "Images processed successfully", "datasetFilename": processed_dataset_filename}), 200

@app.route('/download/<filename>')
def download_file(filename):
    full_path = os.path.join(PROCESSED_FOLDER, filename)
    response = make_response(send_file(full_path, as_attachment=True))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# ── Dataset List API ──────────────────────────────────────────────────────────
@app.route('/api/datasets', methods=['GET'])
def api_list_datasets():
    datasets = []
    if os.path.isdir(PROCESSED_FOLDER):
        for fname in os.listdir(PROCESSED_FOLDER):
            if fname.endswith('.zip'):
                fpath = os.path.join(PROCESSED_FOLDER, fname)
                stat = os.stat(fpath)
                datasets.append({
                    "name": fname,
                    "size_mb": round(stat.st_size / 1024 / 1024, 2),
                    "modified": time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(stat.st_mtime)),
                })
    datasets.sort(key=lambda x: x['modified'], reverse=True)
    return jsonify(datasets), 200


# ── Job Orchestration API ─────────────────────────────────────────────────────
from job_manager.queue_manager import (
    submit_job, get_job, list_jobs, cancel_job, delete_job, get_queue_status,
)
from job_manager.gpu_manager import get_gpu_status
from job_manager.docker_manager import get_container_logs
from job_manager.scheduler import start_scheduler


@app.route('/api/jobs', methods=['POST'])
def api_submit_job():
    data = request.json or {}
    required = {'model', 'epochs', 'dataset'}
    if not required.issubset(data):
        return jsonify({"error": f"Missing fields: {required - data.keys()}"}), 400

    job_config = {
        "model":      data['model'],
        "epochs":     str(data['epochs']),
        "batch_size": str(data.get('batch_size', 16)),
        "imgsz":      str(data.get('imgsz', 640)),
        "lr0":        str(data.get('lr0', 0.01)),
        "optimizer":  data.get('optimizer', 'auto'),
        "patience":   str(data.get('patience', 50)),
        "dataset":    data['dataset'],
        "user":       data.get('user', 'anonymous'),
    }
    priority = data.get('priority', 'medium')
    job_id = submit_job(job_config, priority=priority)
    return jsonify({"job_id": job_id, "status": "pending"}), 201


@app.route('/api/jobs', methods=['GET'])
def api_list_jobs():
    return jsonify(list_jobs()), 200


@app.route('/api/jobs/<job_id>', methods=['GET'])
def api_get_job(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job), 200


@app.route('/api/jobs/<job_id>', methods=['DELETE'])
def api_delete_job(job_id):
    """Delete a job record. Works for any status:
    - running: stop container, release GPU, then remove record.
    - pending: remove from queue, then remove record.
    - completed/failed/cancelled: remove record directly.
    """
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Running: synchronously release container + GPU before delete
    if job.get("status") == "running":
        from job_manager.docker_manager import stop_container, get_container_status, remove_container
        from job_manager.gpu_manager import release_gpu
        cid = job.get("container_id", "")
        if cid:
            try:
                if get_container_status(cid) == "running":
                    stop_container(cid)
                else:
                    remove_container(cid)
            except Exception as e:
                print(f"[delete_job] container cleanup error: {e}")
        gpu_id_str = job.get("gpu_id", "")
        if gpu_id_str != "":
            try:
                release_gpu(int(gpu_id_str))
            except Exception as e:
                print(f"[delete_job] gpu release error: {e}")

    delete_job(job_id)
    return jsonify({"job_id": job_id, "status": "deleted"}), 200


import re

# Ultralytics progress-bar line: "... : 37% ━━━─── 2/36 ..."  We keep 100%
# lines (useful end-of-epoch summary) and drop all intermediate updates.
_PROGRESS_RE = re.compile(r'(\d+)%\s+[─━╸]+\s*\d+/\d+')
# ANSI escape sequences (e.g. '\x1b[K') that appear in container logs.
_ANSI_RE = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]')


def clean_training_logs(raw: str) -> str:
    if not raw:
        return raw
    out = []
    for line in raw.splitlines():
        line = _ANSI_RE.sub('', line)
        m = _PROGRESS_RE.search(line)
        if m and int(m.group(1)) < 100:
            continue
        out.append(line)
    return "\n".join(out)


@app.route('/api/jobs/<job_id>/logs', methods=['GET'])
def api_get_logs(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Prefer live container logs when running, else return stored logs
    container_id = job.get("container_id", "")
    if container_id:
        logs = get_container_logs(container_id, tail=2000)
    else:
        logs = job.get("logs", "")
    return jsonify({"job_id": job_id, "logs": clean_training_logs(logs)}), 200


@app.route('/api/jobs/<job_id>/metrics', methods=['GET'])
def api_get_metrics(job_id):
    """Read results.csv produced by ultralytics and return per-epoch metrics."""
    if not re.fullmatch(r'[0-9a-fA-F-]{36}', job_id):
        return jsonify({"error": "invalid job_id"}), 400
    csv_path = os.path.join('results', job_id, 'results.csv')
    if not os.path.isfile(csv_path):
        return jsonify({"job_id": job_id, "epochs": [], "series": {}}), 200

    import csv
    series: dict[str, list] = {}
    epochs: list[int] = []
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ep = int(float(row.get('epoch', '0')))
            except ValueError:
                continue
            epochs.append(ep)
            for k, v in row.items():
                if k == 'epoch' or v is None or v == '':
                    continue
                try:
                    series.setdefault(k, []).append(float(v))
                except ValueError:
                    pass
    return jsonify({"job_id": job_id, "epochs": epochs, "series": series}), 200


@app.route('/api/resources', methods=['GET'])
def api_resources():
    return jsonify(get_gpu_status()), 200


@app.route('/api/queue', methods=['GET'])
def api_queue():
    return jsonify(get_queue_status()), 200


# ── Inference API ─────────────────────────────────────────────────────────────
from job_manager.inference_manager import (
    list_all_models, save_user_model, delete_user_model, run_inference,
)


@app.route('/api/models', methods=['GET'])
def api_list_models():
    return jsonify(list_all_models(list_jobs())), 200


@app.route('/api/models/upload', methods=['POST'])
def api_upload_model():
    f = request.files.get('model')
    if f is None or not f.filename:
        return jsonify({"error": "No model file uploaded"}), 400
    if not f.filename.lower().endswith('.pt'):
        return jsonify({"error": "Only .pt files are accepted"}), 400
    display_name = request.form.get('name', '').strip()
    try:
        record = save_user_model(f.read(), f.filename, display_name)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(record), 201


@app.route('/api/models/<model_id>', methods=['DELETE'])
def api_delete_model(model_id):
    if not delete_user_model(model_id):
        return jsonify({"error": "Model not found or not deletable"}), 404
    return jsonify({"id": model_id, "deleted": True}), 200


@app.route('/api/inference', methods=['POST'])
def api_inference():
    model_id = (request.form.get('model_id') or request.form.get('job_id') or '').strip()
    if not model_id:
        return jsonify({"error": "Missing model_id"}), 400

    f = request.files.get('image')
    if f is None or not f.filename:
        return jsonify({"error": "No image uploaded"}), 400
    if not f.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        return jsonify({"error": "Only .jpg/.jpeg/.png images are accepted"}), 400

    try:
        conf = float(request.form.get('conf', '0.25'))
    except ValueError:
        conf = 0.25

    try:
        result = run_inference(model_id, f.read(), f.filename, conf=conf)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(result), 200


# ── Start scheduler when Flask launches ───────────────────────────────────────
start_scheduler()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, use_reloader=True)
