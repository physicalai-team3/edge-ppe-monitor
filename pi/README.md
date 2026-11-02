# pi — 👤 팀원 3 (Raspberry Pi 5)

| 폴더 | 컨테이너 | 하는 일 |
|---|---|---|
| `gateway/` | `gateway` :8000 | ESP32 사진 수신 → detector 호출 → 판정 → 위반이면 outbox → Supabase |
| `detector/` | `detector` :9000 (내부) | YOLOv8 PPE ONNX 추론. `DETECTOR_MODE=mock` 지원 |
| `cam-sim/` | `cam-sim` | 가짜 ESP32 |

```
gateway/app/
├── main.py             API 라우트 (03 §3)
├── config.py           환경 변수
├── detector_client.py  detector 호출 (03 §4)
├── judge.py            판정 규칙 — 순수 함수 (03 §5)
├── dedup.py            30초 쿨다운
├── annotate.py         박스 그리기
├── outbox.py           디스크 대기열 + 업로드 워커 (03 §6.1)
└── cloud.py            Supabase Storage + DB (03 §6)
```

```bash
docker compose --profile pi up -d --build                # Pi 에서
docker compose --profile pi --profile sim up --build     # 가짜 ESP32 와 함께
docker compose run --rm gateway pytest -q                # 판정 테스트
```
