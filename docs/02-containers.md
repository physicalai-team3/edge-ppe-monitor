# 02. 컨테이너 구성

## 1. 원칙

- **한 기능 = 한 컨테이너 = 한 주인.** 컨테이너 경계가 곧 사람 사이의 경계다.
- **어디서 돌리나**로 프로필을 나눈다. 파일은 루트 `docker-compose.yml` 하나, 실행은 `--profile`로 고른다.
- **가짜 컨테이너**(`cam-sim`, `cloud-seed`)로 상대가 준비되지 않아도 개발한다.

## 2. 컨테이너 목록

| 컨테이너 | 프로필 | 어디서 | 주인 | 하는 일 | 포트 |
|---|---|---|---|---|---|
| `gateway` | `pi` | Pi 5 | 팀원 3 | ESP32 사진 받기 → detector 호출 → 판정 → outbox → Supabase | **8000** (ESP32가 접속) |
| `detector` | `pi` | Pi 5 | 팀원 3 | YOLOv8 ONNX 추론 (`mock` 모드 지원) | 9000 (내부 전용) |
| `cam-sim` | `sim` | Pi 또는 노트북 | 팀원 3 | 가짜 ESP32: 샘플 사진을 주기적으로 gateway에 POST | — |
| `web` | `web` | 노트북 | 팀원 4 | 대시보드 정적 파일 (nginx) | **8080** |
| `cloud-seed` | `seed` | 노트북 | 팀원 4 | 가짜 Pi: 샘플 위반 1건을 Supabase에 업로드 | — |
| `fw` | `firmware` | 노트북 | 팀원 2 | arduino-cli로 펌웨어 컴파일·단위 테스트 (업로드는 Arduino IDE) | — |

ESP32 보드 자체는 컨테이너가 아니다. 보드 안에서는 **파일**로 일을 나눈다 (팀원 1: `person_sensor.*`, 팀원 2: 나머지).
Supabase도 컨테이너가 아니다. 클라우드 프로젝트 하나를 팀원 4가 만들고 나머지가 키를 받아 쓴다.

```
┌─────────────── Raspberry Pi 5 ── --profile pi ────────────────┐
│                                                                │
│  ESP32 ──:8000──▶ gateway ──http://detector:9000──▶ detector   │
│                     │  volume: pi/gateway/data → /data (outbox)│       volume: pi/detector/models → /models (ro)
│                     └──HTTPS──▶ Supabase                        │
└────────────────────────────────────────────────────────────────┘

┌─────────────── 노트북 ─────────────────────────────────────────┐
│  --profile web      web (nginx :8080) ── 브라우저               │
│  --profile seed     cloud-seed ──HTTPS──▶ Supabase (1회 실행)   │
│  --profile firmware fw (arduino-cli, 1회 실행)                  │
│  --profile sim      cam-sim ──▶ gateway (Pi IP 또는 같은 compose)│
└────────────────────────────────────────────────────────────────┘
```

## 3. 실행 방법

```bash
cp .env.example .env          # 값 채우기 (.env 는 git 에 안 올라감)
```

### 팀원 3 — Pi

```bash
# Pi 에서
docker compose --profile pi up -d --build
docker compose logs -f gateway
curl http://localhost:8000/healthz

# 보드 없이: 가짜 ESP32 함께 띄우기
docker compose --profile pi --profile sim up --build

# 모델 없이: .env 에 DETECTOR_MODE=mock
```

노트북에서 먼저 개발해도 된다. 이미지가 `python:3.11-slim` 기반이라 노트북(amd64)·Pi(arm64) 둘 다 빌드된다.

### 팀원 4 — 웹 / 클라우드

```bash
docker compose --profile web up --build       # http://localhost:8080
docker compose --profile seed run --rm cloud-seed   # 가짜 위반 1건 → 웹에 카드가 떠야 함
```

### 팀원 1·2 — 펌웨어

```bash
docker compose --profile firmware run --rm fw                 # 컴파일 확인
docker compose --profile firmware run --rm fw sh test.sh      # trigger 단위 테스트 (PC에서)
```

업로드는 각자 Arduino IDE (보드 `XIAO_ESP32S3`, PSRAM `OPI PSRAM`, 스케치북 위치 `firmware/`).

## 4. 환경 변수 (`.env`)

| 변수 | 쓰는 곳 | 기본값 | 설명 |
|---|---|---|---|
| `DEVICE_API_KEY` | gateway, cam-sim | `change-me` | ESP32 `PPE_DEVICE_KEY`와 같아야 함 |
| `GATEWAY_PORT` | gateway | `8000` | 호스트에 여는 포트 |
| `GATEWAY_ID` | gateway | `pi-01` | |
| `VIOLATION_COOLDOWN_S` | gateway | `30` | 같은 위반 반복 업로드 방지 ([03 §5.4](03-contracts.md#54-쿨다운-중복-업로드-방지)) |
| `JUDGE_UNKNOWN_AS_VIOLATION` | gateway | `false` | `true`면 보호구가 안 보일 때(판단 불가)도 위반으로 침 ([03 §5.2](03-contracts.md#52-사람별-착용-여부)) |
| `CLOUD_ENABLED` | gateway | `true` | `false`면 판정만 하고 업로드 안 함 |
| `DETECTOR_MODE` | detector | `onnx` | `onnx` \| `mock` |
| `MODEL_FILE` | detector | `ppe.onnx` | `pi/detector/models/` 안의 파일 이름 |
| `CONF_THRESHOLD` / `IOU_THRESHOLD` | detector | `0.4` / `0.5` | |
| `SUPABASE_URL` | gateway, web, cloud-seed | | `https://<ref>.supabase.co` |
| `SUPABASE_SECRET_KEY` | gateway, cloud-seed | | **쓰기 키. Pi·팀원 4 노트북에만** |
| `SUPABASE_PUBLISHABLE_KEY` | web | | 읽기 키 (브라우저에 노출됨) |
| `SUPABASE_BUCKET` | gateway, web, cloud-seed | `violation-images` | |
| `WEB_PORT` | web | `8080` | |
| `SIM_GATEWAY_URL` | cam-sim | `http://gateway:8000` | 다른 기기에서 돌리면 `http://<Pi IP>:8000` |
| `SIM_DEVICE_ID` / `SIM_INTERVAL_S` | cam-sim | `sim-01` / `3` | |

코드에 고정된 값 (바꾸려면 [03-contracts.md](03-contracts.md)부터 수정): 이미지 상한 512KB, gateway→detector 타임아웃 4초, ESP32 HTTP 타임아웃 5초, outbox 재시도 10초, 장치 오프라인 기준 90초.

## 5. 네트워크 체크리스트 (통합 전에)

- [ ] Pi IP 확인: `hostname -I` → 팀 채팅에 공유, ESP32 `config.h`의 `PPE_GATEWAY_HOST`에 입력
- [ ] 노트북에서 `curl http://<Pi IP>:8000/healthz` 성공 (같은 공유기인지 확인)
- [ ] ESP32는 **2.4GHz** SSID에 접속 (이름에 `_5G` X)
- [ ] Pi에서 `curl https://<ref>.supabase.co` 성공 (인터넷)
- [ ] Pi 방화벽(`ufw`)을 쓰면 8000 허용
