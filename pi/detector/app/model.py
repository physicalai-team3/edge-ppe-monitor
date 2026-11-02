"""YOLOv8 ONNX 추론 / mock (docs/03-contracts.md §4.1).

detect(jpeg) → {"model","infer_ms","image_w","image_h","detections":[{cls,score,box}]}
- cls: 표준 이름 5개만 (labels.yaml 의 map 으로 변환, 나머지 클래스는 버림)
- score: CONF_THRESHOLD 이상, 소수 셋째 자리
- box: 원본 이미지 픽셀 정수 [x1,y1,x2,y2], 이미지 범위로 잘라냄, 클래스별 NMS 적용
- detections: 점수 내림차순
"""
import ast
import io
import time
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

LABELS = yaml.safe_load((Path(__file__).parent / "labels.yaml").read_text(encoding="utf-8"))
PAD_COLOR = (114, 114, 114)   # ultralytics letterbox 회색


class InvalidImage(Exception):
    """빈 body, JPEG 디코드 실패 → 400 invalid_image."""


def decode(image: bytes) -> Image.Image:
    if not image:
        raise InvalidImage("empty body")
    try:
        return Image.open(io.BytesIO(image)).convert("RGB")
    except Exception as e:
        raise InvalidImage(type(e).__name__)


def letterbox(img: Image.Image, size: int) -> tuple[np.ndarray, float, tuple[int, int]]:
    """비율 유지 축소 + 회색 여백 → (1,3,size,size) float32, 배율, (왼쪽, 위) 여백."""
    w, h = img.size
    r = min(size / w, size / h)
    nw, nh = round(w * r), round(h * r)
    left, top = (size - nw) // 2, (size - nh) // 2
    canvas = Image.new("RGB", (size, size), PAD_COLOR)
    canvas.paste(img.resize((nw, nh), Image.BILINEAR), (left, top))
    x = np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1)[None] / 255.0
    return x, r, (left, top)


def nms(boxes: np.ndarray, scores: np.ndarray, iou: float) -> list[int]:
    """boxes [N,4] xyxy → 남길 인덱스 (점수 높은 순)."""
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = order[0]
        keep.append(int(i))
        rest = order[1:]
        xx1 = np.maximum(boxes[i, 0], boxes[rest, 0])
        yy1 = np.maximum(boxes[i, 1], boxes[rest, 1])
        xx2 = np.minimum(boxes[i, 2], boxes[rest, 2])
        yy2 = np.minimum(boxes[i, 3], boxes[rest, 3])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        area = lambda b: (b[..., 2] - b[..., 0]) * (b[..., 3] - b[..., 1])
        overlap = inter / (area(boxes[i]) + area(boxes[rest]) - inter + 1e-9)
        order = rest[overlap <= iou]
    return keep


class MockDetector:
    """모델 파일 없이 gateway 를 개발하기 위한 고정 결과: 사람 1명 + no_helmet + vest → 항상 violation."""
    mode = "mock"
    name = "mock"
    ready = True

    def detect(self, image: bytes) -> dict:
        w, h = decode(image).size
        return {"model": self.name, "infer_ms": 0, "image_w": w, "image_h": h,
                "detections": [
                    {"cls": "person", "score": 0.9, "box": [200, 40, 420, 470]},
                    {"cls": "no_helmet", "score": 0.8, "box": [270, 45, 350, 120]},
                    {"cls": "vest", "score": 0.8, "box": [220, 150, 400, 330]},
                ]}


class OnnxDetector:
    mode = "onnx"

    def __init__(self, model_path: str, conf: float, iou: float):
        self.name = Path(model_path).stem   # ppe.onnx → "ppe"
        self.conf = conf
        self.iou = iou
        self.ready = False
        try:
            import onnxruntime
            self.session = onnxruntime.InferenceSession(model_path, providers=["CPUExecutionProvider"])
            inp = self.session.get_inputs()[0]
            self.input_name = inp.name
            self.size = inp.shape[2] if isinstance(inp.shape[2], int) else 640
            meta = self.session.get_modelmeta().custom_metadata_map
            names = ast.literal_eval(meta["names"]) if "names" in meta else dict(enumerate(LABELS["model_classes"]))
            # 모델 클래스 번호 → 표준 이름 (map 에 없으면 None → 버림)
            self.std = {int(i): LABELS["map"].get(n) for i, n in names.items()}
            self.ready = True
            print(f"model loaded: {model_path} input={self.size} classes={len(names)}")
        except Exception as e:
            print(f"model load failed: {model_path}: {e}")

    def detect(self, image: bytes) -> dict:
        img = decode(image)
        w, h = img.size
        x, r, (left, top) = letterbox(img, self.size)

        t0 = time.perf_counter()
        out = self.session.run(None, {self.input_name: x})[0][0].T   # [8400, 4+nc]
        infer_ms = round((time.perf_counter() - t0) * 1000)

        cls_scores = out[:, 4:]
        cls_ids = cls_scores.argmax(1)
        scores = cls_scores[np.arange(len(out)), cls_ids]
        keep = scores >= self.conf
        cx, cy, bw, bh = out[keep, :4].T
        cls_ids, scores = cls_ids[keep], scores[keep]

        # letterbox 좌표 → 원본 픽셀
        boxes = np.stack([cx - bw / 2 - left, cy - bh / 2 - top, cx + bw / 2 - left, cy + bh / 2 - top], 1) / r
        boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, w)
        boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, h)

        detections = []
        for c in np.unique(cls_ids):
            name = self.std.get(int(c))
            if name is None:
                continue
            idx = np.where(cls_ids == c)[0]
            for i in idx[nms(boxes[idx], scores[idx], self.iou)]:
                detections.append({"cls": name, "score": round(float(scores[i]), 3),
                                   "box": [int(round(v)) for v in boxes[i]]})
        detections.sort(key=lambda d: d["score"], reverse=True)
        return {"model": self.name, "infer_ms": infer_ms, "image_w": w, "image_h": h, "detections": detections}


def load_detector(mode: str, model_path: str, conf: float, iou: float):
    if mode == "mock":
        return MockDetector()
    return OnnxDetector(model_path, conf, iou)
