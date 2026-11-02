"""detector 컨테이너 호출 (docs/03-contracts.md §4)."""
import httpx

from .config import settings


class DetectorUnavailable(Exception):
    """연결 실패, 4초 타임아웃, detector 503 → gateway 503 detector_unavailable."""


class InvalidImage(Exception):
    """detector 400 → gateway 400 invalid_image."""


async def detect(image: bytes) -> dict:
    """JPEG → {"v","model","infer_ms","image_w","image_h","detections":[{cls,score,box}]}"""
    try:
        async with httpx.AsyncClient(timeout=settings.detector_timeout_s) as client:
            r = await client.post(f"{settings.detector_url}/v1/detect", content=image,
                                  headers={"Content-Type": "image/jpeg"})
    except httpx.TimeoutException:
        raise DetectorUnavailable("timeout")
    except httpx.HTTPError as e:
        raise DetectorUnavailable(type(e).__name__)

    if r.status_code == 400:
        raise InvalidImage(r.json().get("detail", ""))
    if r.status_code != 200:
        raise DetectorUnavailable(f"detector {r.status_code}")
    return r.json()


async def health() -> str:
    """"ready" | "not_ready" | "unreachable" (03 §3.7)"""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{settings.detector_url}/healthz")
        return "ready" if r.json().get("ready") else "not_ready"
    except (httpx.HTTPError, ValueError):
        return "unreachable"
