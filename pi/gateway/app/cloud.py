"""Supabase 업로드 (docs/03-contracts.md §6). secret 키는 이 컨테이너에만 있다."""
from .config import settings


def upload_violation(image: bytes, row: dict) -> None:
    """1) Storage <bucket>/<row.image_path> 업로드 (upsert) — 사진 먼저
    2) violations upsert (id 기준) — 재시도해도 중복 없음
    실패하면 예외 → outbox 가 재시도."""
    # TODO: supabase.create_client(settings.supabase_url, settings.supabase_secret_key)
    #   .storage.from_(bucket).upload(path, image, {"content-type": "image/jpeg", "upsert": "true"})
    #   .table("violations").upsert(row).execute()
    raise NotImplementedError


def upsert_device(heartbeat: dict) -> None:
    """(2차) devices upsert (03 §6.4): last_seen = 지금(UTC), gateway_id = GATEWAY_ID, frames_sent 는 저장 안 함."""
    raise NotImplementedError
