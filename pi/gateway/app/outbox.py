"""위반을 디스크에 먼저 저장하고 백그라운드로 Supabase 에 올린다 (docs/03-contracts.md §6.1).

/data/outbox/<violation_id>/image.jpg   박스 그린 사진
/data/outbox/<violation_id>/row.json    violations 행 (created_at 제외, shared/schemas/violation-row.schema.json)
/data/outbox/.tmp-<violation_id>/       쓰는 중 → 워커가 건너뜀, 시작 시 삭제
"""
from pathlib import Path

from .config import settings

RETRY_INTERVAL_S = 10
TMP_PREFIX = ".tmp-"


def enqueue(violation_id: str, image: bytes, row: dict) -> None:
    # TODO: .tmp-<id>/ 에 image.jpg, row.json 쓰고 <id>/ 로 rename
    pass


def cleanup_tmp() -> None:
    # TODO: 시작 시 남은 .tmp-* 폴더 삭제
    pass


def pending_count() -> int:
    root = Path(settings.outbox_dir)
    if not root.exists():
        return 0
    return sum(1 for p in root.iterdir() if p.is_dir() and not p.name.startswith(TMP_PREFIX))


async def run_worker() -> None:
    # TODO: 무한 루프 — 오래된 항목부터 1건씩 cloud.upload_violation()
    #       성공 → 폴더 삭제 / 실패 → RETRY_INTERVAL_S 후 같은 항목 재시도 (횟수 제한 없음)
    pass
