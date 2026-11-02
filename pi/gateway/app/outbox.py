"""위반을 디스크에 먼저 저장하고 백그라운드로 Supabase 에 올린다 (docs/03-contracts.md §6.1).

/data/outbox/<violation_id>/image.jpg   박스 그린 사진
/data/outbox/<violation_id>/row.json    violations 행 (created_at 제외, shared/schemas/violation-row.schema.json)
/data/outbox/.tmp-<violation_id>/       쓰는 중 → 워커가 건너뜀, 시작 시 삭제
"""
import asyncio
import json
import shutil
from pathlib import Path

from . import cloud
from .config import settings

RETRY_INTERVAL_S = 10
IDLE_POLL_S = 1
TMP_PREFIX = ".tmp-"


def enqueue(violation_id: str, image: bytes, row: dict) -> None:
    root = Path(settings.outbox_dir)
    tmp = root / f"{TMP_PREFIX}{violation_id}"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "image.jpg").write_bytes(image)
    (tmp / "row.json").write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
    tmp.rename(root / violation_id)   # 다 쓴 뒤에 이름을 바꿔야 워커가 반쯤 쓴 폴더를 읽지 않는다


def cleanup_tmp() -> None:
    root = Path(settings.outbox_dir)
    if root.exists():
        for p in root.glob(f"{TMP_PREFIX}*"):
            shutil.rmtree(p, ignore_errors=True)


def pending_count() -> int:
    root = Path(settings.outbox_dir)
    if not root.exists():
        return 0
    return sum(1 for p in root.iterdir() if p.is_dir() and not p.name.startswith(TMP_PREFIX))


def _oldest() -> Path | None:
    root = Path(settings.outbox_dir)
    if not root.exists():
        return None
    items = [p for p in root.iterdir() if p.is_dir() and not p.name.startswith(TMP_PREFIX)]
    return min(items, key=lambda p: p.stat().st_mtime) if items else None


async def run_worker() -> None:
    """오래된 항목부터 1건씩 업로드. 성공 → 폴더 삭제 / 실패 → RETRY_INTERVAL_S 후 같은 항목 재시도 (횟수 제한 없음)."""
    while True:
        item = _oldest()
        if item is None:
            await asyncio.sleep(IDLE_POLL_S)
            continue
        try:
            image = (item / "image.jpg").read_bytes()
            row = json.loads((item / "row.json").read_text(encoding="utf-8"))
            await asyncio.to_thread(cloud.upload_violation, image, row)   # supabase-py 는 동기 → 스레드로
            shutil.rmtree(item, ignore_errors=True)
            print(f"[outbox] uploaded {item.name}")
        except Exception as e:
            print(f"[outbox] upload failed {item.name}: {type(e).__name__}: {e} → {RETRY_INTERVAL_S}s 후 재시도")
            await asyncio.sleep(RETRY_INTERVAL_S)
