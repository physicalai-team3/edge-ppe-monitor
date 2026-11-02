"""Supabase 설정 점검 (cloud/README.md 4번 "확인"을 자동으로). 아무것도 남기지 않는다.

    .venv/Scripts/python cloud/check.py      # 루트 .env 를 읽는다 (macOS/Linux: .venv/bin/python)

점검: 키 형식·뒤바뀜 / 테이블 2개 / private 버킷 / publishable 키: 읽기 O, 쓰기 X, 사진 업로드 X, 서명 URL O.
Realtime 은 브라우저에서만 확인된다 → 웹을 띄우고 `seed.py one`.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "seed"))
import seed  # noqa: E402  (load_env_file, build_row 재사용)

results: list[bool] = []


def report(ok: bool, what: str, detail: str = "") -> bool:
    results.append(ok)
    print(f"{'OK  ' if ok else 'FAIL'} {what}" + (f" - {detail}" if detail else ""))
    return ok


def main() -> int:
    seed.load_env_file()
    url = os.getenv("SUPABASE_URL", "")
    secret = os.getenv("SUPABASE_SECRET_KEY", "")
    publishable = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    bucket = os.getenv("SUPABASE_BUCKET", "violation-images")

    # 1) .env 값
    if not report(url.startswith("https://") and "your-project-ref" not in url, "SUPABASE_URL", url or "(비어 있음)"):
        return 1
    if not report(bool(secret) and bool(publishable), "키 2개가 채워짐"):
        return 1
    report(not publishable.startswith("sb_secret_"), "publishable 자리에 secret 키가 없음",
           "SUPABASE_PUBLISHABLE_KEY 는 브라우저에 노출된다. 바로 바꿀 것" if publishable.startswith("sb_secret_") else "")
    report(not secret.startswith("sb_publishable_"), "secret 자리에 publishable 키가 없음")

    from supabase import create_client
    admin = create_client(url, secret)
    anon = create_client(url, publishable)

    # 2) init.sql 이 적용됐나 (secret 키)
    for table in ("violations", "devices"):
        try:
            admin.table(table).select("*").limit(1).execute()
            report(True, f"테이블 {table}")
        except Exception as e:
            report(False, f"테이블 {table}", f"{e} → SQL Editor 에서 init.sql 실행")
    try:
        b = admin.storage.get_bucket(bucket)
        report(not b.public, f"버킷 {bucket} (private)", "public 이면 사진이 그대로 공개된다" if b.public else "")
    except Exception as e:
        report(False, f"버킷 {bucket}", f"{e} → init.sql 의 Storage 부분 확인")

    # 3) RLS: publishable 키 = 웹
    try:
        anon.table("violations").select("id").limit(1).execute()
        report(True, "publishable 키로 violations 읽기")
    except Exception as e:
        report(False, "publishable 키로 violations 읽기", str(e))

    row = seed.build_row("seed-01", datetime.now(timezone.utc), [seed.person(seed.ONE[0], helmet=False)])
    try:
        anon.table("violations").insert(row).execute()
        admin.table("violations").delete().eq("id", row["id"]).execute()      # 들어갔으면 지운다
        report(False, "publishable 키로 violations 쓰기 거부", "들어갔다! RLS 가 꺼져 있음")
    except Exception:
        report(True, "publishable 키로 violations 쓰기 거부")

    probe = f"seed-01/check/{uuid.uuid4()}.jpg"
    try:
        anon.storage.from_(bucket).upload(probe, b"\xff\xd8\xff\xd9", {"content-type": "image/jpeg"})
        admin.storage.from_(bucket).remove([probe])
        report(False, "publishable 키로 사진 업로드 거부", "올라갔다! Storage 정책 확인")
    except Exception:
        report(True, "publishable 키로 사진 업로드 거부")

    # 4) 서명 URL: secret 으로 올리고 publishable 로 발급 (웹이 하는 일)
    try:
        admin.storage.from_(bucket).upload(probe, b"\xff\xd8\xff\xd9", {"content-type": "image/jpeg", "upsert": "true"})
        signed = anon.storage.from_(bucket).create_signed_url(probe, 60)
        report(bool(signed.get("signedURL") or signed.get("signedUrl")), "publishable 키로 서명 URL 발급")
    except Exception as e:
        report(False, "publishable 키로 서명 URL 발급", str(e))
    finally:
        try:
            admin.storage.from_(bucket).remove([probe])
        except Exception:
            pass

    print(f"\n{sum(results)}/{len(results)} 통과" + ("" if all(results) else " - FAIL 항목을 확인"))
    print("다음: python web/dev-config.py --serve 로 웹을 띄우고 seed.py one → 새로고침 없이 카드가 뜨면 Realtime 도 OK")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
