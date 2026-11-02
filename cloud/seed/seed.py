"""가짜 Pi: gateway 와 같은 형식(docs/03-contracts.md §6)으로 위반 1건을 올린다.
실행: docker compose --profile seed run --rm cloud-seed
"""
import io
import os
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]
BUCKET = os.getenv("SUPABASE_BUCKET", "violation-images")
SAMPLES_DIR = Path(os.getenv("SAMPLES_DIR", "/samples"))
DEVICE_ID = "seed-01"


def sample_image() -> bytes:
    files = sorted(SAMPLES_DIR.glob("*.jpg"))
    if files:
        return random.choice(files).read_bytes()
    img = Image.new("RGB", (640, 480), (90, 90, 90))
    ImageDraw.Draw(img).rectangle([200, 40, 420, 470], outline=(230, 40, 40), width=4)
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def main() -> None:
    client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
    now = datetime.now(timezone.utc)
    violation_id = str(uuid.uuid4())
    types = random.choice([["no_helmet"], ["no_vest"], ["no_helmet", "no_vest"]])
    image_path = f"{DEVICE_ID}/{now:%Y-%m-%d}/{violation_id}.jpg"

    client.storage.from_(BUCKET).upload(image_path, sample_image(),
                                        {"content-type": "image/jpeg", "upsert": "true"})
    row = {
        "id": violation_id,
        "captured_at": now.isoformat(),
        "device_id": DEVICE_ID,
        "gateway_id": "seed",
        "frame_seq": 0,
        "person_count": 1,
        "no_helmet_count": int("no_helmet" in types),
        "no_vest_count": int("no_vest" in types),
        "violation_types": types,
        "image_path": image_path,
        "image_w": 640,
        "image_h": 480,
        "persons": [{"box": [200, 40, 420, 470],
                     "helmet": "no_helmet" not in types, "vest": "no_vest" not in types}],
        "detections": [{"cls": "person", "score": 0.9, "box": [200, 40, 420, 470]}],
        "model": "seed",
        "infer_ms": 0,
    }
    client.table("violations").upsert(row).execute()
    print(f"[cloud-seed] inserted {violation_id} {types} → {image_path}")


if __name__ == "__main__":
    main()
