# shared — 공동 소유 [contract]

| 경로 | 내용 |
|---|---|
| `schemas/frame-response.schema.json` | ESP32 ← gateway 응답 ([03 §3.2](../docs/03-contracts.md)) |
| `schemas/heartbeat.schema.json` | ESP32 → gateway 하트비트 ([03 §3.6](../docs/03-contracts.md)) |
| `schemas/error.schema.json` | gateway·detector 공통 에러 body ([03 §3.3](../docs/03-contracts.md)) |
| `schemas/detect-response.schema.json` | gateway ← detector 응답 ([03 §4](../docs/03-contracts.md)) |
| `schemas/violation-row.schema.json` | Supabase `violations` 1행 ([03 §6.3](../docs/03-contracts.md)) |
| `samples/` | 테스트 사진 (`cam-sim`, `cloud-seed`가 읽음) |

수정 시 커밋 메시지에 `[contract]`를 붙이고 관련된 사람에게 알린다.
