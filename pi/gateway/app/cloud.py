"""Supabase 업로드 (docs/03-contracts.md §6). secret 키는 이 컨테이너에만 있다."""
from datetime import datetime, timezone

from .config import settings

_client = None


def client():
    """처음 쓸 때 한 번만 연결 (키가 없으면 여기서 예외 → outbox 가 재시도)."""
    global _client
    if _client is None:
        if not settings.supabase_url or not settings.supabase_secret_key:
            raise RuntimeError("SUPABASE_URL / SUPABASE_SECRET_KEY 가 비어 있음")
        from supabase import create_client
        _client = create_client(settings.supabase_url, settings.supabase_secret_key)
    return _client


def upload_violation(image: bytes, row: dict) -> None:
    """1) Storage <bucket>/<row.image_path> 업로드 (upsert) — 사진 먼저
    2) violations upsert (id 기준) — 재시도해도 중복 없음
    실패하면 예외 → outbox 가 재시도."""
    c = client()
    c.storage.from_(settings.supabase_bucket).upload(
        row["image_path"], image, {"content-type": "image/jpeg", "upsert": "true"})
    c.table("violations").upsert(row).execute()


def upsert_device(heartbeat: dict) -> None:
    """(2차) devices upsert (03 §6.4): last_seen = 지금(UTC), gateway_id = GATEWAY_ID, frames_sent 는 저장 안 함."""
    row = {k: heartbeat.get(k) for k in ("device_id", "fw_version", "rssi", "uptime_s", "free_heap", "last_error")}
    row["gateway_id"] = settings.gateway_id
    row["last_seen"] = datetime.now(timezone.utc).isoformat()
    client().table("devices").upsert(row).execute()
