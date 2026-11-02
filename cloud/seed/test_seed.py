"""seed 가 계약(docs/03-contracts.md §6)대로 행을 만드는지 검사. Supabase 없이 돈다.
실행: cd cloud/seed && python -m pytest -q   (컨테이너: docker compose --profile seed run --rm cloud-seed python -m pytest -q)
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

import seed
from seed import ContractError, DryRunSink, Seeder, build_row, check_row, person

VALIDATOR = seed.make_validator(seed._dir("SCHEMAS_DIR", "/schemas", "shared/schemas"))
NOW = datetime(2026, 11, 2, 5, 31, 12, 345000, tzinfo=timezone.utc)   # KST 14:31


def test_single_violation_row_is_valid():
    row = build_row("seed-01", NOW, [person([200, 40, 420, 470], helmet=False)], frame_seq=1)
    check_row(row, VALIDATOR)
    assert row["violation_types"] == ["no_helmet"]
    assert row["no_helmet_count"] == 1 and row["no_vest_count"] == 0
    assert row["captured_at"] == "2026-11-02T05:31:12.345Z"
    assert row["image_path"] == f"seed-01/2026-11-02/{row['id']}.jpg"


def test_types_always_in_contract_order():
    row = build_row("seed-01", NOW, [person([200, 40, 420, 470], helmet=False, vest=False)])
    assert row["violation_types"] == ["no_helmet", "no_vest"]


def test_counts_and_order_for_two_persons():
    right, left = person([360, 50, 580, 470], helmet=False), person([60, 60, 260, 470])
    row = build_row("seed-01", NOW, [right, left])
    check_row(row, VALIDATOR)
    assert row["person_count"] == 2 and row["no_helmet_count"] == 1
    assert [p["box"][0] for p in row["persons"]] == [60, 360]


def test_image_path_uses_utc_date_not_kst():
    kst_morning = datetime(2026, 11, 2, 8, 0, tzinfo=seed.KST)            # = 11-01 23:00 UTC
    row = build_row("seed-01", kst_morning, [person([200, 40, 420, 470], vest=False)])
    assert row["image_path"].startswith("seed-01/2026-11-01/")
    check_row(row, VALIDATOR)


@pytest.mark.parametrize("breakage, message", [
    (lambda r: r.update(violation_types=["no_vest", "no_helmet"]), "순서"),
    (lambda r: r.update(no_helmet_count=0), "no_helmet_count"),
    (lambda r: r.update(captured_at="2026-11-02T14:31:12+09:00"), "UTC"),
    (lambda r: r.update(created_at="2026-11-02T05:31:12Z"), "created_at"),
    (lambda r: r.update(device_id="Seed_01"), "device_id"),
])
def test_contract_violations_are_caught(breakage, message):
    row = build_row("seed-01", NOW, [person([200, 40, 420, 470], helmet=False, vest=False)])
    breakage(row)
    with pytest.raises(ContractError, match=message):
        check_row(row, VALIDATOR)


@pytest.mark.parametrize("scenario, n, expected_rows", [
    ("one", None, 1), ("types", None, 4), ("burst", 4, 4), ("retry", None, 2),
    ("late", None, 1), ("edges", None, 2), ("noimage", None, 1),
])
def test_scenarios_dry_run(tmp_path, scenario, n, expected_rows):
    seeder = Seeder(DryRunSink(tmp_path), VALIDATOR, tmp_path / "no-samples", sleep=lambda s: None, now=lambda: NOW)
    getattr(seeder, scenario)(n)
    rows = [json.loads(line) for line in (tmp_path / "rows.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == expected_rows
    images = list((tmp_path / "storage").rglob("*.jpg")) if (tmp_path / "storage").exists() else []
    if scenario == "noimage":
        assert images == []
    else:
        assert {p.relative_to(tmp_path / "storage").as_posix() for p in images} == {r["image_path"] for r in rows}


def test_retry_reuses_same_id(tmp_path):
    seeder = Seeder(DryRunSink(tmp_path), VALIDATOR, tmp_path, sleep=lambda s: None, now=lambda: NOW)
    seeder.retry()
    ids = [json.loads(line)["id"] for line in (tmp_path / "rows.jsonl").read_text(encoding="utf-8").splitlines()]
    assert ids[0] == ids[1]


def test_edges_straddle_kst_midnight(tmp_path):
    seeder = Seeder(DryRunSink(tmp_path), VALIDATOR, tmp_path, sleep=lambda s: None, now=lambda: NOW)
    seeder.edges()
    rows = [json.loads(line) for line in (tmp_path / "rows.jsonl").read_text(encoding="utf-8").splitlines()]
    kst = [datetime.fromisoformat(r["captured_at"].replace("Z", "+00:00")).astimezone(seed.KST) for r in rows]
    assert [k.strftime("%m-%d %H:%M") for k in kst] == ["11-01 23:59", "11-02 00:01"]


def test_devices_dry_run(tmp_path):
    seeder = Seeder(DryRunSink(tmp_path), VALIDATOR, tmp_path, sleep=lambda s: None, now=lambda: NOW)
    seeder.devices()
    devices = [json.loads(line) for line in (tmp_path / "devices.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [d["device_id"] for d in devices] == ["seed-01", "seed-02"]
    last_seen = [datetime.fromisoformat(d["last_seen"].replace("Z", "+00:00")) for d in devices]
    assert NOW - last_seen[1] == timedelta(minutes=5)
