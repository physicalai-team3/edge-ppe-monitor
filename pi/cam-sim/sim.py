"""가짜 ESP32 (docs/03-contracts.md §3). 샘플 사진을 INTERVAL_S 마다 돌아가며 전송한다."""
import io
import itertools
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from PIL import Image

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8000")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "change-me")
DEVICE_ID = os.getenv("DEVICE_ID", "sim-01")
INTERVAL_S = float(os.getenv("INTERVAL_S", "3"))
SAMPLES_DIR = Path(os.getenv("SAMPLES_DIR", "/samples"))


def load_samples() -> list[tuple[str, bytes]]:
    files = sorted(SAMPLES_DIR.glob("*.jpg"))
    if files:
        return [(f.name, f.read_bytes()) for f in files]
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (128, 128, 128)).save(buf, "JPEG")
    return [("dummy-gray", buf.getvalue())]


def main() -> None:
    samples = load_samples()
    print(f"[cam-sim] {len(samples)} sample(s) → {GATEWAY_URL} as {DEVICE_ID}")
    for seq, (name, jpeg) in enumerate(itertools.cycle(samples)):
        headers = {
            "Content-Type": "image/jpeg",
            "X-Device-Id": DEVICE_ID,
            "X-Device-Key": DEVICE_API_KEY,
            "X-Frame-Seq": str(seq),
            "X-Person-Count": "1",
            "X-Person-Score": "0.90",
            "X-Captured-At": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "X-Fw-Version": "sim",
        }
        try:
            r = httpx.post(f"{GATEWAY_URL}/api/v1/frames", content=jpeg, headers=headers, timeout=5)
            print(f"[cam-sim] seq={seq} {name} → {r.status_code} {r.text}")
        except httpx.HTTPError as e:
            print(f"[cam-sim] seq={seq} {name} → error {e!r}")
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    main()
