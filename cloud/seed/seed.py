"""가짜 Pi: gateway 와 같은 형식(docs/03-contracts.md §6)으로 Supabase 에 위반을 올린다.

웹(팀원 4)은 이 데이터와 실제 gateway 데이터를 구분하지 않는다. device_id 가 seed-* 인 것만 다르다.

실행 (컨테이너):  docker compose --profile seed run --rm cloud-seed python seed.py <시나리오> [N]
실행 (로컬):      python seed.py <시나리오> [N] [--dry-run]

시나리오 (03 §6 의 실제 상황을 흉내낸다)
  one          위반 1건 (기본)
  types        no_helmet / no_vest / 둘 다 / 2명 중 1명 위반
  burst [N]    N건(기본 10)을 1초 간격, 장치 2개 — outbox 가 밀린 위반을 한꺼번에 올림
  retry        같은 id 로 2번 upsert — outbox 재시도 (카드 1개여야 함)
  late         captured_at 이 3분 전인 위반 — outbox 가 늦게 올림
  edges        KST 어제 23:59, 오늘 00:01 — 오늘 통계 경계
  noimage      행만 올리고 사진은 안 올림 — "사진 없음" 표시
  devices      devices 2행: seed-01 방금, seed-02 5분 전 (2차)
  live [S]     S초(기본 30)마다 위반 1건, Ctrl+C 로 멈춤 — 데모 리허설
  clean        seed-* 행·사진·장치 삭제

--dry-run: Supabase 대신 cloud/seed/.out/ 에 사진과 rows.jsonl 을 쓴다 (키 없이 확인).
모든 행은 올리기 전에 shared/schemas/violation-row.schema.json 과 계약 규칙으로 검사한다.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import random
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1] if len(HERE.parents) > 1 else HERE   # 컨테이너(/srv)에서는 쓰지 않음
KST = timezone(timedelta(hours=9))

DEVICES = ("seed-01", "seed-02")   # 실제 장치(xiao-*, sim-01)와 섞이지 않게 seed-* 만 쓴다
GATEWAY_ID = "seed"
VIOLATION_ORDER = ("no_helmet", "no_vest")          # 03 §1.3
DEVICE_ID_RE = re.compile(r"^[a-z0-9-]{1,32}$")      # 03 §1.1
IMAGE_W, IMAGE_H = 640, 480
COLOR_VIOLATOR = "#E5484D"   # 03 §6.2 — gateway annotate.py 와 같은 색
COLOR_OK = "#30A46C"

# 사람 박스 배치 (640x480 기준)
ONE = [[200, 40, 420, 470]]
TWO = [[60, 60, 260, 470], [360, 50, 580, 470]]


def load_env_file() -> None:
    """로컬 실행용: 루트 .env 의 값을 아직 없는 환경 변수에만 채운다 (python-dotenv 없이)."""
    env = REPO / ".env"
    if not env.is_file():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _dir(env_name: str, container_path: str, repo_path: str) -> Path:
    if os.getenv(env_name):
        return Path(os.environ[env_name])
    if Path(container_path).is_dir():
        return Path(container_path)
    return REPO / repo_path


# ── 행 만들기 (03 §6.3) ─────────────────────────────────────

def iso_utc(dt: datetime) -> str:
    """03 §1.1: ISO 8601 UTC, 끝은 Z, 밀리초."""
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def person(box: list[int], helmet: bool = True, vest: bool = True) -> dict:
    return {"box": box, "helmet": helmet, "vest": vest}


def detections_for(persons: list[dict]) -> list[dict]:
    """persons 와 모순되지 않는 detector 결과 (03 §4.1): 머리·몸통 영역 안에 보호구 박스, 점수 내림차순."""
    dets = []
    for p in persons:
        x1, y1, x2, y2 = p["box"]
        h, cx = y2 - y1, (x1 + x2) // 2
        head = [cx - 35, y1 + 5, cx + 35, y1 + int(0.25 * h)]
        torso = [x1 + 15, y1 + int(0.30 * h), x2 - 15, y1 + int(0.65 * h)]
        dets.append({"cls": "person", "score": round(random.uniform(0.85, 0.95), 3), "box": p["box"]})
        dets.append({"cls": "helmet" if p["helmet"] else "no_helmet",
                     "score": round(random.uniform(0.6, 0.85), 3), "box": head})
        dets.append({"cls": "vest" if p["vest"] else "no_vest",
                     "score": round(random.uniform(0.6, 0.85), 3), "box": torso})
    return sorted(dets, key=lambda d: d["score"], reverse=True)


def build_row(device_id: str, captured_at: datetime, persons: list[dict], frame_seq: int | None = None,
              violation_id: str | None = None) -> dict:
    """gateway 가 outbox 에 쓰는 row.json 과 같은 모양. 개수·종류는 persons 에서 계산한다 (직접 적지 않음)."""
    persons = sorted(persons, key=lambda p: p["box"][0])          # 03 §5.3 x1 오름차순
    types = [t for t in VIOLATION_ORDER
             if any(not p["helmet"] if t == "no_helmet" else not p["vest"] for p in persons)]
    vid = violation_id or str(uuid.uuid4())
    return {
        "id": vid,
        "captured_at": iso_utc(captured_at),
        "device_id": device_id,
        "gateway_id": GATEWAY_ID,
        "frame_seq": frame_seq,
        "person_count": len(persons),
        "no_helmet_count": sum(not p["helmet"] for p in persons),
        "no_vest_count": sum(not p["vest"] for p in persons),
        "violation_types": types,
        "image_path": f"{device_id}/{captured_at.astimezone(timezone.utc):%Y-%m-%d}/{vid}.jpg",
        "image_w": IMAGE_W,
        "image_h": IMAGE_H,
        "persons": persons,
        "detections": detections_for(persons),
        "model": "seed",
        "infer_ms": random.randint(150, 250),
    }


# ── 검사 ────────────────────────────────────────────────────

class ContractError(ValueError):
    pass


def make_validator(schemas_dir: Path):
    """violation-row 스키마 검사기 ($ref 로 detect-response 를 참조)."""
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    schemas = [json.loads(p.read_text(encoding="utf-8")) for p in schemas_dir.glob("*.schema.json")]
    registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas)
    row_schema = next(s for s in schemas if s["$id"] == "violation-row.schema.json")
    return Draft202012Validator(row_schema, registry=registry,
                                format_checker=Draft202012Validator.FORMAT_CHECKER)


def check_row(row: dict, validator) -> None:
    """스키마 + 스키마로 표현 못 하는 계약 규칙(03 §1.3, §6.2, §6.3)."""
    errors = sorted(validator.iter_errors(row), key=lambda e: list(e.path))
    if errors:
        raise ContractError("; ".join(f"{list(e.path)}: {e.message}" for e in errors[:3]))
    persons = row["persons"]
    problems = []
    if row["violation_types"] != [t for t in VIOLATION_ORDER if t in row["violation_types"]]:
        problems.append("violation_types 순서는 no_helmet, no_vest")
    if row["person_count"] != len(persons):
        problems.append("person_count != len(persons)")
    if row["no_helmet_count"] != sum(not p["helmet"] for p in persons):
        problems.append("no_helmet_count 가 persons 와 다름")
    if row["no_vest_count"] != sum(not p["vest"] for p in persons):
        problems.append("no_vest_count 가 persons 와 다름")
    if [p["box"][0] for p in persons] != sorted(p["box"][0] for p in persons):
        problems.append("persons 는 x1 오름차순")
    if not row["captured_at"].endswith("Z"):
        problems.append("captured_at 은 Z 로 끝나는 UTC")
    utc_day = datetime.fromisoformat(row["captured_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
    if row["image_path"] != f"{row['device_id']}/{utc_day}/{row['id']}.jpg":
        problems.append("image_path 는 <device_id>/<captured_at UTC 날짜>/<id>.jpg")
    if "created_at" in row:
        problems.append("created_at 은 DB 가 채운다")
    if problems:
        raise ContractError("; ".join(problems))


# ── 사진 (03 §6.2) ──────────────────────────────────────────

def annotated_jpeg(samples_dir: Path, row: dict) -> bytes:
    """샘플 사진(없으면 회색) 위에 gateway 처럼 박스를 그린 JPEG."""
    files = sorted(samples_dir.glob("*.jpg")) if samples_dir.is_dir() else []
    if files:
        img = Image.open(random.choice(files)).convert("RGB").resize((IMAGE_W, IMAGE_H))
    else:
        img = Image.new("RGB", (IMAGE_W, IMAGE_H), (90, 90, 90))
    draw = ImageDraw.Draw(img)
    for p in row["persons"]:
        ok = p["helmet"] and p["vest"]
        draw.rectangle(p["box"], outline=COLOR_OK if ok else COLOR_VIOLATOR, width=3)
    for d in row["detections"]:
        if d["cls"] == "person":
            continue
        color = COLOR_VIOLATOR if d["cls"].startswith("no_") else COLOR_OK
        draw.rectangle(d["box"], outline=color, width=1)
        draw.text((d["box"][0] + 2, d["box"][1] + 2), f"{d['cls']} {d['score']:.2f}", fill=color)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


# ── 저장소 (Supabase 또는 dry-run 폴더) ─────────────────────

class SupabaseSink:
    def __init__(self, url: str, secret_key: str, bucket: str):
        from supabase import create_client
        self.client = create_client(url, secret_key)
        self.bucket = bucket

    def upload_image(self, path: str, data: bytes) -> None:
        self.client.storage.from_(self.bucket).upload(path, data, {"content-type": "image/jpeg", "upsert": "true"})

    def upsert_row(self, row: dict) -> None:
        self.client.table("violations").upsert(row).execute()

    def upsert_device(self, device: dict) -> None:
        self.client.table("devices").upsert(device).execute()

    def clean(self) -> None:
        self.client.table("violations").delete().like("device_id", "seed-%").execute()
        self.client.table("devices").delete().like("device_id", "seed-%").execute()
        storage = self.client.storage.from_(self.bucket)
        paths = []
        for device in DEVICES:
            for day in storage.list(device):                           # 날짜 폴더
                for obj in storage.list(f"{device}/{day['name']}", {"limit": 1000}):
                    paths.append(f"{device}/{day['name']}/{obj['name']}")
        for i in range(0, len(paths), 100):
            storage.remove(paths[i:i + 100])
        print(f"[cloud-seed] removed {len(paths)} image(s)")


class DryRunSink:
    """키 없이 확인: cloud/seed/.out/ 에 Storage 경로 그대로 사진을, rows.jsonl 에 행을 쓴다."""

    def __init__(self, out_dir: Path):
        self.out = out_dir
        self.out.mkdir(parents=True, exist_ok=True)

    def upload_image(self, path: str, data: bytes) -> None:
        target = self.out / "storage" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def upsert_row(self, row: dict) -> None:
        with (self.out / "rows.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def upsert_device(self, device: dict) -> None:
        with (self.out / "devices.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(device, ensure_ascii=False) + "\n")

    def clean(self) -> None:
        import shutil
        shutil.rmtree(self.out, ignore_errors=True)


# ── 시나리오 ────────────────────────────────────────────────

class Seeder:
    def __init__(self, sink, validator, samples_dir: Path, sleep=time.sleep, now=lambda: datetime.now(timezone.utc)):
        self.sink, self.validator, self.samples_dir = sink, validator, samples_dir
        self.sleep, self.now = sleep, now
        self.seq = 0

    def emit(self, row: dict, image: bool = True) -> dict:
        """gateway outbox 와 같은 순서: 검사 → 사진 먼저 → 행 upsert (03 §6.1)."""
        check_row(row, self.validator)
        if image:
            self.sink.upload_image(row["image_path"], annotated_jpeg(self.samples_dir, row))
        self.sink.upsert_row(row)
        kst = datetime.fromisoformat(row["captured_at"].replace("Z", "+00:00")).astimezone(KST)
        print(f"[cloud-seed] {row['device_id']} {kst:%m-%d %H:%M:%S} KST {row['violation_types']} "
              f"persons={row['person_count']} id={row['id'][:8]}{'' if image else ' (사진 없음)'}")
        return row

    def row(self, persons: list[dict], device_id: str = DEVICES[0], captured_at: datetime | None = None) -> dict:
        self.seq += 1
        return build_row(device_id, captured_at or self.now(), persons, frame_seq=self.seq)

    def random_persons(self) -> list[dict]:
        kind = random.choice(["helmet", "vest", "both"])
        return [person(ONE[0], helmet=kind == "vest", vest=kind == "helmet")]

    def one(self, _n=None) -> None:
        self.emit(self.row(self.random_persons()))

    def types(self, _n=None) -> None:
        cases = [
            [person(ONE[0], helmet=False)],
            [person(ONE[0], vest=False)],
            [person(ONE[0], helmet=False, vest=False)],
            [person(TWO[0]), person(TWO[1], helmet=False)],   # 2명 중 1명 위반
        ]
        for persons in cases:
            self.emit(self.row(persons))
            self.sleep(0.5)

    def burst(self, n=None) -> None:
        for i in range(n or 10):
            self.emit(self.row(self.random_persons(), device_id=DEVICES[i % 2]))
            self.sleep(1)

    def retry(self, _n=None) -> None:
        row = self.emit(self.row(self.random_persons()))
        self.sleep(2)
        print("[cloud-seed] retry: 같은 id 로 다시 upsert (웹에는 카드 1개여야 함)")
        self.emit(row)

    def late(self, _n=None) -> None:
        self.emit(self.row(self.random_persons(), captured_at=self.now() - timedelta(minutes=3)))

    def edges(self, _n=None) -> None:
        today = self.now().astimezone(KST).replace(hour=0, minute=0, second=0, microsecond=0)
        self.emit(self.row(self.random_persons(), captured_at=today - timedelta(minutes=1)))   # 어제 23:59 KST
        self.emit(self.row(self.random_persons(), captured_at=today + timedelta(minutes=1)))   # 오늘 00:01 KST

    def noimage(self, _n=None) -> None:
        self.emit(self.row(self.random_persons()), image=False)

    def devices(self, _n=None) -> None:
        now = self.now()
        for device_id, ago, error in ((DEVICES[0], 0, None), (DEVICES[1], 300, "http_503")):
            device = {"device_id": device_id, "gateway_id": GATEWAY_ID, "last_seen": iso_utc(now - timedelta(seconds=ago)),
                      "fw_version": "seed", "rssi": random.randint(-70, -45), "uptime_s": random.randint(60, 7200),
                      "free_heap": random.randint(150000, 200000), "last_error": error}
            if not DEVICE_ID_RE.match(device_id):
                raise ContractError(device_id)
            self.sink.upsert_device(device)
            print(f"[cloud-seed] device {device_id} last_seen {ago}s ago")

    def live(self, n=None) -> None:
        interval = n or 30
        print(f"[cloud-seed] {interval}초마다 위반 1건 - Ctrl+C 로 멈춤")
        try:
            while True:
                self.one()
                self.sleep(interval)
        except KeyboardInterrupt:
            print("[cloud-seed] stopped")

    def clean(self, _n=None) -> None:
        self.sink.clean()
        print("[cloud-seed] seed-* 데이터 삭제")


SCENARIOS = ("one", "types", "burst", "retry", "late", "edges", "noimage", "devices", "live", "clean")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="가짜 Pi: 계약 형식의 위반을 Supabase 에 올린다")
    parser.add_argument("scenario", nargs="?", default="one", choices=SCENARIOS)
    parser.add_argument("n", nargs="?", type=int, help="burst 건수 / live 간격(초)")
    parser.add_argument("--dry-run", action="store_true", help="Supabase 대신 cloud/seed/.out/ 에 쓴다")
    args = parser.parse_args(argv)

    load_env_file()
    samples_dir = _dir("SAMPLES_DIR", "/samples", "shared/samples")
    validator = make_validator(_dir("SCHEMAS_DIR", "/schemas", "shared/schemas"))
    if args.dry_run:
        sink = DryRunSink(HERE / ".out")
    else:
        url, key = os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_SECRET_KEY", "")
        if not url or not key or "your-project-ref" in url:
            parser.error("SUPABASE_URL, SUPABASE_SECRET_KEY 가 필요하다 (.env). 키 없이 보려면 --dry-run")
        sink = SupabaseSink(url, key, os.getenv("SUPABASE_BUCKET", "violation-images"))
    getattr(Seeder(sink, validator, samples_dir), args.scenario)(args.n)


if __name__ == "__main__":
    main()
