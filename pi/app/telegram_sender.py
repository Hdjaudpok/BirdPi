#!/usr/bin/env python3
"""Telegram notification sender for BirdPi v2.

Optimised for Raspberry Pi 2 Model B (ARMv7, 1GB RAM, no GPU):
- YOLOv8-nano ONNX custom model (bird detection, 11.6MB)
- CLAHE preprocessing for IR/nighttime contrast enhancement
- Temporal IoU tracker (3-frame confirmation, eliminates false positives)
- Activity classifier (entry/exit/feeding/resting/transit)
- Lazy imports (cv2/numpy only when AI enabled)
- Memory-conscious frame capture (single connection, bounded buffer)
- Explicit garbage collection after AI inference
- JPEG quality reduced (75) for faster upload on slow networks

v2 changes vs v1:
- YOLOv4-tiny (37MB, 80 COCO classes) -> YOLOv8-nano ONNX (11.6MB, 2 custom classes)
- Added CLAHE preprocessing before inference
- Added temporal tracker (3-frame confirmation)
- Added activity classifier (behavior detection)
- Telegram captions enriched with behavior info
"""
import argparse
import gc
import json
import os
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

_BIRDPI_DIR = Path(os.environ.get("BIRDPI_DIR", Path.home() / "birdpi"))
CONFIG_PATH = _BIRDPI_DIR / "config.env"
MOTION_STREAM_URL = "http://localhost:{port}"
DEFAULT_MESSAGE = "Mouvement detecte dans le birdpi"
EVENT_ACTIVE_FILE_DEFAULT = _BIRDPI_DIR / ".event_active"

# Pi 2 memory guard: max raw frame size to prevent OOM (640x480x3 = 921KB)
MAX_JPEG_SIZE = 500_000  # 500KB - reject corrupt/oversized JPEG frames

# YOLOv8 custom model classes (trained on birdpi dataset)
MODEL_CLASSES = ["bird", "other_animal"]


@dataclass
class AppConfig:
    token: str
    chat_id: str
    stream_port: int
    snapshot_count: int
    snapshot_interval: float
    min_jpeg_size: int
    loop_interval_sec: float
    loop_max_per_event: int
    event_active_file: Path
    ai_enabled: bool
    ai_require_target: bool
    ai_targets: set
    ai_confidence: float
    ai_nms: float
    ai_input_size: int
    ai_annotate: bool
    ai_model_path: Path
    clahe_enabled: bool
    clahe_clip: float
    tracker_enabled: bool
    tracker_confirm_frames: int
    classifier_enabled: bool


@dataclass
class AiResult:
    labels: list
    matched_target: bool
    annotated_photo: bytes | None
    detections: list  # raw detections for tracker
    behavior: str  # from activity classifier


# ---------------------------------------------------------------------------
# Temporal IoU Tracker (embedded for single-file Pi deployment)
# ---------------------------------------------------------------------------
@dataclass
class TrackedObject:
    track_id: int
    label: str
    bbox: list  # [x1, y1, x2, y2]
    confidence: float
    frames_seen: int = 1
    frames_missing: int = 0
    confirmed: bool = False
    first_frame: int = 0
    last_frame: int = 0


def _compute_iou(box_a, box_b):
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


class TemporalTracker:
    """IoU-based multi-frame tracker. Confirms detections after N frames."""

    def __init__(self, min_iou=0.3, confirm_frames=3, max_missing=2):
        self.min_iou = min_iou
        self.confirm_frames = confirm_frames
        self.max_missing = max_missing
        self._tracks = []
        self._next_id = 0
        self._frame_count = 0

    def update(self, detections):
        """Update with new detections. Returns list of confirmed TrackedObjects."""
        self._frame_count += 1
        matched_tracks = set()
        matched_dets = set()

        pairs = []
        for ti, track in enumerate(self._tracks):
            for di, det in enumerate(detections):
                if det["label"] == track.label:
                    iou = _compute_iou(track.bbox, det["bbox"])
                    if iou >= self.min_iou:
                        pairs.append((iou, ti, di))

        pairs.sort(reverse=True)
        for iou, ti, di in pairs:
            if ti in matched_tracks or di in matched_dets:
                continue
            track = self._tracks[ti]
            det = detections[di]
            track.bbox = det["bbox"]
            track.confidence = max(track.confidence, det["confidence"])
            track.frames_seen += 1
            track.frames_missing = 0
            track.last_frame = self._frame_count
            if track.frames_seen >= self.confirm_frames:
                track.confirmed = True
            matched_tracks.add(ti)
            matched_dets.add(di)

        for ti, track in enumerate(self._tracks):
            if ti not in matched_tracks:
                track.frames_missing += 1

        for di, det in enumerate(detections):
            if di not in matched_dets:
                self._tracks.append(TrackedObject(
                    track_id=self._next_id,
                    label=det["label"],
                    bbox=det["bbox"],
                    confidence=det["confidence"],
                    first_frame=self._frame_count,
                    last_frame=self._frame_count,
                ))
                self._next_id += 1

        self._tracks = [t for t in self._tracks if t.frames_missing <= self.max_missing]
        return [t for t in self._tracks if t.confirmed]

    def reset(self):
        self._tracks.clear()
        self._next_id = 0
        self._frame_count = 0


# ---------------------------------------------------------------------------
# Activity Classifier (embedded, rule-based, zero overhead)
# ---------------------------------------------------------------------------
class ActivityClassifier:
    """Classifies bird behavior from tracking data."""

    def __init__(self, img_w=640, img_h=480, edge_margin=50,
                 resting_threshold=15, transit_speed=30):
        self.img_w = img_w
        self.img_h = img_h
        self.edge_margin = edge_margin
        self.resting_threshold = resting_threshold
        self.transit_speed = transit_speed
        self._history = {}  # track_id -> list of bbox centers

    def update(self, track_id, bbox):
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        if track_id not in self._history:
            self._history[track_id] = []
        self._history[track_id].append({"cx": cx, "cy": cy, "area": area})

    def classify(self, track_id):
        if track_id not in self._history:
            return "inconnu"
        history = self._history[track_id]
        n = len(history)
        if n < 2:
            return "inconnu"

        first, last = history[0], history[-1]
        total_movement = sum(
            ((history[i]["cx"] - history[i-1]["cx"])**2 +
             (history[i]["cy"] - history[i-1]["cy"])**2)**0.5
            for i in range(1, n)
        )
        avg_movement = total_movement / (n - 1)
        area_ratio = last["area"] / first["area"] if first["area"] > 0 else 1.0

        at_edge_first = self._is_at_edge(first)
        at_edge_last = self._is_at_edge(last)

        if at_edge_first and not at_edge_last and area_ratio > 1.2:
            return "entree"
        if not at_edge_first and at_edge_last and area_ratio < 0.8:
            return "sortie"
        if avg_movement >= self.transit_speed:
            return "transit"
        if avg_movement <= self.resting_threshold and n >= 5:
            return "repos"
        if avg_movement <= self.resting_threshold * 2:
            return "alimentation"
        return "activite"

    def _is_at_edge(self, point):
        m = self.edge_margin
        return (point["cx"] < m or point["cx"] > self.img_w - m or
                point["cy"] < m or point["cy"] > self.img_h - m)

    def clear(self, track_id=None):
        if track_id is not None:
            self._history.pop(track_id, None)
        else:
            self._history.clear()


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
def load_env(path):
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def parse_bool(value, default=False):
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_int(value, default):
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def parse_float(value, default):
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_targets(value, default):
    raw = value if value is not None else default
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def load_config(path):
    cfg = load_env(path)
    token = cfg.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = cfg.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant dans config.env")

    return AppConfig(
        token=token,
        chat_id=chat_id,
        stream_port=parse_int(cfg.get("MOTION_STREAM_PORT"), 8081),
        snapshot_count=parse_int(cfg.get("TELEGRAM_SNAPSHOT_COUNT"), 6),
        snapshot_interval=parse_float(cfg.get("TELEGRAM_SNAPSHOT_INTERVAL_SEC"), 0.25),
        min_jpeg_size=parse_int(cfg.get("TELEGRAM_MIN_JPEG_SIZE"), 6000),
        loop_interval_sec=parse_float(cfg.get("TELEGRAM_INTERVAL_SEC"), 1.0),
        loop_max_per_event=parse_int(cfg.get("TELEGRAM_MAX_PER_EVENT"), 0),
        event_active_file=Path(cfg.get("TELEGRAM_EVENT_ACTIVE_FILE", str(EVENT_ACTIVE_FILE_DEFAULT))),
        ai_enabled=parse_bool(cfg.get("TELEGRAM_AI_ENABLED"), False),
        ai_require_target=parse_bool(cfg.get("TELEGRAM_AI_REQUIRE_TARGET"), False),
        ai_targets=parse_targets(cfg.get("TELEGRAM_AI_TARGETS"), "bird"),
        ai_confidence=parse_float(cfg.get("TELEGRAM_AI_CONFIDENCE"), 0.35),
        ai_nms=parse_float(cfg.get("TELEGRAM_AI_NMS"), 0.45),
        ai_input_size=parse_int(cfg.get("TELEGRAM_AI_INPUT_SIZE"), 224),
        ai_annotate=parse_bool(cfg.get("TELEGRAM_AI_ANNOTATE"), True),
        ai_model_path=Path(cfg.get("TELEGRAM_AI_MODEL", str(_BIRDPI_DIR / "models" / "yolov8n_birdpi_224.onnx"))),
        clahe_enabled=parse_bool(cfg.get("TELEGRAM_CLAHE_ENABLED"), True),
        clahe_clip=parse_float(cfg.get("TELEGRAM_CLAHE_CLIP"), 2.0),
        tracker_enabled=parse_bool(cfg.get("TELEGRAM_TRACKER_ENABLED"), True),
        tracker_confirm_frames=parse_int(cfg.get("TELEGRAM_TRACKER_CONFIRM_FRAMES"), 3),
        classifier_enabled=parse_bool(cfg.get("TELEGRAM_CLASSIFIER_ENABLED"), True),
    )


# ---------------------------------------------------------------------------
# Frame capture
# ---------------------------------------------------------------------------
def _read_one_frame(resp):
    """Read a single JPEG frame from MJPEG stream. Bounded to prevent OOM on Pi 2."""
    buf = b""
    max_read = MAX_JPEG_SIZE + 4096
    total_read = 0
    while total_read < max_read:
        chunk = resp.read(4096)
        if not chunk:
            return None
        buf += chunk
        total_read += len(chunk)
        start = buf.find(b"\xff\xd8")
        if start == -1:
            buf = buf[-1:]
            total_read = len(buf)
            continue
        buf = buf[start:]
        end = buf.find(b"\xff\xd9", 2)
        if end != -1:
            frame = buf[: end + 2]
            if len(frame) > MAX_JPEG_SIZE:
                return None
            return frame
    return None


def jpeg_sharpness(data, min_jpeg_size):
    if len(data) < min_jpeg_size:
        return 0.0
    sample = data[2:min(len(data), 8192)]
    if not sample:
        return 0.0
    mean = sum(sample) / len(sample)
    variance = sum((byte - mean) ** 2 for byte in sample) / len(sample)
    return variance * len(data)


def capture_best_snapshot(config):
    """Capture frames and pick the sharpest. Uses single connection for Pi 2 efficiency."""
    url = MOTION_STREAM_URL.format(port=config.stream_port)
    best_frame = None
    best_score = 0.0

    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            for idx in range(config.snapshot_count):
                if idx > 0:
                    time.sleep(config.snapshot_interval)
                frame = _read_one_frame(resp)
                if frame is None:
                    break
                score = jpeg_sharpness(frame, config.min_jpeg_size)
                if score > best_score:
                    best_score = score
                    best_frame = frame
    except Exception:
        if best_frame is None:
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    best_frame = _read_one_frame(resp)
            except Exception:
                pass

    return best_frame


# ---------------------------------------------------------------------------
# Telegram API
# ---------------------------------------------------------------------------
def send_photo(token, chat_id, photo, caption):
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    boundary = "----BirdPiBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
        f"{chat_id}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="caption"\r\n\r\n'
        f"{caption}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="photo"; filename="snapshot.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8")
    body += photo
    body += f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result.get("ok", False)


def send_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result.get("ok", False)


# ---------------------------------------------------------------------------
# YOLOv8-nano ONNX Detector
# ---------------------------------------------------------------------------
class YoloV8Detector:
    """YOLOv8-nano ONNX detector optimised for Pi 2 (ARMv7, 1GB RAM).

    Key differences from v1 (YOLOv4-tiny):
    - Uses cv2.dnn.readNetFromONNX (not readNetFromDarknet)
    - Custom 2-class model (bird, other_animal) vs 80 COCO classes
    - 11.6MB vs 37MB model size
    - YOLOv8 output format: [1, num_classes+4, num_predictions]
    - Built-in CLAHE preprocessing for IR/night images
    - No separate objectness score (class scores are direct)

    Pi 2 optimisations preserved:
    - Lazy model loading (load on first detect, not at init)
    - Reduced input size (224px default)
    - Explicit gc.collect() after inference
    - Single-thread OpenCV DNN
    - Memory guard (skip if <200MB RAM available)
    """

    CLASS_NAMES = MODEL_CLASSES  # ["bird", "other_animal"]

    def __init__(self, config):
        self.enabled = False
        self.require_target = config.ai_require_target
        self.targets = config.ai_targets
        self._model_loaded = False
        self._config = config

        if not config.ai_enabled:
            return

        try:
            import cv2
            import numpy as np
        except Exception as exc:
            print(f"[telegram] IA desactivee: opencv/numpy indisponible ({exc})", file=sys.stderr)
            return

        if not config.ai_model_path.exists():
            print(f"[telegram] IA desactivee: modele ONNX manquant ({config.ai_model_path})", file=sys.stderr)
            return

        self.cv2 = cv2
        self.np = np
        self.input_size = max(160, min(config.ai_input_size, 640))
        self.conf_threshold = max(0.05, min(config.ai_confidence, 0.95))
        self.nms_threshold = max(0.05, min(config.ai_nms, 0.95))
        self.annotate = config.ai_annotate
        self.clahe_enabled = config.clahe_enabled
        self.clahe_clip = config.clahe_clip

        self.enabled = True
        print(f"[telegram] IA YOLOv8-nano ONNX prete (input={self.input_size}px, "
              f"classes={self.CLASS_NAMES}, CLAHE={'on' if self.clahe_enabled else 'off'}, "
              f"chargement differe)")

    @staticmethod
    def _available_ram_mb():
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
        except Exception:
            pass
        return 9999

    def _ensure_model(self):
        if self._model_loaded:
            return

        avail_mb = self._available_ram_mb()
        if avail_mb < 200:
            print(f"[telegram] IA desactivee: RAM insuffisante ({avail_mb}MB libre, min 200MB)", file=sys.stderr)
            self.enabled = False
            return

        self.net = self.cv2.dnn.readNetFromONNX(str(self._config.ai_model_path))
        self.net.setPreferableBackend(self.cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(self.cv2.dnn.DNN_TARGET_CPU)
        self.cv2.setNumThreads(1)  # Pi 2: avoid ARM cache-line bouncing
        self._model_loaded = True
        model_size_kb = self._config.ai_model_path.stat().st_size // 1024
        avail_after = self._available_ram_mb()
        print(f"[telegram] modele YOLOv8-nano charge ({model_size_kb}KB, RAM: {avail_mb}MB->{avail_after}MB)")

    def _apply_clahe(self, frame):
        """CLAHE on LAB L-channel for IR/nighttime contrast enhancement."""
        if not self.clahe_enabled:
            return frame
        lab = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2LAB)
        l, a, b = self.cv2.split(lab)
        clahe = self.cv2.createCLAHE(clipLimit=self.clahe_clip, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l)
        lab_enhanced = self.cv2.merge([l_enhanced, a, b])
        return self.cv2.cvtColor(lab_enhanced, self.cv2.COLOR_LAB2BGR)

    def _decode_jpeg(self, photo):
        buf = self.np.frombuffer(photo, dtype=self.np.uint8)
        return self.cv2.imdecode(buf, self.cv2.IMREAD_COLOR)

    def _decode_yolov8_output(self, output, img_w, img_h):
        """Decode YOLOv8 ONNX output tensor.

        YOLOv8 output shape: [1, num_classes+4, num_predictions]
        Format per prediction (after transpose): [x_center, y_center, w, h, class0_score, class1_score, ...]
        No separate objectness - class scores are direct confidence values.
        """
        # output shape: [1, 6, N] -> transpose to [N, 6]
        predictions = output[0].T  # [N, 6] for 2 classes

        boxes = []
        confidences = []
        class_ids = []

        for pred in predictions:
            # First 4 values are bbox in normalized coords
            cx, cy, w, h = pred[0], pred[1], pred[2], pred[3]

            # Remaining values are class scores
            class_scores = pred[4:]
            class_id = int(self.np.argmax(class_scores))
            confidence = float(class_scores[class_id])

            if confidence < self.conf_threshold:
                continue

            # Convert from model coords to pixel coords
            x = int((cx - w / 2) * img_w / self.input_size)
            y = int((cy - h / 2) * img_h / self.input_size)
            box_w = int(w * img_w / self.input_size)
            box_h = int(h * img_h / self.input_size)

            boxes.append([x, y, box_w, box_h])
            confidences.append(confidence)
            class_ids.append(class_id)

        return boxes, confidences, class_ids

    def detect(self, photo):
        """Run YOLOv8 inference with CLAHE preprocessing."""
        empty = AiResult(labels=[], matched_target=False, annotated_photo=None, detections=[], behavior="")
        if not self.enabled:
            return empty

        self._ensure_model()
        if not self._model_loaded:
            return empty

        frame = self._decode_jpeg(photo)
        if frame is None:
            return empty

        # Apply CLAHE before inference
        enhanced = self._apply_clahe(frame)

        (img_h, img_w) = frame.shape[:2]
        blob = self.cv2.dnn.blobFromImage(
            enhanced,
            scalefactor=1.0 / 255.0,
            size=(self.input_size, self.input_size),
            swapRB=True,
            crop=False,
        )
        self.net.setInput(blob)
        outputs = self.net.forward(self.net.getUnconnectedOutLayersNames())
        del blob

        # Decode YOLOv8 output
        boxes, confidences, class_ids = self._decode_yolov8_output(outputs[0], img_w, img_h)
        del outputs

        if not boxes:
            del frame, enhanced
            gc.collect()
            return empty

        # NMS
        indices = self.cv2.dnn.NMSBoxes(boxes, confidences, self.conf_threshold, self.nms_threshold)
        if len(indices) == 0:
            del frame, enhanced
            gc.collect()
            return empty

        if hasattr(indices, "flatten"):
            kept = [int(i) for i in indices.flatten()]
        else:
            kept = [int(i[0]) if isinstance(i, (list, tuple)) else int(i) for i in indices]

        labels = []
        raw_detections = []
        annotated = frame.copy() if (self.annotate and kept) else None

        TARGET_COLORS = {"bird": (0, 255, 0), "other_animal": (0, 165, 255)}

        for idx in kept:
            class_id = class_ids[idx]
            label = self.CLASS_NAMES[class_id] if class_id < len(self.CLASS_NAMES) else f"class_{class_id}"
            conf = confidences[idx]
            x, y, box_w, box_h = boxes[idx]
            labels.append(label)

            # Raw detection for tracker (convert to [x1, y1, x2, y2])
            raw_detections.append({
                "label": label,
                "confidence": conf,
                "bbox": [x, y, x + box_w, y + box_h],
            })

            if annotated is not None:
                color = TARGET_COLORS.get(label, (128, 128, 128))
                self.cv2.rectangle(annotated, (x, y), (x + box_w, y + box_h), color, 2)
                caption = f"{label} {conf:.0%}"
                (tw, th), _ = self.cv2.getTextSize(caption, self.cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                ty = max(th + 4, y - 4)
                self.cv2.rectangle(annotated, (x, ty - th - 4), (x + tw + 4, ty + 2), (0, 0, 0), -1)
                self.cv2.putText(annotated, caption, (x + 2, ty),
                                 self.cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, self.cv2.LINE_AA)

        del frame, enhanced

        label_set = set(labels)
        matched_target = bool(label_set & self.targets) if self.targets else bool(labels)

        annotated_photo = None
        if annotated is not None:
            ok, encoded = self.cv2.imencode(
                ".jpg", annotated,
                [int(self.cv2.IMWRITE_JPEG_QUALITY), 75],
            )
            if ok:
                annotated_photo = encoded.tobytes()
            del annotated, encoded

        gc.collect()

        return AiResult(
            labels=sorted(label_set),
            matched_target=matched_target,
            annotated_photo=annotated_photo,
            detections=raw_detections,
            behavior="",
        )


# ---------------------------------------------------------------------------
# Notification logic
# ---------------------------------------------------------------------------
def enrich_message(message, ai_result, behavior=""):
    parts = [message]
    if ai_result.labels:
        parts.append(f"IA: {', '.join(ai_result.labels[:5])}")
    else:
        parts.append("IA: aucune detection")
    if behavior and behavior != "inconnu":
        parts.append(f"Comportement: {behavior}")
    return " | ".join(parts)


def notify_once(config, message, detector, tracker=None, classifier=None):
    try:
        photo = capture_best_snapshot(config)
    except Exception as exc:
        print(f"[telegram] capture echouee ({exc})", file=sys.stderr)
        photo = None

    if not photo or len(photo) < config.min_jpeg_size:
        return send_message(config.token, config.chat_id, f"{message} | photo indisponible")

    payload = photo
    caption = message
    behavior = ""

    if detector.enabled:
        ai_result = detector.detect(photo)

        # Temporal tracker: only send if detection confirmed across N frames
        if tracker is not None and ai_result.detections:
            confirmed_tracks = tracker.update(ai_result.detections)

            # Update classifier with confirmed tracks
            if classifier is not None:
                for track in confirmed_tracks:
                    classifier.update(track.track_id, track.bbox)

            if not confirmed_tracks and config.tracker_enabled:
                # Detection not yet confirmed - skip sending
                n_unconfirmed = len([t for t in tracker._tracks if not t.confirmed])
                print(f"[telegram] tracker: {n_unconfirmed} detection(s) non confirmee(s), attente...")
                return True  # Don't count as failure

            # Get behavior for best confirmed track
            if classifier is not None and confirmed_tracks:
                best_track = max(confirmed_tracks, key=lambda t: t.confidence)
                behavior = classifier.classify(best_track.track_id)

        elif tracker is not None and not ai_result.detections:
            # No detections: still update tracker (increments missing counts)
            tracker.update([])

        caption = enrich_message(message, ai_result, behavior)

        if detector.require_target and not ai_result.matched_target:
            print("[telegram] IA: aucune classe cible, envoi ignore")
            return True

        if ai_result.annotated_photo:
            payload = ai_result.annotated_photo

    ok = send_photo(config.token, config.chat_id, payload, caption)
    if ok:
        return True

    print("[telegram] sendPhoto KO, fallback sendMessage", file=sys.stderr)
    return send_message(config.token, config.chat_id, caption)


def run_loop(config, message, detector, tracker=None, classifier=None):
    sent = 0
    modules = []
    if detector.enabled:
        modules.append("YOLOv8-nano")
    if config.clahe_enabled:
        modules.append("CLAHE")
    if tracker is not None:
        modules.append(f"Tracker({config.tracker_confirm_frames}f)")
    if classifier is not None:
        modules.append("Classifier")

    print(
        f"[telegram] loop start v2 interval={config.loop_interval_sec}s "
        f"max={config.loop_max_per_event} modules=[{', '.join(modules)}]"
    )

    while config.event_active_file.exists():
        try:
            ok = notify_once(config, message, detector, tracker, classifier)
            if ok:
                sent += 1
        except Exception as exc:
            print(f"[telegram] loop erreur: {exc}", file=sys.stderr)

        if config.loop_max_per_event > 0 and sent >= config.loop_max_per_event:
            break

        time.sleep(config.loop_interval_sec)

    print(f"[telegram] loop exit v2 sent={sent}")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--loop", action="store_true", help="Run until event file disappears")
    parser.add_argument("message", nargs="*", help="Custom alert message")
    args = parser.parse_args()

    message = " ".join(args.message).strip() if args.message else DEFAULT_MESSAGE

    try:
        config = load_config(CONFIG_PATH)
    except Exception as exc:
        print(f"[telegram] config erreur: {exc}", file=sys.stderr)
        return 1

    detector = YoloV8Detector(config)

    # Initialize tracker and classifier (state persists across loop iterations)
    tracker = None
    classifier = None
    if config.tracker_enabled and detector.enabled:
        tracker = TemporalTracker(
            confirm_frames=config.tracker_confirm_frames,
        )
        print(f"[telegram] tracker init (confirm={config.tracker_confirm_frames} frames)")
    if config.classifier_enabled and detector.enabled:
        classifier = ActivityClassifier()
        print("[telegram] classifier init (entry/exit/feeding/resting/transit)")

    if args.loop:
        return run_loop(config, message, detector, tracker, classifier)

    try:
        ok = notify_once(config, message, detector, tracker, classifier)
    except Exception as exc:
        print(f"[telegram] erreur: {exc}", file=sys.stderr)
        return 1

    if ok:
        print("[telegram] notification envoyee v2")
        return 0

    print("[telegram] echec envoi", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
