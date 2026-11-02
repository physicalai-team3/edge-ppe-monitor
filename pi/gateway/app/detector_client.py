"""detector 컨테이너 호출 (docs/03-contracts.md §4)."""
import httpx

from .config import settings


class DetectorUnavailable(Exception):
    """연결 실패, 4초 타임아웃, detector 503 → gateway 503 detector_unavailable."""


class InvalidImage(Exception):
    """detector 400 → gateway 400 invalid_image."""


async def detect(image: bytes) -> dict:
    """JPEG → {"v","model","infer_ms","image_w","image_h","detections":[{cls,score,box}]}"""
    # TODO: POST {settings.detector_url}/v1/detect (Content-Type: image/jpeg),
    #       timeout=settings.detector_timeout_s. 400 → InvalidImage, 503/연결 실패/타임아웃 → DetectorUnavailable
    raise DetectorUnavailable("not implemented")


async def health() -> str:
    """"ready" | "not_ready" | "unreachable" (03 §3.7)"""
    # TODO: GET /healthz → ready 값
    return "unreachable"
