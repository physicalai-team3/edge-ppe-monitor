"""YOLOv8 ONNX 추론 / mock (docs/03-contracts.md §4.1).

detect(jpeg) → {"model","infer_ms","image_w","image_h","detections":[{cls,score,box}]}
- cls: 표준 이름 5개만 (labels.yaml 의 map 으로 변환, 나머지 클래스는 버림)
- score: CONF_THRESHOLD 이상, 소수 셋째 자리
- box: 원본 이미지 픽셀 정수 [x1,y1,x2,y2], 이미지 범위로 잘라냄, 클래스별 NMS 적용
- detections: 점수 내림차순
"""
from pathlib import Path

import yaml

LABELS = yaml.safe_load((Path(__file__).parent / "labels.yaml").read_text(encoding="utf-8"))


class InvalidImage(Exception):
    """빈 body, JPEG 디코드 실패 → 400 invalid_image."""


class MockDetector:
    """모델 파일 없이 gateway 를 개발하기 위한 고정 결과: 사람 1명 + no_helmet + vest → 항상 violation."""
    mode = "mock"
    name = "mock"
    ready = True

    def detect(self, image: bytes) -> dict:
        # TODO: Pillow 로 디코드해 크기를 읽고, 실패하면 InvalidImage (실제 모드와 같은 동작)
        if not image:
            raise InvalidImage("empty body")
        return {"model": self.name, "infer_ms": 0, "image_w": 640, "image_h": 480,
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
        # TODO: onnxruntime.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        #       입력 크기(640), 모델 클래스 이름(ONNX 메타데이터 names → 없으면 labels.yaml model_classes)
        #       성공하면 ready = True. 실패해도 예외로 죽지 말고 로그만 (healthz 가 ready:false)

    def detect(self, image: bytes) -> dict:
        # TODO: JPEG 디코드(실패 → InvalidImage) → letterbox 640 → 추론 → 출력 [1, 4+nc, 8400] 디코드
        #       → conf 필터 → 클래스별 NMS → 원본 좌표로 되돌리고 정수·범위 클립 → LABELS["map"] 변환
        raise NotImplementedError


def load_detector(mode: str, model_path: str, conf: float, iou: float):
    if mode == "mock":
        return MockDetector()
    return OnnxDetector(model_path, conf, iou)
