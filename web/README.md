# web — 👤 팀원 4 (대시보드)

Supabase 에서만 읽는 정적 페이지 (nginx). 계약: [docs/03-contracts.md §7](../docs/03-contracts.md).

| 기능 | 내용 |
|---|---|
| 위반 피드 | 최근 50건, `captured_at` 최신이 위 (늦게 도착한 위반도 시간 순서 자리에), `id` 로 중복 제거 |
| 사진 | 서명 URL 1시간 (처음 50건은 한 번에 발급). 실패·만료 시 "사진 없음" → 누르면 다시 발급 |
| 오늘 통계 | KST 0시 이후 기록 수·안전모·조끼, 장치별 건수. 자정에 자동 초기화 |
| 실시간 | `violations` INSERT 구독, 끊겼다 다시 연결되면 다시 조회 |
| 알림 | 새 위반 토스트 + (버튼으로 켜면) 소리. 1초 안에 여러 건이면 "새 위반 N건" 한 번 |
| 장치 상태 (2차) | `devices` 구독, `last_seen` 90초 이내면 온라인 |

## 실행

```bash
# 컨테이너
docker compose --profile web up --build                  # http://localhost:8080

# Docker 없이 — 루트 .env 를 읽어 public/config.js 를 만들고 띄운다
python web/dev-config.py --serve                          # http://localhost:8080
```

가짜 데이터는 `cloud/seed` ([cloud/README.md](../cloud/README.md#seed--가짜-gateway)): `seed.py burst`, `retry`, `late`, `edges`, `noimage`, `devices` 로 위 기능을 하나씩 확인한다.
