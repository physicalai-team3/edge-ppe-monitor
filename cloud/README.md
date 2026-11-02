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

   - 키는 **새 형식**(`sb_secret_…`, `sb_publishable_…`)을 쓴다. supabase-py **2.10.0 은 새 형식 키를 `Invalid API key` 로 거부**하므로 seed 는 2.33.0 을 쓴다 (gateway 도 올려야 함, 아니면 Legacy API Keys 탭의 JWT 키 사용).
4. 확인
   - `.venv/Scripts/python cloud/check.py` → 키 형식, 테이블 2개, private 버킷, publishable 키 읽기 O·쓰기 X·업로드 X·서명 URL O 를 자동 점검 (흔적 남기지 않음)
   - `docker compose --profile seed run --rm cloud-seed` (또는 `cd cloud/seed && ../../.venv/Scripts/python seed.py`) → Table Editor에 행 1개, Storage에 사진 1장
   - 웹을 띄운 채로 `seed.py one` → 새로고침 없이 카드가 뜨면 Realtime OK

## 폴더

| 경로 | 내용 |
|---|---|
| `supabase/migrations/` | [contract] 스키마 SQL. 바꿀 때는 새 파일을 추가 (`YYYYMMDDHHMMSS_설명.sql`) |
| `seed/` | 가짜 Pi — gateway 와 같은 형식으로 위반을 업로드 (시나리오 10종) |

## seed — 가짜 gateway

gateway(팀원 3)가 쓸 것과 **같은 테이블·버킷·행 형식**([03 §6](../docs/03-contracts.md))으로 쓴다. 웹은 둘을 구분하지 않으므로, 나중에 gateway 가 붙어도 웹 코드는 바뀌지 않는다.
모든 행은 올리기 전에 `shared/schemas/violation-row.schema.json` + 계약 규칙(위반 순서, 개수, UTC, `image_path`)으로 검사한다. 장치는 `seed-01`, `seed-02`만 쓴다.

| 명령 | 만드는 것 | 웹에서 확인할 것 |
|---|---|---|
| `one` (기본) | 위반 1건 | 새로고침 없이 카드 1개, 통계 +1 |
| `types` | no_helmet / no_vest / 둘 다 / 2명 중 1명 | 라벨, 안전모·조끼 합계 |
| `burst [N]` | N건(기본 10) 1초 간격, 장치 2개 | 순서, 중복 없음, 알림 |
| `retry` | 같은 id 로 2번 upsert (outbox 재시도) | 카드 1개, 통계 +1 |
| `late` | captured_at 3분 전 (outbox 지연) | 시간 순서 자리에 들어감 |
| `edges` | KST 어제 23:59, 오늘 00:01 | 어제 것은 오늘 통계에서 빠짐 |
| `noimage` | 행만, 사진 없음 | "사진 없음" 표시 |
| `devices` | devices: seed-01 방금, seed-02 5분 전 | 온라인 1 / 오프라인 1 (2차) |
| `live [S]` | S초(기본 30)마다 1건, Ctrl+C 로 멈춤 | 데모 리허설 |
| `clean` | seed-* 행·사진·장치 삭제 | 피드 비워짐 (데모 전) |

```bash
# 컨테이너
docker compose --profile seed run --rm cloud-seed                       # one
docker compose --profile seed run --rm cloud-seed python seed.py burst 10
docker compose --profile seed run --rm cloud-seed python -m pytest -q   # 계약 테스트

# 로컬 (Docker 없이) — 루트 .env 를 자동으로 읽는다
python -m venv .venv && .venv/Scripts/pip install -r cloud/seed/requirements.txt   # macOS/Linux: .venv/bin/pip
cd cloud/seed
../../.venv/Scripts/python seed.py types
../../.venv/Scripts/python seed.py types --dry-run   # 키 없이: cloud/seed/.out/ 에 사진·rows.jsonl
../../.venv/Scripts/python -m pytest -q
```
