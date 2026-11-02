"""gateway API (docs/03-contracts.md §3).

POST /api/v1/frames     ESP32 → JPEG 1장 → 판정 결과 JSON
POST /api/v1/heartbeat  ESP32 상태 (2차)
GET  /healthz           사람이 curl 로 확인
"""
import asyncio
import io
import re
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from PIL import Image

from . import annotate, cloud, detector_client, outbox
from .config import settings
from .dedup import Cooldown
from .judge import judge

DEVICE_ID_RE = re.compile(r"^[a-z0-9-]{1,32}$")

app = FastAPI(title="edge-ppe-monitor gateway")
cooldown = Cooldown(settings.violation_cooldown_s)


def is_jpeg(image: bytes) -> bool:
    try:
        with Image.open(io.BytesIO(image)) as im:
            im.verify()
            return im.format == "JPEG"
    except Exception:
        return False


def parse_captured_at(value: str | None) -> datetime:
    """X-Captured-At (UTC, 끝이 Z) → datetime. 없거나 형식 오류면 수신 시각 (03 §3.1)."""
    if value and value.endswith("Z"):
        try:
            return datetime.fromisoformat(value).astimezone(timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def iso_utc(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def error(status: int, code: str, detail: str = "") -> JSONResponse:
    """에러 body 는 항상 shared/schemas/error.schema.json 형식."""
    return JSONResponse(status_code=status, content={"v": 1, "error": code, "detail": detail})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI 기본 422 → 계약상 400 (03 §3.3)
    code = "invalid_heartbeat" if request.url.path.endswith("/heartbeat") else "missing_header"
    return error(400, code, str(exc.errors()[:1]))


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception) -> JSONResponse:
    return error(500, "internal_error", type(exc).__name__)


@app.on_event("startup")
async def startup() -> None:
    outbox.cleanup_tmp()
    if settings.cloud_enabled:
        app.state.worker = asyncio.create_task(outbox.run_worker())


@app.get("/healthz")
async def healthz() -> dict:
    detector = await detector_client.health()
    return {"v": 1, "ok": detector == "ready", "detector": detector, "outbox_pending": outbox.pending_count(),
            "cloud": "enabled" if settings.cloud_enabled else "disabled"}


@app.post("/api/v1/frames")
async def post_frame(
    request: Request,
    content_type: str = Header(...),
    x_device_id: str = Header(...),
    x_device_key: str = Header(...),
    x_frame_seq: int = Header(..., ge=0),
    x_person_count: int = Header(..., ge=0, le=255),
    x_person_score: float = Header(..., ge=0, le=1),
    x_captured_at: str | None = Header(None),
    x_fw_version: str | None = Header(None),
):
    # 검사 순서: 401 → 400(device_id) → 415 → 413 → 400(image)
    if x_device_key != settings.device_api_key:
        return error(401, "bad_device_key")
    if not DEVICE_ID_RE.match(x_device_id):
        return error(400, "bad_device_id", x_device_id)
    if not content_type.startswith("image/jpeg"):
        return error(415, "unsupported_media_type", content_type)
    image = await request.body()
    if len(image) > settings.max_image_bytes:
        return error(413, "image_too_large", str(len(image)))
    if not image:
        return error(400, "invalid_image", "empty body")
    if not is_jpeg(image):
        return error(400, "invalid_image", "not a jpeg")
    captured_at = parse_captured_at(x_captured_at)

    try:
        det = await detector_client.detect(image)
    except detector_client.InvalidImage as e:
        return error(400, "invalid_image", str(e))
    except detector_client.DetectorUnavailable as e:
        return error(503, "detector_unavailable", str(e))

    j = judge(det["detections"], settings.unknown_as_violation)

    cloud, violation_id = "none", None
    if j.result == "violation":
        if not settings.cloud_enabled:
            cloud = "disabled"
        elif not cooldown.should_upload(x_device_id, j.violations):
            cloud = "duplicate"
        else:
            violation_id = str(uuid.uuid4())
            row = {
                "id": violation_id,
                "captured_at": iso_utc(captured_at),
                "device_id": x_device_id,
                "gateway_id": settings.gateway_id,
                "frame_seq": x_frame_seq,
                "person_count": len(j.persons),
                "no_helmet_count": j.no_helmet_count,
                "no_vest_count": j.no_vest_count,
                "violation_types": j.violations,
                "image_path": f"{x_device_id}/{captured_at:%Y-%m-%d}/{violation_id}.jpg",
                "image_w": det.get("image_w"),
                "image_h": det.get("image_h"),
                "persons": [asdict(p) for p in j.persons],
                "detections": det["detections"],
                "model": det.get("model"),
                "infer_ms": det.get("infer_ms"),
            }
            outbox.enqueue(violation_id, annotate.draw(image, det["detections"], j), row)
            cloud = "queued"

    return {"v": 1, "frame_seq": x_frame_seq, "result": j.result, "persons": len(j.persons),
            "violations": j.violations, "violation_id": violation_id, "cloud": cloud,
            "infer_ms": det.get("infer_ms", 0)}


@app.post("/api/v1/heartbeat")
async def post_heartbeat(payload: dict, x_device_key: str = Header(...)):
    if x_device_key != settings.device_api_key:
        return error(401, "bad_device_key")
    device_id, uptime_s = payload.get("device_id"), payload.get("uptime_s")
    if not isinstance(device_id, str) or not DEVICE_ID_RE.match(device_id):
        return error(400, "invalid_heartbeat", "device_id")
    if not isinstance(uptime_s, int) or isinstance(uptime_s, bool) or uptime_s < 0:
        return error(400, "invalid_heartbeat", "uptime_s")
    if settings.cloud_enabled:
        try:
            await asyncio.to_thread(cloud.upsert_device, payload)
        except Exception as e:
            print(f"[heartbeat] devices upsert failed: {type(e).__name__}: {e}")
    return {"v": 1, "ok": True}
