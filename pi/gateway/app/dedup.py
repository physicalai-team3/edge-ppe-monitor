"""같은 위반 반복 업로드 방지 (docs/03-contracts.md §5.4). 메모리에만 저장 (재시작 시 초기화)."""
import time


class Cooldown:
    def __init__(self, seconds: int):
        self.seconds = seconds
        self._last_upload: dict[tuple[str, tuple[str, ...]], float] = {}

    def should_upload(self, device_id: str, violations: list[str], now: float | None = None) -> bool:
        """키 (device_id, violations) 가 마지막 업로드 후 seconds 안이면 False.
        True 를 반환할 때만 시각을 기록한다 (duplicate 는 타이머를 다시 시작하지 않음)."""
        now = time.monotonic() if now is None else now
        key = (device_id, tuple(violations))
        last = self._last_upload.get(key)
        if last is not None and now - last < self.seconds:
            return False
        self._last_upload[key] = now
        return True
