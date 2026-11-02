# cloud — 👤 팀원 4 (Supabase)

## 처음 설정 (오전 첫 일)

1. Supabase에서 새 프로젝트 생성 (리전: Seoul `ap-northeast-2`).
2. SQL Editor에서 [supabase/migrations/20261102000000_init.sql](supabase/migrations/20261102000000_init.sql) 실행.
   - 테이블 `violations`, `devices` / RLS(읽기만 허용) / Realtime / Storage 버킷 `violation-images`(private)
3. Project Settings → API Keys 에서 키 확인 후 전달:

| 키 | 누구에게 | 어디에 |
|---|---|---|
| Project URL | 전원 | `.env`의 `SUPABASE_URL` |
| **secret** (`sb_secret_…`, 예전 service_role) | **팀원 3에게만 DM** | Pi `.env`의 `SUPABASE_SECRET_KEY` |
| publishable (`sb_publishable_…`, 예전 anon) | 웹(본인) | `.env`의 `SUPABASE_PUBLISHABLE_KEY` |

4. 확인
   - `docker compose --profile seed run --rm cloud-seed` → Table Editor에 행 1개, Storage에 사진 1장
   - publishable 키로 insert 시도 → **거부되어야 정상** (RLS)

## 폴더

| 경로 | 내용 |
|---|---|
| `supabase/migrations/` | [contract] 스키마 SQL. 바꿀 때는 새 파일을 추가 (`YYYYMMDDHHMMSS_설명.sql`) |
| `seed/` | 가짜 Pi — 위반 1건 업로드 |
