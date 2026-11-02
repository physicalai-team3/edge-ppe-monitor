"""환경 변수 → 설정 (docs/02-containers.md §4)."""
import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class Settings:
    detector_url: str = os.getenv("DETECTOR_URL", "http://detector:9000")
    detector_timeout_s: float = 4.0          # ESP32 타임아웃(5초) 안에 503 을 돌려주기 위해 (03 §3.4)
    device_api_key: str = os.getenv("DEVICE_API_KEY", "change-me")
    gateway_id: str = os.getenv("GATEWAY_ID", "pi-01")
    violation_cooldown_s: int = int(os.getenv("VIOLATION_COOLDOWN_S", "30"))
    unknown_as_violation: bool = _bool("JUDGE_UNKNOWN_AS_VIOLATION", True)
    cloud_enabled: bool = _bool("CLOUD_ENABLED", True)
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_secret_key: str = os.getenv("SUPABASE_SECRET_KEY", "")
    supabase_bucket: str = os.getenv("SUPABASE_BUCKET", "violation-images")
    outbox_dir: str = os.getenv("OUTBOX_DIR", "/data/outbox")
    max_image_bytes: int = 512 * 1024


settings = Settings()
