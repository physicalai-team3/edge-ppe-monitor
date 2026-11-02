"""detector API (docs/03-contracts.md §4). compose 내부망 전용."""
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .model import InvalidImage, load_detector

app = FastAPI(title="edge-ppe-monitor detector")
detector = load_detector(
    mode=os.getenv("DETECTOR_MODE", "onnx"),
    model_path=os.getenv("MODEL_PATH", "/models/ppe.onnx"),
    conf=float(os.getenv("CONF_THRESHOLD", "0.4")),
    iou=float(os.getenv("IOU_THRESHOLD", "0.5")),
)


def error(status: int, code: str, detail: str = "") -> JSONResponse:
    return JSONResponse(status_code=status, content={"v": 1, "error": code, "detail": detail})


@app.get("/healthz")
def healthz() -> dict:
    # 모델 로드에 실패해도 200 (ready:false) — 원인은 로그로 확인 (03 §4.3)
    return {"v": 1, "ready": detector.ready, "mode": detector.mode, "model": detector.name,
            "classes": ["person", "helmet", "no_helmet", "vest", "no_vest"]}


@app.post("/v1/detect")
async def detect(request: Request):
    if not detector.ready:
        return error(503, "model_not_ready", detector.name)
    image = await request.body()
    try:
        return {"v": 1, **detector.detect(image)}
    except InvalidImage as e:
        return error(400, "invalid_image", str(e))
