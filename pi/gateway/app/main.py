"""gateway API (docs/03-contracts.md §3).

POST /api/v1/frames     ESP32 → JPEG 1장 → 판정 결과 JSON
POST /api/v1/heartbeat  ESP32 상태 (2차)
GET  /healthz           사람이 curl 로 확인
"""
import re

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import settings

DEVICE_ID_RE = re.compile(r"^[a-z0-9-]{1,32}$")

app = FastAPI(title="edge-ppe-monitor gateway")


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
    # TODO: outbox 의 .tmp-* 정리 후 워커 시작 (outbox.cleanup_tmp, outbox.run_worker)
    pass


@app.get("/healthz")
async def healthz() -> dict:
    # TODO: detector_client.health() → "ready" | "not_ready" | "unreachable"
    detector = "unreachable"
    return {"v": 1, "ok": detector == "ready", "detector": detector, "outbox_pending": 0,
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

    # TODO (03 §3~§6):
    #   0) Pillow 로 디코드 확인 → 실패 시 400 invalid_image
    #   1) captured_at = X-Captured-At 파싱, 없거나 형식 오류면 수신 시각(UTC)
    #   2) detector_client.detect(image)  → InvalidImage 면 400, DetectorUnavailable 이면 503
    #   3) judge.judge(detections, settings.unknown_as_violation)
    #   4) violation 이면:  CLOUD_ENABLED=false → cloud="disabled"
    #                       cooldown.should_upload() False → "duplicate"
    #                       True → id=uuid4, annotate.draw → outbox.enqueue → "queued", violation_id=id
    #   5) violation_id 는 queued 일 때만, 나머지 null
    return {"v": 1, "frame_seq": x_frame_seq, "result": "no_person", "persons": 0,
            "violations": [], "violation_id": None, "cloud": "none", "infer_ms": 0}


@app.post("/api/v1/heartbeat")
async def post_heartbeat(payload: dict, x_device_key: str = Header(...)):
    if x_device_key != settings.device_api_key:
        return error(401, "bad_device_key")
    # TODO (2차): device_id 정규식·uptime_s 검사 → 400 invalid_heartbeat
    #             CLOUD_ENABLED 면 cloud.upsert_device(payload) (실패는 로그만, outbox X)
    return {"v": 1, "ok": True}
